"""
main.py — FastAPI Application Entry Point for AgroIntel AI
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import endpoints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AgroIntel AI",
    description="Multi-model agricultural price prediction API with Black Swan event modeling.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
logger.info("Frontend dir: %s (exists=%s)", FRONTEND_DIR, FRONTEND_DIR.exists())

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "AgroIntel AI", "version": "2.0.0"}

# ── Include API routes BEFORE mounting StaticFiles ──
app.include_router(endpoints.router, prefix="/api")

# ── Serve frontend (Must be at the bottom to avoid catching /api requests) ──
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def serve_frontend_fallback():
        return HTMLResponse("<h1>Frontend not found. Go to /docs</h1>", status_code=404)



logger.info("AgroIntel AI starting...")
