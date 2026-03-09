"""MCP server creation."""

from fastmcp import FastMCP


def create_mcp_server(base_app):
    """Create MCP server from FastAPI app."""
    mcp = FastMCP.from_fastapi(app=base_app, name="Lex API")
    return mcp
