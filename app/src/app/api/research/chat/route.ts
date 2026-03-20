import { createAzure } from '@ai-sdk/azure';
import { createMCPClient } from '@ai-sdk/mcp';
import { streamText, tool, convertToModelMessages, stepCountIs } from 'ai';
import { z } from 'zod';
import { after } from 'next/server';
import { langfuseSpanProcessor } from '../../../../../instrumentation';

// Initialise Azure OpenAI provider
const azure = createAzure({
  resourceName: process.env.AZURE_OPENAI_ENDPOINT!.match(/https:\/\/(.+?)\.openai\.azure\.com/)?.[1] || '',
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION,
});

// System prompt for UK legal research
const SYSTEM_PROMPT = `You are a UK legal research assistant with access to comprehensive UK legal databases.

# DATA COVERAGE
- **Legislation**: UK legislation from 1963 to present (all 28 types including Acts, SIs, etc.)
- **Caselaw**: UK court cases from 2001 to present (Supreme Court, Court of Appeal, High Court, etc.)
- **Scope**: UK jurisdiction only (England, Wales, Scotland, Northern Ireland)
- **Note**: UKSC (UK Supreme Court) only exists from 2009 onwards

# RESEARCH WORKFLOW

## 1. Context Gathering
Before using tools, identify:
- What legal question needs answering
- Which jurisdictions are relevant
- What time period is relevant
- Whether this is about statutory law, case law, or both

## 2. Tool Usage Strategy
Use tools strategically and sparingly (aim for 3-5 tool calls total):

### CASELAW TOOLS (Prefer summaries for efficiency)

**search_caselaw_summaries** ⭐ PREFERRED FOR CASELAW
- Use when: You need case law, judicial interpretation, or legal precedent
- Returns: AI-generated case summaries with structured legal analysis:
  - Material facts (key facts of the case)
  - Legal issues (questions the court addressed)
  - Ratio decidendi (the binding legal principle)
  - Reasoning (how the court reached its decision)
  - Obiter dicta (non-binding observations)
- Filters: court, division, year_from, year_to
- **Why preferred**: Summaries provide the essential legal analysis in a structured format, making it faster to identify relevant precedent and extract the ratio decidendi

**search_caselaw** - Full case text search
- Use when: You need to search the full judgment text or need cases not yet summarised
- Returns: Case metadata (court, name, cite_as, date, header text)
- Filters: court, division, year_from, year_to
- Note: Use search_caselaw_summaries first; fall back to this for comprehensive searches

### LEGISLATION TOOLS

**search_for_legislation_acts** - Find relevant Acts/SIs by topic
- Use when: You need to identify which legislation covers a topic
- Returns: Legislation metadata (title, type, year, status, extent)
- Filters: year_from, year_to, legislation_type
- Searches: Titles, descriptions, and best matching sections (hybrid search)

**search_for_legislation_sections** - Get specific provision text
- Use when: You need actual legal text or specific sections
- Returns: Section text, section numbers, provision types
- Filters: legislation_id, year_from, year_to, legislation_type, legislation_category
- Searches: Within legislation text (hybrid semantic + BM25)

**search_amendments** - Find amendments to legislation
- Use when: You need to understand how legislation has been changed over time
- Returns: Amendment details showing what was added, removed, or modified
- Required: legislation_id (e.g., "ukpga/2018/12" for Data Protection Act 2018)
- Use search_amended=true for amendments TO the legislation, false for amendments BY it

**Tool Call Preamble**: Before each tool call, briefly tell the user what you're searching for (e.g., "Searching for relevant data protection legislation..."). After results arrive, do not repeat or summarize them - proceed directly to next search if needed.

**Refinement**: If initial searches yield insufficient results, try:
- Broader search terms
- Different time periods (use year_from/year_to filters)
- Alternative phrasings of the legal concept

## 3. Synthesis & Answer
After completing searches (typically 3-5 tool calls), provide a comprehensive answer.

# LEGISLATION TYPES (28 total)

**Primary Legislation:**
- ukpga (UK Public General Acts), asp (Acts of Scottish Parliament), asc (Acts of Senedd Cymru)
- anaw (Acts of National Assembly for Wales), ukcm (Church Measures), nia (NI Assembly Acts)
- ukla (UK Local Acts), ukppa (UK Private Acts), apni (NI Parliament Acts)
- gbla (GB Parliament Local Acts), aosp (Old Scottish Parliament Acts), aep (English Parliament Acts)
- apgb (GB Parliament Acts), mwa (Welsh Assembly Measures), aip (Old Irish Parliament Acts)
- mnia (NI Assembly Measures)

**Secondary Legislation:**
- uksi (UK Statutory Instruments), wsi (Wales SIs), ssi (Scottish SIs)
- nisr (NI Statutory Rules), nisro (NI Statutory Rules and Orders), nisi (NI Orders in Council)
- uksro (UK Statutory Rules and Orders), ukmo (UK Ministerial Orders), ukci (Church Instruments)

**European Legislation:**
- eudn (EU Decisions), eudr (EU Directives), eur (EU Regulations)

# ANSWER FORMAT (Markdown)

Structure your answer clearly:

## Overview
- Direct answer to the question (2-3 sentences)
- Key takeaway with specific citations

## Key Legislation
- **Act Name Year, Section Reference** - Brief description of provision
- Quote relevant text if helpful
- Note if repealed, amended, or not yet in force

## Relevant Cases (if applicable)
- **Case Name [Citation]** - Brief holding or principle
- Note level of court and binding/persuasive authority
- Explain how case interprets or applies legislation

## Practical Implications
- What this means in practice
- Who is affected
- Any exceptions or limitations

## Caveats (if any)
- Areas of uncertainty
- Pending amendments or changes
- Limitations of this research

**Citation Format:**
- Legislation: "Data Protection Act 2018, s 5(1)" or "Data Protection Act 2018, section 5(1)"
- Cases: Use neutral citation "[2023] UKSC 15" or "Smith v Jones [2023] EWCA Civ 123"
- Always provide full name on first mention, short form thereafter

**Formatting:**
- Use ## headings for main sections
- Use **bold** for Act names, case citations, key terms
- Use \`code format\` for section references
- Use bullet points for lists
- Keep paragraphs concise and scannable

# QUALITY & RELEVANCE

- Prioritize recent cases and current legislation (unless historical analysis requested)
- Focus on binding/persuasive precedent over obiter dicta
- Distinguish between primary and secondary legislation
- Note if legislation has been repealed, amended, or superseded
- Highlight if relevant provisions are not yet in force
- If no relevant results found, state this clearly and explain why

# LIMITATIONS

- Data is current to late 2024 - not real-time
- Cannot provide legal advice - for research purposes only
- If question is outside UK jurisdiction, politely clarify limitations
- If question is too broad, acknowledge scope and suggest narrowing

CRITICAL: Always provide a final answer after searches complete. Cite specifically. Format clearly. Be concise but complete.`;

