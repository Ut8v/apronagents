"""FastAPI application: serves the built dashboard and mounts the API."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apron.server.routes import ServerContext, build_router
from apron.server.websocket import register_websocket

DASHBOARD_DIST = Path(__file__).parents[2] / "dashboard" / "dist"

# The Vite dev server, for dashboard development against a live backend.
_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def build_app(ctx: ServerContext) -> FastAPI:
    app = FastAPI(title="Apron Agents", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router(ctx), prefix="/api")
    register_websocket(app, ctx)
    if DASHBOARD_DIST.is_dir():
        app.mount("/", StaticFiles(directory=DASHBOARD_DIST, html=True))
    return app


async def serve(ctx: ServerContext) -> None:
    """Run the server until cancelled (used by the launcher)."""
    config = uvicorn.Config(
        build_app(ctx),
        host=ctx.settings.host,
        port=ctx.settings.port,
        log_level="warning",
    )
    await uvicorn.Server(config).serve()
