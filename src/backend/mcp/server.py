"""MCP server creation and middleware."""

import os

from fastmcp import FastMCP

from backend.monitoring import monitoring


def create_mcp_server(base_app):
    """Create MCP server from FastAPI app with monitoring."""
    # Enable new OpenAPI parser for better schema handling
    os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

    # Create MCP server from FastAPI app
    mcp = FastMCP.from_fastapi(app=base_app, name="Lex API")

    # Return the MCP server for combined routes pattern
    return mcp


class MCPMiddleware:
    """MCP protocol monitoring middleware."""

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
