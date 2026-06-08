"""Lex UK Law Agent exposed as a Bindu A2A agent.

agno's MCPTools is async and its session is bound to the task that opened it, but
Bindu calls the handler synchronously per request. So we run one asyncio loop in a
daemon thread, open the MCP connection to the hosted Lex server **once** at boot,
and marshal each handler call onto that loop. One warm connection serves every
request instead of reconnecting each time.

Run:  uv run --no-project python bindu_agent.py
"""

from __future__ import annotations

import asyncio
import atexit
import os
import threading
from pathlib import Path

from agent import agent, make_mcp_tools
from bindu.penguin.bindufy import bindufy
from dotenv import load_dotenv
from prompts import AGENT_DESCRIPTION

# agent.py already loads this example's .env when imported above; load it again
# here (harmless) so the BINDU_* config below resolves no matter the entry point.
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

_loop = asyncio.new_event_loop()
_mcp_tools = None
_ready = threading.Event()


def _run_loop() -> None:
    asyncio.set_event_loop(_loop)
    _loop.run_forever()


threading.Thread(target=_run_loop, name="lex-mcp-loop", daemon=True).start()


async def _open_mcp() -> None:
    global _mcp_tools
    _mcp_tools = make_mcp_tools()
    await _mcp_tools.connect()
    agent.tools = [_mcp_tools]


asyncio.run_coroutine_threadsafe(_open_mcp(), _loop).result()
_ready.set()


def _shutdown() -> None:
    if not _loop.is_running():
        return
    try:
        if _mcp_tools is not None:
            asyncio.run_coroutine_threadsafe(_mcp_tools.close(), _loop).result(timeout=5)
    except Exception:
        pass
    _loop.call_soon_threadsafe(_loop.stop)


atexit.register(_shutdown)


async def _arun(content: str) -> str:
    result = await agent.arun(content)
    return result.content if hasattr(result, "content") else str(result)


def handler(messages):
    """Sync Bindu handler; hops the prompt onto the background loop. See gotchas.md.

    Bindu normalizes the inbound A2A message to OpenAI-style
    [{"role": "user"|"assistant", "content": "..."}] before calling us.
    """
    user_content = " ".join(
        (m.get("content") or "") for m in (messages or []) if m.get("role") == "user"
    ).strip()
    if not user_content:
        return "Send me a question about UK legislation and I'll look it up in Lex."
    _ready.wait(timeout=30)
    return asyncio.run_coroutine_threadsafe(_arun(user_content), _loop).result()


config = {
    "author": os.getenv("BINDU_AGENT_AUTHOR", "you@example.com"),
    "name": os.getenv("BINDU_AGENT_NAME", "bindu-lex"),
    "description": AGENT_DESCRIPTION,
    "deployment": {
        "url": os.getenv("BINDU_AGENT_URL", "http://localhost:3773"),
        "expose": os.getenv("BINDU_EXPOSE", "false").lower() == "true",  # see README
        "cors_origins": ["http://localhost:5173"],
    },
    "capabilities": {"streaming": False},
}


if __name__ == "__main__":
    bindufy(config, handler)
