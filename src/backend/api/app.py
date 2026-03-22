"""FastAPI application creation and configuration."""

import logging
from importlib.metadata import PackageNotFoundError, version as pkg_version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.amendment.router import router as amendment_router
from backend.core.middleware import monitoring_and_rate_limit_middleware
from backend.core.telemetry import instrument_fastapi_app
from backend.explanatory_note.router import router as explanatory_note_router
from backend.legislation.router import router as legislation_router
from backend.mcp_server.server import create_mcp_server
from backend.monitoring import monitoring
from backend.stats.router import router as stats_router
from backend.templates.router import router as template_router

try:
    _VERSION = pkg_version("uk-lex")
except PackageNotFoundError:
    _VERSION = "0.0.0-dev"


def create_base_app():
    """Create the base FastAPI app with routes and middleware."""
    base_app = FastAPI(
        title="Lex API",
        description="API for accessing Lex's legislation search capabilities",
        version=_VERSION,
        redirect_slashes=False,
    )

    # Add monitoring and rate limiting middleware
    base_app.middleware("http")(monitoring_and_rate_limit_middleware)

    # Note: CORS is configured on the outer app in create_app() only.
    # Adding CORSMiddleware here AND on the outer app causes layering
    # conflicts with OPTIONS preflight requests and MCP .well-known routes.

    # Instrument FastAPI with OpenTelemetry
    monitoring.instrument_fastapi(base_app)

    # Include routers
    base_app.include_router(template_router)  # Include template router first for root path
    base_app.include_router(legislation_router)
    base_app.include_router(explanatory_note_router)
    base_app.include_router(amendment_router)
    base_app.include_router(stats_router)

    # Health check endpoint
    @base_app.get("/healthcheck")
    async def health_check():
        """Health check with Qdrant connection verification."""
        try:
            import asyncio

            from lex.core.qdrant_client import async_qdrant_client

            # Test Qdrant connection
            collections = await async_qdrant_client.get_collections()

            # Fetch all collection details concurrently
            async def _get_info(name: str):
                info = await async_qdrant_client.get_collection(name)
                return name, {
                    "points": info.points_count,
                    "status": info.status.value
                    if hasattr(info.status, "value")
                    else str(info.status),
                }

            results = await asyncio.gather(
                *[_get_info(coll.name) for coll in collections.collections]
            )
            collection_info = dict(results)

            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "database": "qdrant",
                    "collections": len(collections.collections),
                    "collection_details": collection_info,
                },
            )
        except Exception as e:
            return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})

    return base_app


def create_app():
    """Create the complete application with MCP support and static files."""
    base_app = create_base_app()
    mcp = create_mcp_server(base_app)
    mcp_app = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)

    # Combined routes pattern: MCP routes first so /mcp is matched before
    # any catch-all. Lifespan from mcp_app is required for session management.
    app = FastAPI(
        title="Lex API",
        description="UK Legal API for AI agents with MCP support",
        version=_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        routes=[
            *mcp_app.routes,
            *base_app.routes,
        ],
        lifespan=mcp_app.lifespan,
        redirect_slashes=False,
    )

    # Single CORS middleware on the outer app only.
    # FastMCP docs warn: "layering CORS middleware can cause conflicts
    # (such as 404 errors on .well-known routes or OPTIONS requests)."
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "MCP-Protocol-Version",
            "mcp-session-id",
        ],
        # Required: without this, browsers receive mcp-session-id but
        # JavaScript cannot access it, breaking session management.
        expose_headers=["mcp-session-id"],
    )

    # Serve static files at /static, NOT at root "/".
    # StaticFiles mounted at "/" acts as a catch-all and returns 405 Method
    # Not Allowed for any non-GET request, which breaks POST /mcp.
    try:
        app.mount(
            "/static", StaticFiles(directory="./src/backend/static", html=True), name="static"
        )
        logging.info("Serving static files from src/backend/static at /static")
    except Exception as e:
        logging.warning(f"Could not mount static files: {e}")

        # Fallback: create a simple root endpoint
        @app.get("/")
        async def root(request):
            monitoring.track_page_view(request, "home_fallback")
            return {
                "message": "Lex API",
                "description": "UK Legal API for AI agents",
                "version": _VERSION,
                "endpoints": {
                    "api_docs": "/api/docs",
                    "mcp_server": "/mcp",
                    "health_check": "/healthcheck",
                },
            }

    # Instrument FastAPI apps for Azure Monitor telemetry
    instrument_fastapi_app(app)

    return app
