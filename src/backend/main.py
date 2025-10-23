import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP

from backend.amendment.router import router as amendment_router
from backend.caselaw.router import router as caselaw_router
from backend.explanatory_note.router import router as explanatory_note_router
from backend.legislation.router import router as legislation_router

# Configure logging to show all INFO level logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Ensure lex.core.embeddings logger shows INFO logs
logging.getLogger("lex.core.embeddings").setLevel(logging.INFO)

app = FastAPI(
    title="Lex API",
    description="API for accessing Lex's legislation and caselaw search capabilities",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(legislation_router)
app.include_router(caselaw_router)
app.include_router(explanatory_note_router)
app.include_router(amendment_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/healthcheck")
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


mcp = FastApiMCP(app)
mcp.mount_http()  # Streamable HTTP transport (v0.4.0+ recommended)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
