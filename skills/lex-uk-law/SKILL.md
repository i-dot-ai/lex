---
name: lex-uk-law
description: UK legal research using the Lex API. Search UK legislation, case law, and legal provisions. Use when researching UK law, finding legal precedents, analysing statutory instruments, or grounding responses in authoritative legal sources.
---

# UK Legal Research with Lex API

This skill requires the **Lex MCP server** to be installed and enabled. The skill provides guidance on using the Lex tools effectively for UK legal research.

## Prerequisites: Lex MCP Server

Check if Lex tools are available (e.g. `search_legislation`, `search_caselaw`). If not installed, refer the user to https://github.com/i-dot-ai/lex for setup instructions.

## When to Use This Skill
- Researching UK legislation (Acts, Statutory Instruments)
- Finding court judgments and legal precedents
- Searching for specific legal provisions or sections
- Analysing how legislation has been amended over time
- Grounding AI responses in authoritative UK legal sources

## Available Tools

The Lex MCP server provides these tools:

### Legislation Search
- **search_legislation** - Semantic search across UK Acts and Statutory Instruments
- **search_legislation_sections** - Search within specific provisions and sections
- **get_legislation_amendments** - Find amendments to legislation

### Case Law Search
- **search_caselaw** - Semantic search across court judgments
- **search_caselaw_paragraphs** - Search within case paragraphs
- **find_caselaw_references** - Find cases referencing specific legislation

## Search Best Practices

1. **Be specific with queries** - "employment tribunal unfair dismissal" works better than "employment law"
2. **Use filters** - Filter by year, court, or legislation type when possible
3. **Combine searches** - Search legislation first, then find related case law
4. **Check amendments** - Legislation may have been amended since enactment

## Data Coverage

- **Legislation**: 1267-present (complete from 1963)
- **Case Law**: 2001-present
- **Sources**: The National Archives, Find Case Law

## Important Notes

- This is an experimental service for research purposes
- PDF-sourced legislation (pre-1963) uses LLM extraction - verify at source for critical accuracy
- Rate limited to 60 requests/minute
