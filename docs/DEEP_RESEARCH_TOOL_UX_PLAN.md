# Deep Research Tool Call UX Improvements

## Problem

Tool calls currently show only metadata: "search legislation acts" with query and size params.
No visibility into actual results, relevance, or actionable data.

## Technical Discovery (AI SDK v5)

**UPDATED Finding**: AI SDK v5 **DOES automatically stream tool results** to the client!

- Tools execute server-side with `execute` functions
- Client receives: tool calls (inputs), reasoning traces, text responses, AND tool results
- Tool results available in `part.output` when `part.state === 'output-available'`
- No custom streaming code needed - built into `toUIMessageStreamResponse()` + `useChat`

## Solution: Progressive Enhancement (No Overengineering)

### Phase 1: Improved Tool Call & Reasoning Display (COMPLETED)

**Goal**: Make tool calls and reasoning traces more readable, show query context, and display results

✅ **Implemented:**

**Tool Calls:**

1. Capitalized tool names for better readability
2. Inline layout: tool name, query (monospace), and result count on one line
3. Query text in monospace font to distinguish it as input data
4. Long queries truncated with ellipsis to prevent wrapping
5. **Result count badge** showing "X result(s)" when available
6. **Expandable result previews** showing top 3 results with title/citation
7. "+N more results" indicator for results beyond top 3
8. Chevrons only visible on hover (cleaner interface)
9. Smooth slide-in animation when expanding

**Reasoning Traces:**
10. First line shown as preview, full content on expand
11. Markdown stripped from preview title to avoid syntax artifacts
12. First line not duplicated in expanded content
13. Chevrons only visible on hover
14. Smooth slide-in animation when expanding

**Layout & Spacing:**
15. Individual chronological display (reasoning and tools in order they occurred)
16. Intelligent type-based spacing: tight within groups (space-y-1.5), extra gap between different types (mb-5)
17. Maximum 85% width for better readability

**Current Format:**

```
🔍 Search legislation acts "digital identity UK legislation" 10 results ›
   [Click to expand and see top 3 results]

🧠 Analyzing search results for key legislation... ›
   [Click to expand for full reasoning]
```

### Phase 2: Future Enhancements (Optional)

**No backend changes needed** - tool results already stream automatically!

Possible future improvements:

- Click result to open full legislation/caselaw preview modal
- Show relevance scores if available in backend responses
- Add "View all N results" button to open filtered search page
- Highlight matching terms in result snippets

**Implementation**: These would require updating backend to return additional metadata (scores, snippets) in tool execution responses.

## Implementation Notes

- Reuse existing badge components where possible
- Keep tool call display compact by default
- Progressive disclosure: collapsed → summary → full details
- Don't create new complex components - extend existing card system

## Anti-Patterns to Avoid

❌ Building a new result preview system (reuse LegislationPreview)
❌ Complex state management for result caching
❌ Over-styled result cards
❌ Automatic modal popups

✅ Simple list rendering
✅ Basic expand/collapse
✅ Minimal styling changes
✅ User-initiated actions only
