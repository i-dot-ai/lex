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
    # Auto-detect base URL from request, respecting X-Forwarded-Proto for SSL termination
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    base_url = f"{scheme}://{host}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "posthog_key": POSTHOG_KEY,
            "posthog_host": POSTHOG_HOST,
            "base_url": base_url,
        },
    )
