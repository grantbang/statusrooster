from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import auth, monitors, cron, pages, billing, api_v1
from datetime import datetime
import json
import os

app = FastAPI(title="StatusRooster", version="0.1.0")

# Routers — pages first so / doesn't conflict
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(monitors.router)
app.include_router(billing.router)
app.include_router(api_v1.router)
app.include_router(cron.router)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# Custom JSON serializer for Firestore timestamps
class FirestoreEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '_seconds'):  # Firestore DatetimeWithNanoseconds
            return datetime.fromtimestamp(obj._seconds).isoformat()
        return super().default(obj)


def tojson_filter(value):
    return json.dumps(value, cls=FirestoreEncoder)


templates.env.filters["tojson"] = tojson_filter

# Also register filter in the pages router templates
from app.routers.pages import templates as page_templates
page_templates.env.filters["tojson"] = tojson_filter


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "statusrooster"}
