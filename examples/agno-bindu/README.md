# Exposing Lex as a network-addressable Bindu agent

This directory turns [Lex](https://github.com/i-dot-ai/lex) — the UK legal API and
MCP server — into an **agent you can talk to over the network**. It wires Lex's
hosted MCP tools into an [agno](https://github.com/agno-agi/agno) agent and serves
that agent over the [Bindu](https://github.com/GetBindu/Bindu) A2A
(Agent-to-Agent) protocol: a public agent card, a DID identity, and a JSON-RPC
endpoint other agents and apps can call.

> **Community-built example.** Not affiliated with or endorsed by the Lex / i.AI
> maintainers. Lex is open source under its own [MIT LICENSE](../../LICENSE); this
> directory is example glue showing one way to drive it. Lex describes its hosted
> service as experimental and not for production use — treat this example the same
> way.

Contributed by the team at [Bindu](https://github.com/GetBindu/Bindu). Lex provides
the real capability — 8.4M+ UK legal documents with semantic search; this example
is the thin layer that lets an A2A network reach it. Bindu's examples index links
back here so discovery flows both ways.

## Maintenance

The Lex data, API, and MCP tools are maintained by [i.AI](https://github.com/i-dot-ai/lex) —
file tool/data issues there. For issues with *this example* (the Bindu glue, the
prompt, this README), open an issue on [Bindu](https://github.com/GetBindu/Bindu)
and tag it `[lex example]`, or reach the Bindu team on Discord.

## What the example does

You ask a question about UK law. The agno agent decides which Lex MCP tool to call
— search for an Act, look one up by citation, pull its full text, read an
explanatory note, or trace an amendment — calls it against the **hosted** Lex MCP
server, and answers with citations. Because the model only answers from tool
output, the responses are grounded in primary sources rather than the model's
memory.

There is no local Lex stack to run. Lex publishes a hosted MCP server, so the
agent connects straight to it over HTTP — you only need a model key.

It exposes 13 Lex tools, grouped as:

- **Find legislation** — `search_for_legislation_acts`, `search_for_legislation_sections`
- **Read legislation** — `lookup_legislation`, `get_legislation_sections`,
  `get_legislation_full_text`, `proxy_legislation_data`
- **Explanatory notes** — `search_explanatory_note`,
  `get_explanatory_note_by_legislation`, `get_explanatory_note_by_section`
- **Amendments** — `search_amendments`, `search_amendment_sections`
- **Service** — `get_live_stats_api_stats_get`, `health_check_healthcheck_get`

## The libraries it uses

- **[agno](https://github.com/agno-agi/agno)** — the agent loop: model call,
  tool-calling against MCP, and short-term memory.
- **[Bindu](https://github.com/GetBindu/Bindu)** — wraps the agent as an A2A
  service with a DID identity, an agent card, and a JSON-RPC endpoint.

## Setup

All commands use [`uv`](https://docs.astral.sh/uv/) and run from this directory.

```bash
uv venv
uv pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY (https://openrouter.ai/keys)
```

That's the whole setup — the Lex MCP server is remote, so there is nothing else to
install or ingest. The default model is `anthropic/claude-sonnet-4.5`; override it
with `BINDU_AGENT_MODEL` in `.env`.

> **Why `--no-project` below:** Lex is itself a `uv` project, so a bare `uv run`
> would try to sync Lex's full dependency set. Running the example with
> `uv run --no-project` keeps this small env (the `.venv` you just created here)
> separate from Lex's — your Lex setup is untouched.

## Run the CLI (one-shot)

The fastest way to see it work — one question, rich-rendered, then exit:

```bash
uv run --no-project python cli.py "What does the Data Protection Act 2018 say about the rights of data subjects?"
```

The agent searches Lex, retrieves the relevant Act/sections, and answers with a
`Sources` list of the legislation ids it used.

## Run the A2A service (primary)

```bash
uv run --no-project python bindu_agent.py
```

This starts the Bindu agent on `http://localhost:3773` with:

- `GET /.well-known/agent.json` — the agent card; the DID is published under
  `capabilities.extensions[].uri` as `did:bindu:…`
- `GET /.well-known/did.json` — the DID document
- `GET /health` — health payload (`health: healthy`, `task_manager_running: true`,
  and `application.agent_did`)
- `POST /` — JSON-RPC 2.0: `message/send` (returns a task id with `state:
  submitted`) and `tasks/get` (poll until `completed`)

## Try it out

`message/send` is asynchronous: it returns a task id, and you poll `tasks/get` for
the answer. Each call needs **four UUIDs** (the JSON-RPC `id`, plus
`messageId` / `contextId` / `taskId`), and the JSON-RPC `id` is validated as a UUID
— so the snippet generates them. With the service running in another terminal:

```bash
BASE=http://localhost:3773
uuid() { uuidgen | tr 'A-Z' 'a-z'; }
RPC_ID=$(uuid); MSG_ID=$(uuid); CTX_ID=$(uuid); TASK_ID=$(uuid)

# 1) send the question
curl -s -X POST "$BASE" -H 'content-type: application/json' -d "{
  \"jsonrpc\":\"2.0\",\"id\":\"$RPC_ID\",\"method\":\"message/send\",
  \"params\":{
    \"configuration\":{\"acceptedOutputModes\":[\"text/plain\"]},
    \"message\":{
      \"role\":\"user\",\"messageId\":\"$MSG_ID\",
      \"contextId\":\"$CTX_ID\",\"taskId\":\"$TASK_ID\",
      \"kind\":\"message\",
      \"parts\":[{\"kind\":\"text\",\"text\":\"Which Act introduced the UK's right to be forgotten, and which section?\"}]
    }
  }
}" >/dev/null

# 2) poll until the task is done, then print the answer
for i in $(seq 1 45); do
  RESP=$(curl -s -X POST "$BASE" -H 'content-type: application/json' -d "{
    \"jsonrpc\":\"2.0\",\"id\":\"$(uuid)\",\"method\":\"tasks/get\",
    \"params\":{\"taskId\":\"$TASK_ID\"}
  }")
  STATE=$(printf '%s' "$RESP" | jq -r '.result.status.state // "?"')
  echo "  [$i] $STATE"
  case "$STATE" in completed|failed|input-required) break;; esac
  sleep 2
done
printf '%s' "$RESP" | jq -r '.result.artifacts[0].parts[0].text // "(no answer text)"'
```

> **File uploads:** send your text as a `text` part, as above. Don't rely on A2A
> file parts for PDFs/DOCX in this example — extract the text client-side first.

## Network exposure & dependencies

- **Local by default.** The service binds to `localhost` and CORS is limited to a
  local origin. Nothing is published.
- **`BINDU_EXPOSE=true` opens a PUBLIC, UNAUTHENTICATED tunnel** to your agent,
  with your model key on the billing path. Only set it when you intend to share the
  agent, and understand that anyone with the URL can spend your model budget.
- **Opt-in dependencies.** Everything this example needs is in
  `requirements.txt`; it adds nothing to Lex's own dependencies.
- **Upstream service.** Answers come from the hosted Lex MCP server
  (`https://lex.lab.i.ai.gov.uk/mcp`); point `LEX_MCP_URL` at your own instance if
  you run one.