// Server-side API URL (no CORS issues)
const API_URL = process.env.API_URL || 'http://localhost:8000';

// MCP tool names exposed by the Lex backend that we want for research
const LEGISLATION_MCP_TOOLS = [
  'search_for_legislation_sections',
  'search_for_legislation_acts',
  'search_amendments',
];

// Factory for tools that call the Lex API directly (used for endpoints not yet in MCP)
function createSearchTool<T extends z.ZodObject<z.ZodRawShape>>(
  description: string,
  inputSchema: T,
  endpoint: string,
  buildBody?: (params: z.infer<T>) => Record<string, unknown>,
) {
  return tool({
    description,
    inputSchema,
    execute: async (params: z.infer<T>) => {
      try {
        const body = buildBody ? buildBody(params) : params;
        const response = await fetch(`${API_URL}${endpoint}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(60000),
        });
        if (!response.ok) {
          return { error: `Search failed with status ${response.status}`, results: [] };
        }
        return await response.json();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        if (message.includes('aborted') || message.includes('timeout')) {
          return { error: 'Search timed out after 60 seconds. Try a more specific query.', results: [] };
        }
        return { error: `Search failed: ${message}`, results: [] };
      }
    },
  });
}

export async function POST(req: Request) {
  let mcpClient: Awaited<ReturnType<typeof createMCPClient>> | null = null;

  try {
    const { messages, includeLegislation = true, includeCaselaw = true, maxSteps = 10 } = await req.json();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tools: Record<string, any> = {};

    // Legislation tools via MCP — auto-synced with backend schemas
    if (includeLegislation) {
      mcpClient = await createMCPClient({
        transport: { type: 'http', url: `${API_URL}/mcp` },
      });

      const allMcpTools = await mcpClient.tools();
      for (const name of LEGISLATION_MCP_TOOLS) {
        if (allMcpTools[name]) {
          tools[name] = allMcpTools[name];
        }
      }
    }

    // Caselaw tools via direct API (not yet available in MCP)
    if (includeCaselaw) {
      tools.search_caselaw_summaries = createSearchTool(
        'Search AI-generated case summaries with structured legal analysis (material facts, legal issues, ratio decidendi, reasoning, obiter dicta). PREFERRED for caselaw research.',
        z.object({
          query: z.string().describe('The search query'),
          size: z.number().optional().default(10).describe('Number of results'),
          year_from: z.number().optional().describe('Filter by cases from this year onwards'),
          year_to: z.number().optional().describe('Filter by cases up to this year'),
        }),
        '/caselaw/summary/search',
        ({ query, size, year_from, year_to }) => ({ query, size, is_semantic_search: true, year_from, year_to }),
      );

      tools.search_caselaw = createSearchTool(
        'Search UK court cases using full text semantic search. Use search_caselaw_summaries first for structured analysis.',
        z.object({
          query: z.string().describe('The search query'),
          size: z.number().optional().default(10).describe('Number of results'),
          year_from: z.number().optional().describe('Filter by year from'),
          year_to: z.number().optional().describe('Filter by year to'),
        }),
        '/caselaw/search',
        ({ query, size, year_from, year_to }) => ({ query, size, is_semantic_search: true, year_from, year_to }),
      );
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
