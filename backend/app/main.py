"""
Conversational BI / Data Agent (NLQ -> SQL)
FastAPI Application Entry Point.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.app.core.config import settings
from backend.app.api.routes import router as api_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Conversational Data Agent translating natural language (Indonesian/English) into safe, validated SQL.",
    version="1.0.0"
)

# Enable CORS for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
