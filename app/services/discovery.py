"""
Auto-discovery service — scan a domain to find monitorable endpoints.
Checks sitemap, robots.txt, homepage links, common paths, and SSL cert.
"""

import asyncio
import re
import ssl
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_URLS = 50
PROBE_TIMEOUT = 10
USER_AGENT = "StatusRooster/1.0 (https://statusrooster.com)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

COMMON_PATHS = [
    "/api/health", "/api/v1", "/api/status", "/api", "/graphql",
    "/login", "/signup", "/dashboard", "/admin", "/docs", "/app",
    "/.well-known/security.txt",
]

# Priority rules: path substring → priority
HIGH_PRIORITY_PATTERNS = ["/", "/api", "/health", "/status", "/graphql", "/login", "/signup", "/app", "/dashboard"]
LOW_PRIORITY_PATTERNS = ["/terms", "/privacy", "/cookie", "/legal", "/tos", "/sitemap", "/robots", "/feed", "/rss"]

# Patterns that indicate deep/content pages (skip these)
SKIP_PATTERNS = re.compile(
    r'/(?:ip|dp|product|item|blog|news|articles?|posts?|collections|shop|products|categories|tags|archive|reviews?|comments?)/|'
    r'/\d{4,}|'              # numeric IDs (4+ digits)
    r'\.(pdf|jpg|png|gif|svg|css|js|xml|json|zip|webp)$|'
    r'[?#]',                 # query strings or fragments
    re.IGNORECASE,
)

# Important first path segments — always keep regardless of depth
IMPORTANT_SEGMENTS = {
    'api', 'health', 'status', 'login', 'signup', 'dashboard',
    'admin', 'docs', 'app', 'graphql', 'pricing', 'contact',
    'about', 'help', 'support', 'settings', 'account',
}


def _is_structural_url(url: str) -> bool:
    """Return True if URL looks like a structural/navigational page worth monitoring."""
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')

    if not path:
        return True  # homepage

    # Skip file extensions, query strings, deep content
    if SKIP_PATTERNS.search(path):
        return False

    # Skip very long paths
    if len(path) > 80:
        return False

    segments = [s for s in path.split('/') if s]

    # Always keep important paths
    if segments and segments[0].lower() in IMPORTANT_SEGMENTS:
        return True

    # Max 2 path segments for general pages
    if len(segments) > 2:
        return False

    return True


# ---------------------------------------------------------------------------
# Link extractor (lightweight, no BeautifulSoup)
# ---------------------------------------------------------------------------

class _LinkExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                url = urljoin(self.base_url, value)
                parsed = urlparse(url)
                if parsed.netloc == self.base_domain and parsed.scheme in ("http", "https"):
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if clean not in self.links:
                        self.links.append(clean)


# ---------------------------------------------------------------------------
# Name + priority helpers
# ---------------------------------------------------------------------------

def _suggest_name(url: str, domain: str) -> str:
    """Generate a human-readable name from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    if not path or path == "/":
        return "Homepage"

    # Clean up the path segment
    segment = path.split("/")[-1]
    # Handle common patterns
    name_map = {
        "health": "API Health", "status": "API Status", "graphql": "GraphQL",
        "login": "Login Page", "signup": "Signup Page", "dashboard": "Dashboard",
        "admin": "Admin Panel", "docs": "Documentation", "app": "App",
        "security.txt": "Security Policy", "api": "API", "v1": "API v1",
    }
    if segment in name_map:
        return name_map[segment]

    # Title-case the segment
    return segment.replace("-", " ").replace("_", " ").title()


def _suggest_priority(url: str) -> str:
    """Assign high/medium/low priority based on URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"

    for pattern in LOW_PRIORITY_PATTERNS:
        if pattern in path.lower():
            return "low"
    for pattern in HIGH_PRIORITY_PATTERNS:
        if path.lower() == pattern or path.lower().startswith(pattern + "/"):
            return "high"
    if path == "/":
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# Scanning functions
# ---------------------------------------------------------------------------

