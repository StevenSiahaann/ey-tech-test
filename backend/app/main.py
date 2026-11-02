"""
Conversational BI / Data Agent (NLQ -> SQL)
FastAPI Application Entry Point.
"""

import os
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.app.core.config import settings
from backend.app.core.logger import setup_logging, get_logger, set_log_context
from backend.app.api.routes import router as api_router

setup_logging()
logger = get_logger("main")

app = FastAPI(
    title=settings.APP_NAME,
    description="Conversational Data Agent translating natural language (Indonesian/English) into safe, validated SQL.",
    version="1.0.0"
)


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
    set_log_context(request_id=req_id, step_name="http_request")
    t0 = time.time()
    response = await call_next(request)
    dur_ms = round((time.time() - t0) * 1000, 1)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api"):
        logger.info(f"HTTP {request.method} {request.url.path} -> {response.status_code} ({dur_ms}ms)")
    return response


# PoC Best-Practice CORS Policy: explicit origin allowlist, no wildcard credentials reflection
_allowed_origins = settings.get_cors_origins()
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

app.include_router(api_router)

# Resolve Frontend SPA distribution path
frontend_dist = os.path.join(os.getcwd(), "frontend", "dist")
if not os.path.exists(frontend_dist):
    frontend_dist = "/app/frontend/dist"

if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api"):
            return {"error": "API route not found"}
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "online", "message": "Conversational BI API Active"}
else:
    @app.get("/")
    def root():
        return {
            "app": settings.APP_NAME,
            "status": "online",
            "docs_url": "/docs",
            "health_check": "/api/health"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
