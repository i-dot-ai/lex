---
name: lex-uk-law
description: UK legal research using the Lex API. Use this skill whenever the user asks about UK law, legislation, statutory instruments, Acts of Parliament, legal provisions, amendments, or anything that could benefit from searching authoritative UK legal sources. Also use when the user mentions specific UK Acts (e.g. "the Data Protection Act"), asks about legal requirements, or needs to understand how legislation has changed over time. Even if the user doesn't explicitly say "search legislation", if they're asking a question that UK law could answer, use this skill.
---

# UK Legal Research with Lex API

You have access to the complete corpus of UK legislation from The National Archives via MCP tools. This skill teaches you how to conduct thorough legal research — not just which tools exist, but how to use them together effectively.

## Research Workflows

Different questions need different approaches. Choose the right workflow for the task.

### "What law covers X?" — Topic Research

When the user asks about a legal topic (e.g. "unfair dismissal", "data protection for AI"):

1. **Search for Acts first** using `search_for_legislation_acts` with a natural language query. Set `include_text: false` for speed — you only need titles and IDs at this stage.
2. **Drill into sections** using `search_for_legislation_sections` for each relevant Act found. Pass the `legislation_id` to scope your search. This is where the substantive law lives.
3. **Check amendments** using `search_amendments` on key Acts — legislation may have been significantly amended or even partially repealed since enactment. This is easy to miss and important.
4. **Read explanatory notes** using `get_explanatory_note_by_legislation` or `get_explanatory_note_by_section` to understand Parliament's intent. Explanatory notes are invaluable for interpretation — they explain *why* provisions exist, not just what they say.

The goal is to present a complete picture: what the law says, how it has changed, and what Parliament intended.

### "What does section X of Y say?" — Specific Lookup

When the user asks about a specific provision:

1. **Look up the Act** using `lookup_legislation` with `legislation_type`, `year`, and `number`.
2. **Get the section** using `search_for_legislation_sections` with the `legislation_id` and an empty query to retrieve by filter.
3. **Check amendments** to that section using `search_amendment_sections` with the `provision_id` (e.g. "ukpga/1998/42/section/3"), then also `search_amendments` at the Act level. Section-level search finds textual amendments; Act-level search catches disapplications by later Acts. Both are needed for a complete picture.
4. **Get the explanatory note** using `get_explanatory_note_by_section` for context on what the provision means.

### "How has X been amended?" — Amendment Research

When the user asks about changes to legislation:

1. **For section-level amendments**: use `search_amendment_sections` with the `provision_id` (e.g. "ukpga/1998/42/section/3"). The provision_id must include the section path, not just the Act ID.
2. **Always also check Act-level amendments**: use `search_amendments` with the `legislation_id`. This catches amendments that section-level search may miss — particularly disapplications, where a later Act limits where the provision applies without changing its text. Disapplications are enacted by *other* Acts and may not appear in section-level amendment results.
3. **If both return nothing, search for referencing legislation**: use `search_for_legislation_sections` with a query describing the provision (e.g. "section 3 Human Rights Act"). Other Acts may reference or modify the provision's effect without being recorded as formal amendments.
4. **Distinguish amendment types**: textual amendments change the wording; disapplications limit where the provision applies without changing its text; repeals remove it entirely. Disapplications are easy to miss because the original text looks unchanged — always check for them explicitly.

### "What was the intent behind X?" — Parliamentary Intent

1. **Get explanatory notes** using `get_explanatory_note_by_legislation` for an overview of the whole Act, or `get_explanatory_note_by_section` for a specific provision.
2. **Search notes by topic** using `search_explanatory_note` with a natural language query if you don't know which Act is relevant.
3. **Filter by note type**: use `note_type` to focus on specific sections of the explanatory material (overview, policy_background, legal_background, extent, provisions, commencement, related_documents).

## Common Mistakes to Avoid

- **Searching Acts when you need sections**: `search_for_legislation_acts` returns whole Acts ranked by relevance. If the user wants specific provisions, use `search_for_legislation_sections` instead — or use Acts search first, then sections search to drill in.
- **Not checking amendments**: Always check amendments for key provisions. Legislation from even a few years ago may have been substantially changed.
- **Only checking section-level amendments**: `search_amendment_sections` finds direct textual amendments but can miss disapplications enacted by other Acts. Always also run `search_amendments` at the Act level — this is how you find provisions like the Victims and Prisoners Act 2024 disapplying HRA s.3 in specific contexts.
- **Repeating the same search**: If a search returns poor results, try different terms rather than the same query again. The search is semantic — rephrase your query.
- **Forgetting explanatory notes**: When the user asks "why" or "what was the intent", explanatory notes are the answer. They're published by the government alongside the Act and explain the purpose of each provision.
- **Using full URLs as IDs**: Use short form IDs like "ukpga/1998/42", not "http://www.legislation.gov.uk/id/ukpga/1998/42".

## Tool Reference

### Legislation Search
- `search_for_legislation_acts` — find Acts/SIs by topic. Key params: `query`, `legislation_type`, `year_from`/`year_to`, `include_text`, `limit`.
- `search_for_legislation_sections` — find provisions within legislation. Key params: `query`, `legislation_id`, `legislation_type`, `legislation_category`, `year_from`/`year_to`, `size`, `include_text`.

### Legislation Retrieval
- `lookup_legislation` — get a specific Act by type/year/number.
- `get_legislation_sections` — list all sections of an Act by `legislation_id`.
- `get_legislation_full_text` — complete text. Set `include_schedules: true` only if specifically needed.
- `proxy_legislation_data` — enriched metadata from legislation.gov.uk.

### Explanatory Notes
- `search_explanatory_note` — search note content. Key params: `query`, `legislation_id`, `note_type`, `section_type`.
- `get_explanatory_note_by_legislation` — all notes for an Act.
- `get_explanatory_note_by_section` — note for a specific section number.

### Amendments
- `search_amendments` — Act-level amendments. Key params: `legislation_id`, `search_amended`.
- `search_amendment_sections` — section-level amendments. Key params: `provision_id`, `search_amended`.

## Output Guidelines

When presenting legal research:
- **Cite precisely**: include Act name, year, section number, and legislation ID.
- **Structure by Act**: group findings under each relevant Act with clear headings.
- **Distinguish current from historical**: note if provisions have been amended, repealed, or disapplied.
- **Quote sparingly**: short quotes from the legislation text are useful; long block quotes are not.
- **Include a sources table**: list the Acts consulted with their legislation IDs at the end.

## Data Coverage

- **Legislation**: 1267–present (complete digital coverage from 1963; pre-1963 uses PDF extraction)
- **Explanatory Notes**: available for modern legislation (post-1999)
- **Amendments**: cross-referencing between all legislation
- **Sources**: The National Archives / legislation.gov.uk
