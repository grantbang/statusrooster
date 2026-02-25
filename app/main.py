from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import auth, monitors, cron
import os

app = FastAPI(title="StatusRooster", version="0.1.0")

# Routers
app.include_router(auth.router)
app.include_router(monitors.router)
app.include_router(cron.router)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "statusrooster"}
