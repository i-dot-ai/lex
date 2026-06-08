"""One-shot CLI for the Lex UK Law Agent.

    uv run --no-project python cli.py "What does the Data Protection Act 2018 cover?"

Opens its own MCP connection for a single question and exits — no background loop
needed here (that lives in bindu_agent.py for the long-running A2A service).
"""

from __future__ import annotations

import asyncio
import sys

from agent import agent, make_mcp_tools  # importing agent loads this example's .env
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

console = Console()
err = Console(stderr=True)


async def ask(question: str) -> str:
    async with make_mcp_tools() as mcp_tools:
        agent.tools = [mcp_tools]
        result = await agent.arun(question)
        return result.content if hasattr(result, "content") else str(result)


def main() -> int:
    if len(sys.argv) < 2:
        err.print('[bold red]Error:[/bold red] pass a question, e.g. cli.py "..."')
        return 2
    question = " ".join(sys.argv[1:])
    console.print(Panel.fit(question, title="Question", border_style="cyan"))
    try:
        with err.status("[bold cyan]Researching UK law…[/bold cyan]", spinner="dots"):
            answer = asyncio.run(ask(question))
    except Exception as exc:
        err.print(f"[bold red]Error:[/bold red] {exc}")
        return 1
    console.print(Rule(style="dim"))
    console.print(Markdown(answer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
