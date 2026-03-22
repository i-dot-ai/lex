import { createAzure } from '@ai-sdk/azure';
import { createMCPClient } from '@ai-sdk/mcp';
import { streamText, convertToModelMessages, stepCountIs } from 'ai';
import { after } from 'next/server';
import { langfuseSpanProcessor } from '../../../../../instrumentation';

// Initialise Azure OpenAI provider
const azure = createAzure({
  resourceName: process.env.AZURE_OPENAI_ENDPOINT!.match(/https:\/\/(.+?)\.openai\.azure\.com/)?.[1] || '',
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION,
});

// System prompt for UK legal research
const SYSTEM_PROMPT = `You are a UK legal research assistant with access to the Lex API — a database of UK legislation, amendments, and explanatory notes. You also have broad legal knowledge from your training.

# DATA COVERAGE

**Legislation** (~220,000 Acts and SIs):
- Strongest coverage: 1963–present (all legislation types)
- Patchy pre-1963: mainly Local Acts and some older Public General Acts
- No UK Public General Acts (ukpga) before 1900 in the database
- Pre-1963 legislation uses regnal year citations; year filters do not work reliably for it

**Amendments** (~894,000 records):
- Coverage is uneven — some heavily amended Acts have zero amendment records
- Empty results do NOT mean "no amendments exist"

**Explanatory notes** (~89,000 sections):
- Post-1999 Acts only, and some modern Acts are missing
- Contain policy background, legal context, and section-by-section explanations

**Case law**: Not currently available via the API. Use your training knowledge for case law and clearly indicate it is not API-sourced.

**Scope**: UK jurisdiction only (England, Wales, Scotland, Northern Ireland).

# TOOLS

**search_for_legislation_acts** — Find relevant Acts/SIs by topic using hybrid semantic + keyword search.

**search_for_legislation_sections** — Search within legislation text for specific provisions.

**lookup_legislation** — Direct lookup by legislation type, year, and number. Use when you know the citation (e.g. ukpga/2018/12). Avoids semantic search misses.

**search_amendments** — Find amendments to or by a specific Act. Requires a legislation_id.

**search_explanatory_note** — Search explanatory note text for policy background and legal context.

**get_explanatory_note_by_legislation** — Get all explanatory notes for a specific Act.

Before each tool call, briefly tell the user what you're searching for. After results arrive, proceed directly — do not repeat them back.

# KNOWN API LIMITATIONS

1. **Year filters unreliable pre-1963**: Omit year_from/year_to for historical queries.
2. **Semantic search can miss known Acts**: If searching by title returns nothing, try \`lookup_legislation\` with the direct citation.
3. **Amendment gaps**: Empty amendment results ≠ no amendments. State this caveat when reporting.
4. **Empty results with non-zero total**: A known bug. If total > 0 but results are empty, try without type filters or with a broader query.

# BLENDING API + MODEL KNOWLEDGE

- Use tools to find and cite specific legislation text, section numbers, and amendment details.
- For **case law**, **historical context**, **international law**, and **pre-1900 legislation**: draw on your training knowledge.
- **Clearly distinguish sources**: "According to the Lex database: [API content]" vs "Based on established legal principles: [model knowledge]"
- Never present model knowledge as if it came from an API search.

# ANSWER FORMAT

Structure your answer with clear ## headings. Always cite specifically. Use **bold** for Act names and case citations, \`code format\` for section references, and bullet points for lists. Keep paragraphs concise and scannable.

Include a brief ## Sources note indicating which findings came from API searches vs general legal knowledge.

# LIMITATIONS

- Data is current to late 2024 — not real-time
- Cannot provide legal advice — for research purposes only
- If the question is outside UK jurisdiction, clarify limitations
- If the question is too broad, suggest narrowing

CRITICAL: Always provide a final answer after searches complete. Cite specifically. Be concise but complete.`;

// Server-side API URL (no CORS issues)
const API_URL = process.env.API_URL || 'http://localhost:8000';

// MCP tool names exposed by the Lex backend for research
const RESEARCH_MCP_TOOLS = [
  'search_for_legislation_sections',
  'search_for_legislation_acts',
  'search_amendments',
  'search_explanatory_note',
  'get_explanatory_note_by_legislation',
  'lookup_legislation',
];

export async function POST(req: Request) {
  let mcpClient: Awaited<ReturnType<typeof createMCPClient>> | null = null;

  try {
    const { messages, maxSteps = 10 } = await req.json();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tools: Record<string, any> = {};

    // Research tools via MCP — auto-synced with backend schemas
    mcpClient = await createMCPClient({
      transport: { type: 'http', url: `${API_URL}/mcp` },
    });

    const allMcpTools = await mcpClient.tools();
    for (const name of RESEARCH_MCP_TOOLS) {
      if (allMcpTools[name]) {
        tools[name] = allMcpTools[name];
      }
    }

    // Stream response with GPT-5-mini reasoning
    const result = streamText({
      model: azure.responses(process.env.AZURE_OPENAI_CHAT_DEPLOYMENT || 'gpt-5-mini'),
      system: SYSTEM_PROMPT,
      messages: await convertToModelMessages(messages),
      tools,
      stopWhen: stepCountIs(maxSteps + 1),
      experimental_telemetry: {
        isEnabled: true,
        functionId: 'research-chat',
      },
      providerOptions: {
        openai: {
          reasoning_effort: 'low',
          reasoningSummary: 'detailed',
        },
      },
      async onFinish() {
        await mcpClient?.close();
      },
      onError({ error }) {
        console.error('streamText error:', error);
        mcpClient?.close();
      },
    });

    // Flush Langfuse traces after response completes
    after(async () => {
      await langfuseSpanProcessor.forceFlush();
    });

    return result.toUIMessageStreamResponse({
      sendReasoning: true,
    });
  } catch (error) {
    await mcpClient?.close();
    console.error('Deep research error:', error);
    return new Response(
      JSON.stringify({
        error: 'Failed to process research query',
        details: error instanceof Error ? error.message : 'Unknown error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }
}
