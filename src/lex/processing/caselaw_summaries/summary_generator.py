"""Generate AI summaries for caselaw using GPT-5-nano."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from openai import AzureOpenAI

from lex.caselaw.models import Caselaw, CaselawSummary

logger = logging.getLogger(__name__)

# Azure OpenAI client (lazy loaded)
_openai_client: AzureOpenAI | None = None

# Token limits for GPT-5-nano (272K context window)
# Using 90% of limit (~245K tokens, ~900K characters)
MAX_JUDGMENT_CHARS = 900_000
MIN_JUDGMENT_CHARS = 500  # Skip very short judgments (likely procedural orders)

CASELAW_SUMMARY_PROMPT = """Summarise this UK court judgment for legal research purposes.

Case: {name}
Citation: {cite_as}
Court: {court} {division}
Date: {date}

Judgment Text:
{text}

Start with a header line in this exact format:
{name} | {court} {division} | {date}

Then provide a structured summary following law report conventions:

(1) MATERIAL FACTS - The essential facts that determined the outcome (2-3 sentences)

(2) LEGAL ISSUES - The question(s) of law the court had to decide (1-2 sentences)

(3) HELD (Ratio Decidendi) - The binding legal principle(s) established by this decision. \
State as a rule that could apply to future cases with different facts. (2-3 sentences)

(4) REASONING - Key reasons given for the decision (2-3 sentences)

(5) OBITER DICTA - Any significant observations not essential to the decision, \
if present (1 sentence, or "None")

Write precisely and authoritatively. Use legal terminology appropriately but ensure \
accessibility. Include key legal concepts and terms that researchers might search for."""


def get_openai_client() -> AzureOpenAI:
    """Lazy load Azure OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-03-01-preview",  # GPT-5 Responses API
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
        logger.info("Azure OpenAI client initialised for caselaw summary generation")
    return _openai_client


def generate_summary(
    caselaw: Caselaw, model: str = "gpt-5-nano"
) -> tuple[str, str, datetime, int, bool]:
    """
    Generate AI summary for a caselaw judgment.

    Args:
        caselaw: Caselaw object to summarise
        model: Model name (default: gpt-5-nano)

    Returns:
        Tuple of (summary_text, model_used, timestamp, source_length, was_truncated)
    """
    source_text = caselaw.text
    source_length = len(source_text)
    was_truncated = False

    # Truncate if exceeds token limit
    if source_length > MAX_JUDGMENT_CHARS:
        source_text = source_text[:MAX_JUDGMENT_CHARS] + "\n\n[... judgment text truncated ...]"
        was_truncated = True
        logger.info(
            f"Truncated judgment for {caselaw.id} "
            f"from {source_length} to {MAX_JUDGMENT_CHARS} chars"
        )

    # Build prompt
    division_str = caselaw.division.value.upper() if caselaw.division else ""
    prompt = CASELAW_SUMMARY_PROMPT.format(
        name=caselaw.name,
        cite_as=caselaw.cite_as or "N/A",
        court=caselaw.court.value.upper(),
        division=division_str,
        date=caselaw.date.isoformat(),
        text=source_text,
    )

    try:
        openai_client = get_openai_client()
        deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", model)

        logger.info(f"Generating summary for caselaw {caselaw.id} using {deployment}")

        response = openai_client.responses.create(
            model=deployment,
            input=prompt,
            reasoning={"effort": "medium"},  # Medium reasoning for complex legal analysis
            # No max_output_tokens - let model determine appropriate length
        )

        summary = response.output_text.strip()
        timestamp = datetime.now(timezone.utc)

        logger.info(f"Successfully generated summary for caselaw {caselaw.id}")

        return summary, deployment, timestamp, source_length, was_truncated

    except Exception as e:
        logger.error(f"Failed to generate summary for caselaw {caselaw.id}: {e}")
        error_msg = f"Error generating summary: {str(e)[:200]}"
        return error_msg, model, datetime.now(timezone.utc), source_length, was_truncated


def create_summary_from_caselaw(
    caselaw: Caselaw, model: str = "gpt-5-nano"
) -> CaselawSummary | None:
    """
    Create a CaselawSummary object from a Caselaw judgment.

    Args:
        caselaw: Caselaw object to summarise
        model: Model name to use

    Returns:
        CaselawSummary object, or None if judgment is too short
    """
    # Skip very short judgments (likely procedural orders)
    if len(caselaw.text) < MIN_JUDGMENT_CHARS:
        logger.info(f"Skipping {caselaw.id} - judgment too short ({len(caselaw.text)} chars)")
        return None

    summary_text, model_used, timestamp, source_length, was_truncated = generate_summary(
        caselaw, model
    )

    return CaselawSummary(
        id=f"{caselaw.id}-summary",
        caselaw_id=caselaw.id,
        court=caselaw.court,
        division=caselaw.division,
        year=caselaw.year,
        number=caselaw.number,
        name=caselaw.name,
        cite_as=caselaw.cite_as,
        date=caselaw.date,
        text=summary_text,
        ai_model=model_used,
        ai_timestamp=timestamp,
        source_text_length=source_length,
        source_text_truncated=was_truncated,
    )


def add_summaries_to_caselaw(
    caselaw_items: list[Caselaw], model: str = "gpt-5-nano", max_workers: int = 25
) -> list[CaselawSummary]:
    """
    Generate AI summaries for a list of caselaw items in parallel.

    Args:
        caselaw_items: List of Caselaw objects
        model: Model name to use (default: gpt-5-nano)
        max_workers: Number of concurrent workers (default: 25)

    Returns:
        List of CaselawSummary objects
    """
    logger.info(
        f"Generating summaries for {len(caselaw_items)} caselaw items using {model} "
        f"({max_workers} workers)"
    )

    # Filter to only cases that need summaries (long enough text)
    cases_to_process = [c for c in caselaw_items if len(c.text) >= MIN_JUDGMENT_CHARS]

    if not cases_to_process:
        logger.info("No caselaw items need summaries (all too short)")
        return []

    logger.info(
        f"Processing {len(cases_to_process)} caselaw items "
        f"(skipped {len(caselaw_items) - len(cases_to_process)} short judgments)"
    )

    summaries: list[CaselawSummary] = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_caselaw = {
            executor.submit(create_summary_from_caselaw, caselaw, model): caselaw
            for caselaw in cases_to_process
        }

        for future in as_completed(future_to_caselaw):
            caselaw = future_to_caselaw[future]
            completed += 1

            try:
                summary = future.result()
                if summary:
                    summaries.append(summary)

                if completed % 10 == 0 or completed == len(cases_to_process):
                    logger.info(
                        f"Progress: {completed}/{len(cases_to_process)} summaries generated"
                    )

            except Exception as e:
                logger.error(f"Failed to process caselaw {caselaw.id}: {e}")
                continue

    logger.info(f"Generated {len(summaries)} summaries from {len(caselaw_items)} caselaw items")
    return summaries
