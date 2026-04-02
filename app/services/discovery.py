"""
Auto-discovery service — scan a domain to find monitorable endpoints.
Checks sitemap, robots.txt, homepage links, common paths, and SSL cert.
Scores URLs 0-100 to filter junk and prioritize important endpoints.
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

# Minimum score to include in results; pre-check threshold for UI
SCORE_SHOW_THRESHOLD = 30
SCORE_PRECHECK_THRESHOLD = 60


# ---------------------------------------------------------------------------
# URL Scoring (replaces binary include/exclude filtering)
# ---------------------------------------------------------------------------

def _score_url(url: str, status_code: int = 200, response_ms: float = 0,
               content_type: str = "", source: str = "crawl") -> int:
    """
    Score a URL 0-100 based on how likely it is to be worth monitoring.
    Higher = more important to monitor.
    """
    score = 50  # baseline
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").lower() or "/"
    segments = [s for s in path.split("/") if s]

    # ── SOURCE BONUS ──────────────────────────
    if source == "sitemap":
        score += 5
    if source == "probe":
        score += 10

    # ── PATH IMPORTANCE (biggest signal) ──────

    # Homepage is always critical
    if path == "/":
        score += 40

    # API and infrastructure endpoints
    api_patterns = {"api", "health", "healthz", "healthcheck", "status",
                    "ping", "graphql", "webhook", "webhooks", "v1", "v2", "v3"}
    if segments and segments[0] in api_patterns:
        score += 35
    elif any(seg in api_patterns for seg in segments):
        score += 25

    # Authentication pages
    auth_patterns = {"login", "signin", "sign-in", "signup", "sign-up",
                     "register", "auth", "oauth", "sso"}
    if segments and segments[0] in auth_patterns:
        score += 30

    # Core app pages
    app_patterns = {"dashboard", "app", "console", "portal", "admin",
                    "settings", "account", "billing", "checkout", "pay"}
    if segments and segments[0] in app_patterns:
        score += 25

    # Documentation and support
    docs_patterns = {"docs", "documentation", "help", "support", "faq",
                     "guides", "reference"}
    if segments and segments[0] in docs_patterns:
        score += 10

    # Marketing pages
    marketing_patterns = {"pricing", "features", "about", "contact",
                          "demo", "tour", "integrations"}
    if segments and segments[0] in marketing_patterns:
        score += 10

    # ── PATH PENALTIES (filter out junk) ──────

    # Deep paths are almost always content, not structure
    if len(segments) > 3:
        score -= 30
    elif len(segments) > 2:
        score -= 15

    # Numeric IDs = dynamic content pages
    if re.search(r'/\d{3,}', path):
        score -= 35

    # Date slugs = blog/news content
    if re.search(r'/\d{4}/\d{2}', path):
        score -= 40

    # Known content/junk path patterns
    content_patterns = [
        "/blog", "/news", "/articles", "/posts", "/stories",
        "/ip/", "/dp/", "/product/", "/item/", "/listing/",
        "/tag/", "/tags/", "/category/", "/categories/",
        "/archive", "/feed", "/rss", "/atom",
        "/wp-content", "/wp-admin", "/wp-includes",
        "/cdn-cgi", "/assets/", "/static/",
    ]
    for pattern in content_patterns:
        if pattern in path:
            score -= 30
            break

    # Legal/boilerplate pages
    legal_patterns = ["/terms", "/privacy", "/cookie", "/legal",
                      "/tos", "/gdpr", "/dmca", "/disclaimer",
                      "/sitemap", "/robots"]
    for pattern in legal_patterns:
        if pattern in path:
            score -= 25
            break

    # File extensions that aren't pages
    if re.search(r'\.(pdf|jpg|jpeg|png|gif|svg|css|js|xml|json|zip|webp|ico|woff|mp4|mp3)$', path):
        score -= 50

    # Query strings suggest dynamic/filtered content
    if parsed.query:
        score -= 15

    # Fragment-only links aren't real endpoints
    if parsed.fragment and not parsed.path.strip("/"):
        score -= 50

    # Very long paths
    if len(path) > 80:
        score -= 20

    # ── RESPONSE SIGNALS ──────────────────────

    if response_ms and response_ms < 100:
        score += 5

    if status_code and status_code != 200:
        if status_code in (301, 302, 307, 308):
            score -= 10
        elif status_code in (401, 403):
            score -= 15
        elif status_code == 404:
            score -= 40
        elif status_code >= 500:
            score -= 5  # broken right now, but WORTH monitoring

    if content_type:
        if "json" in content_type:
            score += 10
        elif "html" not in content_type and "text" not in content_type:
            score -= 20

    return max(0, min(100, score))


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
# Name helper
# ---------------------------------------------------------------------------

def _suggest_name(url: str, domain: str) -> str:
    """Generate a human-readable name from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    if not path or path == "/":
        return "Homepage"

    segment = path.split("/")[-1]
    name_map = {
        "health": "API Health", "healthz": "API Health", "healthcheck": "API Health",
        "status": "API Status", "graphql": "GraphQL",
        "login": "Login Page", "signin": "Login Page", "sign-in": "Login Page",
        "signup": "Signup Page", "sign-up": "Signup Page", "register": "Signup Page",
        "dashboard": "Dashboard", "admin": "Admin Panel",
        "docs": "Documentation", "documentation": "Documentation",
        "app": "App", "console": "Console", "portal": "Portal",
        "security.txt": "Security Policy", "api": "API", "v1": "API v1", "v2": "API v2",
        "pricing": "Pricing", "about": "About", "contact": "Contact",
        "help": "Help", "support": "Support", "faq": "FAQ",
        "settings": "Settings", "account": "Account", "billing": "Billing",
    }
    if segment in name_map:
        return name_map[segment]

    return segment.replace("-", " ").replace("_", " ").title()


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
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, re.IGNORECASE)
    domain = urlparse(base_url).netloc

    for loc in locs:
        parsed = urlparse(loc)
        if parsed.netloc == domain and parsed.scheme in ("http", "https"):
            results.append({"url": loc, "source": "sitemap"})
            if len(results) >= MAX_URLS * 2:  # collect extra, scoring will filter
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
                if parsed.netloc == domain:
                    results.append({"url": loc, "source": "sitemap"})
                    if len(results) >= MAX_URLS * 2:
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
            results.append({"url": link, "source": "crawl"})
            if len(results) >= MAX_URLS * 2:
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
            elapsed = resp.elapsed.total_seconds() * 1000 if hasattr(resp, 'elapsed') else 0
            results.append({
                "url": url,
                "source": "probe",
                "status_code": resp.status_code,
                "response_ms": elapsed,
                "content_type": resp.headers.get("content-type", ""),
            })

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
    Scan a domain and return discovered endpoints, scored and filtered.

    Returns:
        {
            "domain": str,
            "urls": [{"url", "source", "score", "suggested_name", "suggested_type", "suggested_priority"}, ...],
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
            sitemap_task = _parse_sitemap(client, base_url)
            robots_task = _parse_robots(client, base_url)
            crawl_task = _crawl_homepage(client, base_url)
            probe_task = _probe_common_paths(client, base_url)

            sitemap_results, robots_results, crawl_results, probe_results = await asyncio.gather(
                sitemap_task, robots_task, crawl_task, probe_task,
                return_exceptions=True,
            )

            all_urls: list[dict] = []
            for batch in [sitemap_results, robots_results, crawl_results, probe_results]:
                if isinstance(batch, list):
                    all_urls.extend(batch)

        # Deduplicate by URL (keep first occurrence, which preserves source priority)
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

        # Score every URL and filter
        scored: list[dict] = []
        for item in unique:
            url_score = _score_url(
                item["url"],
                status_code=item.get("status_code", 200),
                response_ms=item.get("response_ms", 0),
                content_type=item.get("content_type", ""),
                source=item.get("source", "crawl"),
            )
            item["score"] = url_score
            item["suggested_name"] = f"{domain} - {_suggest_name(item['url'], domain)}"
            item["suggested_type"] = "http"
            item["suggested_priority"] = "high" if url_score >= 60 else "medium" if url_score >= 30 else "low"

            if url_score >= SCORE_SHOW_THRESHOLD:
                scored.append(item)

        # Sort by score descending
        scored.sort(key=lambda x: -x["score"])

        # Cap at max_urls
        scored = scored[:max_urls]

        # SSL detection (synchronous, run in thread)
        ssl_info = await asyncio.to_thread(_grab_ssl_info, domain)
        result["ssl"] = ssl_info

        # Add SSL as first entry if detected
        if ssl_info:
            scored.insert(0, {
                "url": domain,
                "source": "probe",
                "score": 95,
                "suggested_name": f"SSL - {domain}",
                "suggested_type": "ssl",
                "suggested_priority": "high",
                "ssl_info": ssl_info,
            })

        result["urls"] = scored
        result["total_found"] = len(scored)
        result["sources"] = {
            "sitemap": sum(1 for u in scored if u["source"] == "sitemap"),
            "crawl": sum(1 for u in scored if u["source"] == "crawl"),
            "probe": sum(1 for u in scored if u["source"] == "probe"),
        }

    except httpx.ConnectError:
        result["status"] = f"Could not connect to {domain}. Check the domain and try again."
    except httpx.ConnectTimeout:
        result["status"] = f"Connection to {domain} timed out."
    except Exception as e:
        result["status"] = f"Discovery failed: {str(e)[:100]}"

    return result
