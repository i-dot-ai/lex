import { createAzure } from '@ai-sdk/azure';
import { streamText, tool, convertToModelMessages, stepCountIs } from 'ai';
import { z } from 'zod';
import { after } from 'next/server';
import { langfuseSpanProcessor } from '../../../../../instrumentation';

// Initialize Azure OpenAI provider
const azure = createAzure({
  resourceName: process.env.AZURE_OPENAI_ENDPOINT!.match(/https:\/\/(.+?)\.openai\.azure\.com/)?.[1] || '',
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  // v1 API doesn't require version parameter (defaults to 'v1')
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

**search_legislation_acts** - Find relevant Acts/SIs by topic
- Use when: You need to identify which legislation covers a topic
- Returns: Legislation metadata (title, type, year, status, extent)
- Filters: year_from, year_to, legislation_type
- Searches: Titles, descriptions, and best matching sections (hybrid search)

**search_legislation_sections** - Get specific provision text
- Use when: You need actual legal text or specific sections
- Returns: Section text, section numbers, provision types
- Filters: legislation_id, year_from, year_to, legislation_type, legislation_category
- Searches: Within legislation text (hybrid semantic + BM25)

**search_caselaw** - Find judicial interpretation and precedent
- Use when: You need case law or judicial interpretation of legislation
- Returns: Case metadata (court, name, cite_as, date, header text)
- Filters: court, division, year_from, year_to
- Searches: Case names, citations, summaries (semantic search)

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

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(req: Request) {
  try {
    const { messages, includeLegislation = true, includeCaselaw = true, maxSteps = 10 } = await req.json();

    // Define tools as direct API calls
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tools: Record<string, any> = {};

    if (includeLegislation) {
      tools.search_legislation_sections = tool({
        description: 'Search within UK legislation text using semantic search',
        inputSchema: z.object({
          query: z.string().describe('The search query'),
          size: z.number().optional().describe('Number of results (default 10)'),
          year_from: z.number().optional().describe('Filter by year from'),
          year_to: z.number().optional().describe('Filter by year to'),
        }),
        execute: async ({ query, size = 10, year_from, year_to }) => {
          const startTime = Date.now();
          try {
            console.log(`[TOOL] Legislation section search starting: "${query}"`);
            console.log(`[TOOL] Fetching: ${API_URL}/legislation/section/search`);
            const fetchStart = Date.now();
            const response = await fetch(`${API_URL}/legislation/section/search`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ query, size, year_from, year_to }),
              signal: AbortSignal.timeout(60000), // 60 second timeout
            });
            const fetchElapsed = Date.now() - fetchStart;
            console.log(`[TOOL] Fetch completed in ${fetchElapsed}ms, status: ${response.status}`);
            const elapsed = Date.now() - startTime;
            console.log(`[TOOL] Legislation section search completed in ${elapsed}ms`);

            if (!response.ok) {
              return { error: `Search failed with status ${response.status}`, results: [] };
            }

            return await response.json();
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('Legislation section search error:', errorMessage);

            if (errorMessage.includes('aborted') || errorMessage.includes('timeout')) {
              return { error: 'Search timed out after 60 seconds. Try a more specific query.', results: [] };
            }

            return { error: `Search failed: ${errorMessage}`, results: [] };
          }
        },
      });

      tools.search_legislation_acts = tool({
        description: 'Search UK legislation titles and metadata',
        inputSchema: z.object({
          query: z.string().describe('The search query'),
          limit: z.number().optional().describe('Number of results (default 10)'),
          year_from: z.number().optional().describe('Filter by year from'),
          year_to: z.number().optional().describe('Filter by year to'),
        }),
        execute: async ({ query, limit = 10, year_from, year_to }) => {
          const startTime = Date.now();
          try {
            console.log(`[TOOL] Legislation acts search starting: "${query}"`);
            console.log(`[TOOL] Fetching: ${API_URL}/legislation/search`);
            const fetchStart = Date.now();
            const response = await fetch(`${API_URL}/legislation/search`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ query, limit, use_semantic_search: true, year_from, year_to }),
              signal: AbortSignal.timeout(60000), // 60 second timeout
            });
            const fetchElapsed = Date.now() - fetchStart;
            console.log(`[TOOL] Fetch completed in ${fetchElapsed}ms, status: ${response.status}`);

            if (!response.ok) {
              return { error: `Search failed with status ${response.status}`, results: [], total: 0 };
            }

            const result = await response.json();
            const elapsed = Date.now() - startTime;
            console.log(`[TOOL] Legislation acts search completed in ${elapsed}ms`);
            return result;
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('Legislation act search error:', errorMessage);

            if (errorMessage.includes('aborted') || errorMessage.includes('timeout')) {
              return { error: 'Search timed out after 60 seconds. Try a more specific query.', results: [], total: 0 };
            }

            return { error: `Search failed: ${errorMessage}`, results: [], total: 0 };
          }
        },
      });
    }

    if (includeCaselaw) {
      tools.search_caselaw = tool({
        description: 'Search UK court cases using semantic search',
        inputSchema: z.object({
          query: z.string().describe('The search query'),
          size: z.number().optional().describe('Number of results (default 10)'),
          year_from: z.number().optional().describe('Filter by year from'),
          year_to: z.number().optional().describe('Filter by year to'),
        }),
        execute: async ({ query, size = 10, year_from, year_to }) => {
          const startTime = Date.now();
          try {
            console.log(`[TOOL] Caselaw search starting: "${query}"`);
            console.log(`[TOOL] Fetching: ${API_URL}/caselaw/search`);
            const fetchStart = Date.now();
            const response = await fetch(`${API_URL}/caselaw/search`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ query, size, is_semantic_search: true, year_from, year_to }),
              signal: AbortSignal.timeout(60000), // 60 second timeout
            });
            const fetchElapsed = Date.now() - fetchStart;
            console.log(`[TOOL] Fetch completed in ${fetchElapsed}ms, status: ${response.status}`);

            if (!response.ok) {
              return { error: `Search failed with status ${response.status}`, results: [], total: 0 };
            }

            const result = await response.json();
            const elapsed = Date.now() - startTime;
            console.log(`[TOOL] Caselaw search completed in ${elapsed}ms`);
            return result;
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('Caselaw search error:', errorMessage);

            if (errorMessage.includes('aborted') || errorMessage.includes('timeout')) {
              return { error: 'Search timed out after 60 seconds. Try a more specific query.', results: [], total: 0 };
            }

            return { error: `Search failed: ${errorMessage}`, results: [], total: 0 };
          }
        },
      });
    }

    // Stream the response using GPT-5-mini with reasoning
    // Add 1 to maxSteps to ensure there's always room for a final synthesis after tool calls
    const result = streamText({
      model: azure.responses(process.env.AZURE_OPENAI_CHAT_DEPLOYMENT || 'gpt-5-mini'),
      system: SYSTEM_PROMPT,
      messages: convertToModelMessages(messages),
      tools,
      stopWhen: stepCountIs(maxSteps + 1), // +1 to allow final synthesis after research steps
      experimental_telemetry: {
        isEnabled: true,
        functionId: 'research-chat',
      },
      providerOptions: {
        openai: {
          reasoning_effort: 'low', // Balanced reasoning for legal research (was 'minimal')
          reasoningSummary: 'detailed', // 'auto' or 'detailed' for GPT-5
        }
      },
      onError({ error }) {
        console.error('streamText error:', error);
      },
    });

    // Flush Langfuse traces after response completes
    after(async () => {
      await langfuseSpanProcessor.forceFlush();
    });

    return result.toUIMessageStreamResponse({
      sendReasoning: true, // Enable reasoning traces in UI stream
    });
  } catch (error) {
    console.error('Deep research error:', error);
    return new Response(
      JSON.stringify({
        error: 'Failed to process research query',
        details: error instanceof Error ? error.message : 'Unknown error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
