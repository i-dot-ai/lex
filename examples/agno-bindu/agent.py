"""Lex UK Law Agent — the agent definition (no server started here).

Consumed by cli.py (one-shot) and bindu_agent.py (A2A service, primary entry).

Unlike a stdio MCP example, Lex runs a *hosted* MCP server, so there is nothing
to install or launch locally: we point agno's MCPTools at the remote streamable
HTTP endpoint (the same one Lex's own .mcp.json uses). The tools are attached to
the agent when a connection is opened by the caller.
"""

from __future__ import annotations

import os
from pathlib import Path

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openrouter import OpenRouter
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from prompts import AGENT_DESCRIPTION, AGENT_NAME, SYSTEM_PROMPT

HERE = Path(__file__).parent.resolve()

# Load this example's .env deterministically, regardless of the current working
# directory (so cli.py / bindu_agent.py started from the repo root still pick it
# up). This must run before the model is built at import time below.
load_dotenv(HERE / ".env")

DB_PATH = HERE / "tmp" / "lex.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# The hosted Lex MCP server. Override via env only if you run your own instance.
LEX_MCP_URL = os.getenv("LEX_MCP_URL", "https://lex.lab.i.ai.gov.uk/mcp")
# Legal search over millions of documents can be slow; give it room.
MCP_TIMEOUT_SECONDS = int(os.getenv("LEX_MCP_TIMEOUT_SECONDS", "60"))


def make_mcp_tools() -> MCPTools:
    """A fresh MCPTools bound to the hosted Lex MCP server.

    Returns a new instance each call on purpose: an MCP session is tied to the
    asyncio loop/task that opened it, so cli.py and bindu_agent.py each open their
    own (see bindu_agent.py for how the A2A path keeps one warm).
    """
    return MCPTools(
        url=LEX_MCP_URL,
        transport="streamable-http",
        timeout_seconds=MCP_TIMEOUT_SECONDS,
    )


def _build_model() -> OpenRouter:
    model_id = os.getenv("BINDU_AGENT_MODEL", "anthropic/claude-sonnet-4.5")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to your .env (see .env.example).")
    return OpenRouter(
        id=model_id,
        api_key=api_key,
        max_tokens=int(os.getenv("BINDU_AGENT_MAX_TOKENS", "4096")),
    )


def build_agent() -> Agent:
    """Create the agent. Tools are attached when an MCP connection opens."""
    return Agent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        instructions=SYSTEM_PROMPT,
        model=_build_model(),
        db=SqliteDb(db_file=str(DB_PATH)),
        add_history_to_context=True,
        num_history_runs=3,
        add_datetime_to_context=True,
        markdown=True,
    )


agent: Agent = build_agent()  # module-level so cli.py and bindu_agent.py can import
