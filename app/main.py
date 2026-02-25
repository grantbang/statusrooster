from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import auth
import os

app = FastAPI(title="StatusRooster", version="0.1.0")

# Routers
app.include_router(auth.router)

# Static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "statusrooster"}
