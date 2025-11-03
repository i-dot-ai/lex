import { createAzure } from '@ai-sdk/azure';
import { generateObject } from 'ai';
import { z } from 'zod';

// Initialize Azure OpenAI provider
const azure = createAzure({
  resourceName: process.env.AZURE_OPENAI_ENDPOINT!.match(/https:\/\/(.+?)\.openai\.azure\.com/)?.[1] || '',
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION,
});

export async function POST(req: Request) {
  try {
    const { recentQueries, searchType } = await req.json();

    // Validate input
    if (!recentQueries || !Array.isArray(recentQueries) || recentQueries.length === 0) {
      return new Response(
        JSON.stringify({ suggestions: [] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Generate AI suggestions using GPT-4.1-nano for maximum speed (fastest model for low-latency tasks)
    const result = await generateObject({
      model: azure('gpt-4.1-nano'),
      schema: z.object({
        suggestions: z.array(z.string()).length(4)
      }),
      prompt: `Based on these recent ${searchType} searches: ${recentQueries.join(', ')}

Generate 4 short, natural UK legal search queries (2-4 words each) that lawyers would realistically search for next. Use British spelling and legal terminology.

Examples:
- Recent: "GDPR compliance" → Suggest: "data breach penalties", "subject access rights"  
- Recent: "employment contracts" → Suggest: "unfair dismissal", "notice periods"
- Recent: "company formation" → Suggest: "directors duties", "share capital"

Return only brief search terms, no explanations.`,
      experimental_telemetry: {
        isEnabled: true,
        functionId: 'search-suggestions',
      },
    });

    return new Response(
      JSON.stringify({ suggestions: result.object.suggestions }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );

  } catch (error) {
    console.error('Search suggestions error:', error);
    return new Response(
      JSON.stringify({ 
        suggestions: [],
        error: 'Failed to generate suggestions'
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}