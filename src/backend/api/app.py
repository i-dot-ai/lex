"""FastAPI application creation and configuration."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles

from backend.amendment.router import router as amendment_router
from backend.caselaw.router import router as caselaw_router
from backend.explanatory_note.router import router as explanatory_note_router
from backend.legislation.router import router as legislation_router
from backend.core.middleware import monitoring_and_rate_limit_middleware
from backend.core.telemetry import instrument_fastapi_app
from backend.monitoring import monitoring
from backend.mcp.server import create_mcp_server


def create_base_app():
    """Create the base FastAPI app with routes and middleware."""
    base_app = FastAPI(
        title="Lex API",
        description="API for accessing Lex's legislation and caselaw search capabilities",
        version="0.1.0",
        redirect_slashes=False,
    )

    # Add monitoring and rate limiting middleware
    base_app.middleware("http")(monitoring_and_rate_limit_middleware)

    # Configure CORS
    base_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for public API
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*", "MCP-Protocol-Version", "mcp-session-id"],
    )

    # Instrument FastAPI with OpenTelemetry
    monitoring.instrument_fastapi(base_app)

    # Include routers
    base_app.include_router(legislation_router)
    base_app.include_router(caselaw_router)
    base_app.include_router(explanatory_note_router)
    base_app.include_router(amendment_router)

    # Health check endpoint
    @base_app.get("/healthcheck")
    async def health_check():
        """Health check with Qdrant connection verification."""
        try:
            from lex.core.qdrant_client import qdrant_client

            # Test Qdrant connection
            collections = qdrant_client.get_collections()
            collection_info = {}

            for coll in collections.collections:
                info = qdrant_client.get_collection(coll.name)
                collection_info[coll.name] = {
                    "points": info.points_count,
                    "status": info.status.value if hasattr(info.status, "value") else str(info.status),
                }

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
    # Create base app
    base_app = create_base_app()
    
    # Create MCP server
    mcp = create_mcp_server(base_app)
    
    # Create MCP ASGI app with proper path
    mcp_app = mcp.http_app(path='/mcp')
    
    # Use FastMCP's combined routes pattern from docs
    app = FastAPI(
        title="Lex API",
        description="UK Legal API for AI agents with MCP support",
        version="2.0.0",
        docs_url="/api/docs",  # Move API docs to /api/docs
        redoc_url="/api/redoc",  # Move ReDoc to /api/redoc
        openapi_url="/api/openapi.json",  # Move OpenAPI spec
        routes=[
            *mcp_app.routes,      # MCP routes
            *base_app.routes,     # Original API routes
        ],
        lifespan=mcp_app.lifespan,
    )

    # Serve static files at root (this should be last)
    try:
        app.mount("/", StaticFiles(directory="./src/backend/static", html=True), name="static")
        logging.info("Serving static files from src/backend/static at root path")
    except Exception as e:
        logging.warning(f"Could not mount static files: {e}")
        
        # Fallback: create a simple root endpoint
        @app.get("/")
        async def root(request):
            monitoring.track_page_view(request, "home_fallback")
            return {
                "message": "Lex API",
                "description": "UK Legal API for AI agents",
                "version": "2.0.0",
                "endpoints": {
                    "api_docs": "/api/docs",
                    "mcp_server": "/mcp",
                    "health_check": "/healthcheck"
                }
            }

    # Instrument FastAPI apps for Azure Monitor telemetry
    instrument_fastapi_app(app)
    
    return app