async def _fetch(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    """Fetch a URL, return response or None on failure."""
    try:
        return await client.get(url, headers=HEADERS, follow_redirects=True, timeout=PROBE_TIMEOUT)
    except Exception:
        return None


async def _parse_sitemap(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    """Fetch /sitemap.xml and extract URLs."""
    results = []
    resp = await _fetch(client, f"{base_url}/sitemap.xml")
    if not resp or resp.status_code != 200:
        return results

    text = resp.text
    # Simple XML parsing — extract <loc> tags
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.IGNORECASE)
    domain = urlparse(base_url).netloc

    for loc in locs:
        parsed = urlparse(loc)
        if parsed.netloc == domain and parsed.scheme in ("http", "https") and _is_structural_url(loc):
            results.append({"url": loc, "source": "sitemap"})
            if len(results) >= MAX_URLS:
                break

    return results


async def _parse_robots(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    """Fetch /robots.txt, look for Sitemap: directives, fetch those sitemaps."""
    results = []
    resp = await _fetch(client, f"{base_url}/robots.txt")
    if not resp or resp.status_code != 200:
        return results

    sitemap_urls = re.findall(r"^Sitemap:\s*(.+)$", resp.text, re.MULTILINE | re.IGNORECASE)
    for sm_url in sitemap_urls[:5]:
        sm_url = sm_url.strip()
        sm_resp = await _fetch(client, sm_url)
        if sm_resp and sm_resp.status_code == 200:
            locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", sm_resp.text, re.IGNORECASE)
            domain = urlparse(base_url).netloc
            for loc in locs:
                parsed = urlparse(loc)
                if parsed.netloc == domain and _is_structural_url(loc):
                    results.append({"url": loc, "source": "sitemap"})
                    if len(results) >= MAX_URLS:
                        break

    return results


async def _crawl_homepage(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    """Fetch homepage and extract same-domain links."""
    results = []
    resp = await _fetch(client, base_url)
    if not resp or resp.status_code != 200:
        return results

    try:
        parser = _LinkExtractor(base_url)
        parser.feed(resp.text[:500_000])  # Cap parsing to 500KB
        for link in parser.links:
            if _is_structural_url(link):
                results.append({"url": link, "source": "crawl"})
                if len(results) >= MAX_URLS:
                    break
    except Exception:
        pass

    return results


async def _probe_common_paths(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    """Probe common paths concurrently, return those that respond with 200."""
    results = []
    urls = [f"{base_url}{path}" for path in COMMON_PATHS]

    responses = await asyncio.gather(*[_fetch(client, url) for url in urls])
    for url, resp in zip(urls, responses):
        if resp and resp.status_code == 200:
            results.append({"url": url, "source": "probe"})

    return results


def _grab_ssl_info(domain: str) -> dict | None:
    """Grab SSL certificate info for a domain. Returns dict or None."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                der = ssock.getpeercert(binary_form=True)
        cert = x509.load_der_x509_certificate(der, default_backend())
        expiry = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.replace(tzinfo=timezone.utc)
        days_remaining = (expiry - datetime.now(timezone.utc)).days
        issuer_parts = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATION_NAME)
        issuer = issuer_parts[0].value if issuer_parts else "Unknown"

        return {
            "domain": domain,
            "issuer": issuer,
            "expiry": expiry.isoformat(),
            "days_remaining": days_remaining,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main discovery function
# ---------------------------------------------------------------------------

async def discover_endpoints(domain: str, max_urls: int = MAX_URLS) -> dict:
    """
    Scan a domain and return discovered endpoints.

    Returns:
        {
            "domain": str,
            "urls": [{"url", "source", "suggested_name", "suggested_type", "suggested_priority"}, ...],
            "ssl": {...} or None,
            "total_found": int,
            "sources": {"sitemap": N, "crawl": N, "probe": N},
            "status": "ok" | "error message",
        }
    """
    # Normalize domain
    domain = domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.rstrip("/")
    # Remove path if someone pasted a full URL
    domain = domain.split("/")[0]

    base_url = f"https://{domain}"
    result = {
        "domain": domain,
        "urls": [],
        "ssl": None,
        "total_found": 0,
        "sources": {"sitemap": 0, "crawl": 0, "probe": 0},
        "status": "ok",
    }

    try:
        # verify=False intentional — discovery scans unknown domains that may have
        # expired/self-signed certs. We still detect and report SSL info separately.
        async with httpx.AsyncClient(verify=False) as client:
            # Run all discovery methods concurrently
            sitemap_task = _parse_sitemap(client, base_url)
            robots_task = _parse_robots(client, base_url)
            crawl_task = _crawl_homepage(client, base_url)
            probe_task = _probe_common_paths(client, base_url)

            sitemap_results, robots_results, crawl_results, probe_results = await asyncio.gather(
                sitemap_task, robots_task, crawl_task, probe_task,
                return_exceptions=True,
            )

            # Merge results, handling exceptions
            all_urls: list[dict] = []
            for batch in [sitemap_results, robots_results, crawl_results, probe_results]:
                if isinstance(batch, list):
                    all_urls.extend(batch)

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[dict] = []
        for item in all_urls:
            url_normalized = item["url"].rstrip("/")
            if url_normalized not in seen:
                seen.add(url_normalized)
                unique.append(item)

        # Ensure homepage is included
        homepage_normalized = base_url.rstrip("/")
        if homepage_normalized not in seen:
            unique.insert(0, {"url": base_url, "source": "probe"})

        # Cap results
        unique = unique[:max_urls]

        # Enrich with metadata
        for item in unique:
            item["suggested_name"] = f"{domain} - {_suggest_name(item['url'], domain)}"
            item["suggested_type"] = "http"
            item["suggested_priority"] = _suggest_priority(item["url"])

        # Sort: high first, then medium, then low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        unique.sort(key=lambda x: priority_order.get(x["suggested_priority"], 1))

        # SSL detection (synchronous, run in thread)
        ssl_info = await asyncio.to_thread(_grab_ssl_info, domain)
        result["ssl"] = ssl_info

        # Add SSL as first URL entry if detected
        if ssl_info:
            unique.insert(0, {
                "url": domain,
                "source": "probe",
                "suggested_name": f"SSL - {domain}",
                "suggested_type": "ssl",
                "suggested_priority": "high",
                "ssl_info": ssl_info,
            })

        result["urls"] = unique
        result["total_found"] = len(unique)
        result["sources"] = {
            "sitemap": sum(1 for u in unique if u["source"] == "sitemap"),
            "crawl": sum(1 for u in unique if u["source"] == "crawl"),
            "probe": sum(1 for u in unique if u["source"] == "probe"),
        }

    except httpx.ConnectError:
        result["status"] = f"Could not connect to {domain}. Check the domain and try again."
    except httpx.ConnectTimeout:
        result["status"] = f"Connection to {domain} timed out."
    except Exception as e:
        result["status"] = f"Discovery failed: {str(e)[:100]}"

    return result
