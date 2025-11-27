"""Template rendering router for dynamic HTML with environment-injected configuration."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from lex.settings import POSTHOG_HOST, POSTHOG_KEY

router = APIRouter()
templates = Jinja2Templates(directory="src/backend/templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_homepage(request: Request):
    """Serve the homepage with PostHog configuration and base URL injected from request."""
    # Auto-detect base URL from request for dynamic MCP endpoint display
    base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "posthog_key": POSTHOG_KEY,
            "posthog_host": POSTHOG_HOST,
            "base_url": base_url,
        },
    )
