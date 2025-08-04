import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP

from backend.amendment.router import router as amendment_router
from backend.caselaw.router import router as caselaw_router
from backend.explanatory_note.router import router as explanatory_note_router
from backend.legislation.router import router as legislation_router

app = FastAPI(
    title="Lex API",
    description="API for accessing Lex's legislation and caselaw search capabilities",
    version="0.1.0",
)

# Include routers with API key protection
app.include_router(legislation_router)
app.include_router(caselaw_router)
app.include_router(explanatory_note_router)
app.include_router(amendment_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/healthcheck")
async def health_check():
    return JSONResponse(status_code=200, content={"status": "ok"})


mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
