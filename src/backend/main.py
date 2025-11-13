import logging
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Configure Azure Monitor OpenTelemetry FIRST - before any FastAPI imports
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor()
    print("✅ Azure Monitor OpenTelemetry configured")

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
import redis
import json

from backend.amendment.router import router as amendment_router
from backend.caselaw.router import router as caselaw_router
from backend.explanatory_note.router import router as explanatory_note_router
from backend.legislation.router import router as legislation_router

from backend.monitoring import monitoring

# Add explicit FastAPI instrumentation for Azure Monitor
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure logging to show all INFO level logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Ensure lex.core.embeddings logger shows INFO logs
logging.getLogger("lex.core.embeddings").setLevel(logging.INFO)

# Smart cache that works with Redis or in-memory fallback
class SmartCache:
    def __init__(self):
        self.redis_client = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.use_redis = False
        
        # Try to connect to Redis
        redis_url = os.getenv("REDIS_URL")
        redis_password = os.getenv("REDIS_PASSWORD")
        
        if redis_url:
            try:
                # Create Redis client with password if provided
                if redis_password:
                    self.redis_client = redis.from_url(
                        redis_url, 
                        password=redis_password,
                        decode_responses=True
                    )
                else:
                    self.redis_client = redis.from_url(redis_url, decode_responses=True)
                
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                logging.info("Connected to Redis for caching and rate limiting")
            except Exception as e:
                logging.warning(f"Failed to connect to Redis, using in-memory cache: {e}")
        else:
            logging.info("No Redis URL configured, using in-memory cache")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.use_redis:
            try:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            except Exception as e:
                logging.error(f"Redis get error: {e}")
                return None
        else:
            # Check memory cache with TTL
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if datetime.now() < entry["expires"]:
                    return entry["value"]
                else:
                    del self.memory_cache[key]
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL."""
        if self.use_redis:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return True
            except Exception as e:
                logging.error(f"Redis set error: {e}")
                return False
        else:
            # Store in memory with expiration
            self.memory_cache[key] = {
                "value": value,
                "expires": datetime.now() + timedelta(seconds=ttl)
            }
            # Simple cleanup: remove expired entries occasionally
            if len(self.memory_cache) > 1000:
                now = datetime.now()
                expired_keys = [
                    k for k, v in self.memory_cache.items() 
                    if now >= v["expires"]
                ]
                for k in expired_keys:
                    del self.memory_cache[k]
            return True
    
    def increment_with_ttl(self, key: str, ttl: int = 60) -> int:
        """Increment counter with TTL for rate limiting."""
        if self.use_redis:
            try:
                # Use Redis pipeline for atomic increment with TTL
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, ttl)
                result = pipe.execute()
                return result[0]  # Return the incremented value
            except Exception as e:
                logging.error(f"Redis increment error: {e}")
                return 0
        else:
            # In-memory rate limiting
            now = datetime.now()
            if key not in self.memory_cache:
                self.memory_cache[key] = {
                    "value": 1,
                    "expires": now + timedelta(seconds=ttl)
                }
                return 1
            else:
                entry = self.memory_cache[key]
                if now < entry["expires"]:
                    entry["value"] += 1
                    return entry["value"]
                else:
                    # Reset expired counter
                    self.memory_cache[key] = {
                        "value": 1,
                        "expires": now + timedelta(seconds=ttl)
                    }
                    return 1

# Global cache instance
cache = SmartCache()

# Rate limiting configuration
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))

# Helper functions for middleware
def get_client_ip(request: Request) -> str:
    """Extract client IP considering proxy headers."""
    # Check X-Forwarded-For header first (Azure Container Apps)
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Fallback to X-Real-IP
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    
    # Last resort: direct connection IP
    return getattr(request.client, "host", "unknown")

def add_rate_limit_headers(response, minute_count: int, hour_count: int) -> None:
    """Add rate limiting headers to response."""
    response.headers["X-RateLimit-Limit-Minute"] = str(RATE_LIMIT_PER_MINUTE)
    response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, RATE_LIMIT_PER_MINUTE - minute_count))
    response.headers["X-RateLimit-Limit-Hour"] = str(RATE_LIMIT_PER_HOUR)
    response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, RATE_LIMIT_PER_HOUR - hour_count))

def track_request_safely(request: Request, response, duration: float, minute_count: int, hour_count: int) -> None:
    """Track request with safe error handling for monitoring."""
    try:
        # Track rate limiting events if approaching limits
        if minute_count > RATE_LIMIT_PER_MINUTE * 0.8:  # 80% threshold
            monitoring.track_rate_limit_event(
                request, "minute", minute_count, RATE_LIMIT_PER_MINUTE, 
                exceeded=(minute_count > RATE_LIMIT_PER_MINUTE)
            )
        
        if hour_count > RATE_LIMIT_PER_HOUR * 0.8:  # 80% threshold
            monitoring.track_rate_limit_event(
                request, "hour", hour_count, RATE_LIMIT_PER_HOUR,
                exceeded=(hour_count > RATE_LIMIT_PER_HOUR)
            )
        
        # Track monitoring events based on path
        if request.url.path == "/":
            monitoring.track_page_view(request, "home")
        elif request.url.path == "/api/docs":
            monitoring.track_page_view(request, "api_docs")
        elif request.url.path == "/api/redoc":
            monitoring.track_page_view(request, "redoc")
        elif request.url.path not in ["/", "/api/docs", "/api/redoc", "/api/openapi.json"]:
            query_params = dict(request.query_params) if request.query_params else None
            monitoring.track_api_usage(
                request, request.url.path, duration, response.status_code, query_params
            )
    except Exception as e:
        # If monitoring fails, don't break the request - just log
        print(f"Monitoring error (non-critical): {e}")

# First create the base FastAPI app with routes
base_app = FastAPI(
    title="Lex API",
    description="API for accessing Lex's legislation and caselaw search capabilities",
    version="0.1.0",
    redirect_slashes=False,
)

# Enhanced monitoring and rate limiting middleware
@base_app.middleware("http")
async def monitoring_and_rate_limit_middleware(request: Request, call_next):
    """Combined monitoring and rate limiting middleware with proper exception handling."""
    start_time = time.time()
    minute_count = 0
    hour_count = 0
    
    try:
        # Skip rate limiting for health checks
        if request.url.path in ["/healthcheck", "/health"]:
            response = await call_next(request)
            return response
        
        # Get client IP and check rate limits
        client_ip = get_client_ip(request)
        minute_key = f"rate_limit:minute:{client_ip}"
        hour_key = f"rate_limit:hour:{client_ip}"
        
        minute_count = cache.increment_with_ttl(minute_key, 60)
        hour_count = cache.increment_with_ttl(hour_key, 3600)
        
        # Check limits and return early with proper headers
        if minute_count > RATE_LIMIT_PER_MINUTE or hour_count > RATE_LIMIT_PER_HOUR:
            limit_type = "minute" if minute_count > RATE_LIMIT_PER_MINUTE else "hour"
            limit_value = RATE_LIMIT_PER_MINUTE if minute_count > RATE_LIMIT_PER_MINUTE else RATE_LIMIT_PER_HOUR
            
            # Create 429 response with headers
            from fastapi import Response
            response = Response(
                content=f"Rate limit exceeded: {limit_value} requests per {limit_type}",
                status_code=429,
                media_type="text/plain"
            )
            add_rate_limit_headers(response, minute_count, hour_count)
            return response
        
        # Process the request
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Add monitoring and headers safely
        track_request_safely(request, response, duration, minute_count, hour_count)
        add_rate_limit_headers(response, minute_count, hour_count)
        
        return response
        
    except HTTPException:
        # Let HTTPExceptions (like 429) pass through unchanged
        raise
        
    except Exception as e:
        # Only catch unexpected errors, not HTTP responses
        try:
            monitoring.track_error(request, e, request.url.path)
        except Exception:
            # If monitoring fails, don't break the original error
            pass
        raise

# Configure CORS
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for public API
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Instrument FastAPI with OpenTelemetry
monitoring.instrument_fastapi(base_app)

# Include routers
base_app.include_router(legislation_router)
base_app.include_router(caselaw_router)
base_app.include_router(explanatory_note_router)
base_app.include_router(amendment_router)


# Removed GET / route to allow static files to handle root path
# The static files mount will now handle the root URL


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


# Enable new OpenAPI parser for better schema handling
import os
os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

# Create MCP server from FastAPI app
mcp = FastMCP.from_fastapi(app=base_app, name="Lex Research API")

# MCP lifecycle tracking via FastAPI events
@base_app.on_event("startup")
async def track_mcp_startup():
    """Track MCP server startup."""
    monitoring.track_mcp_event("server_startup")

@base_app.on_event("shutdown")
async def track_mcp_shutdown():
    """Track MCP server shutdown."""
    monitoring.track_mcp_event("server_shutdown")

# Create the MCP ASGI app using streamable HTTP for better compatibility
mcp_app = mcp.streamable_http_app(path='/mcp')

# Create combined app with both API and MCP routes
app = FastAPI(
    title="Lex API",
    description="UK Legal Research API for AI agents with MCP support",
    version="2.0.0",
    docs_url="/api/docs",  # Move API docs to /api/docs
    redoc_url="/api/redoc",  # Move ReDoc to /api/redoc
    openapi_url="/api/openapi.json",  # Move OpenAPI spec
)

# Add all middleware from base_app to main app
for middleware in base_app.user_middleware:
    # Handle different FastAPI middleware structure
    if hasattr(middleware, 'cls') and hasattr(middleware, 'args') and hasattr(middleware, 'kwargs'):
        app.add_middleware(middleware.cls, **middleware.kwargs)
    elif hasattr(middleware, 'cls'):
        app.add_middleware(middleware.cls)

# Include all API routes except the root path (/) to allow static files
for route in base_app.routes:
    # Skip the root path route to let static files handle it
    if hasattr(route, 'path') and route.path == "/":
        continue
    app.router.routes.append(route)

# MCP protocol monitoring middleware
class MCPMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            body = await self._get_request_body(receive)
            request = monitoring.parse_mcp_request(body)
            
            client_info = {"name": "mcp_client", "version": "unknown"}
            if "params" in request and "clientInfo" in request["params"]:
                client_info.update(request["params"]["clientInfo"])
            
            method = request.get("method", "unknown")
            monitoring.track_mcp_event(method, client_info)
            
            async def new_receive():
                return {"type": "http.request", "body": body, "more_body": False}
            
            await self.app(scope, new_receive, send)
        else:
            await self.app(scope, receive, send)
    
    async def _get_request_body(self, receive) -> bytes:
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
            else:
                break
        return body

# Mount MCP server at /mcp with monitoring middleware
app.mount("/mcp", MCPMiddleware(mcp_app), name="mcp")

# Serve static files at root (this should be last)
try:
    app.mount("/", StaticFiles(directory="./src/backend/static", html=True), name="static")
    logging.info("Serving static files from src/backend/static at root path")
except Exception as e:
    logging.warning(f"Could not mount static files: {e}")
    
    # Fallback: create a simple root endpoint
    @app.get("/")
    async def root(request: Request):
        monitoring.track_page_view(request, "home_fallback")
        return {
            "message": "Lex Research API",
            "description": "UK Legal Research API for AI agents",
            "version": "2.0.0",
            "endpoints": {
                "api_docs": "/api/docs",
                "mcp_server": "/mcp",
                "health_check": "/healthcheck"
            }
        }

# Instrument FastAPI apps for Azure Monitor telemetry
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    try:
        FastAPIInstrumentor.instrument_app(app)
        print("✅ FastAPI app instrumented for Azure Monitor")
    except Exception as e:
        print(f"⚠️ FastAPI instrumentation failed: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        lifespan=mcp_app.lifespan
    )
