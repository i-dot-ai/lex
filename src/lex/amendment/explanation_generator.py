"""Generate AI explanations for amendments using GPT-5."""

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from openai import AzureOpenAI

from lex.amendment.models import Amendment
from lex.core.http import HttpClient

logger = logging.getLogger(__name__)

# Initialize clients
_http_client: Optional[HttpClient] = None
_openai_client: Optional[AzureOpenAI] = None


def get_http_client() -> HttpClient:
    """Lazy load HTTP client with caching."""
    global _http_client
    if _http_client is None:
        _http_client = HttpClient(
            cache_ttl=28800,  # 8 hours - provisions are relatively stable
            max_retries=30,
            max_delay=600.0,
            timeout=30,
        )
        logger.info("HTTP client initialized for amendment explanation generation")
    return _http_client


def get_openai_client() -> AzureOpenAI:
    """Lazy load Azure OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-03-01-preview",  # GPT-5 Responses API
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
        logger.info("Azure OpenAI client initialized for amendment explanation generation")
    return _openai_client


def fetch_provision_text(provision_url: str) -> Optional[str]:
    """
    Fetch provision text from legislation.gov.uk XML.

    Args:
        provision_url: Full provision URL (e.g., "http://www.legislation.gov.uk/id/ukpga/2024/1/section/5")

    Returns:
        Text content of the provision, or None if not found
    """
    # Ensure http:// (legislation.gov.uk uses http in IDs)
    provision_url = provision_url.replace("https://", "http://")

    # Build XML URL
    xml_url = f"{provision_url}/data.xml"

    try:
        http_client = get_http_client()
        response = http_client.get(xml_url)
        response.raise_for_status()

        # Parse XML and extract text
        root = ET.fromstring(response.content)

        # Extract text from all text elements (simplified extraction)
        texts = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                text = elem.text.strip()
                # Skip very short text (likely tags/metadata)
                if len(text) > 3:
                    texts.append(text)

        full_text = " ".join(texts)

        # Truncate if very long (keep within token limits)
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "... [truncated]"

        return full_text if full_text else None

    except Exception as e:
        logger.warning(f"Failed to fetch provision text from {xml_url}: {e}")
        return None


def generate_explanation(amendment: Amendment, model: str = "gpt-5-mini") -> tuple[str, str, datetime]:
    """
    Generate AI explanation for an amendment.

    Args:
        amendment: Amendment object to explain
        model: Model name (default: gpt-5-mini)

    Returns:
        Tuple of (explanation_text, model_used, timestamp)
    """
    # Fetch provision texts
    changed_text = None
    if amendment.changed_provision_url:
        changed_text = fetch_provision_text(amendment.changed_provision_url)

    affecting_text = None
    if amendment.affecting_provision_url:
        affecting_text = fetch_provision_text(amendment.affecting_provision_url)

    # Build prompt
    prompt = f"""Analyze this UK legislative amendment and explain what it does in 2-3 clear sentences.

Amendment Details:
- Changed Legislation: {amendment.changed_legislation}
- Changed Provision: {amendment.changed_provision or 'N/A'}
- Affecting Legislation: {amendment.affecting_legislation or 'N/A'}
- Affecting Provision: {amendment.affecting_provision or 'N/A'}
- Type of Effect: {amendment.type_of_effect or 'N/A'}

Changed Provision Text (current version):
{changed_text if changed_text else '[Not available - provision may not exist or have been repealed]'}

Affecting Provision Text (the instruction that makes the change):
{affecting_text if affecting_text else '[Not available]'}

Explain: (1) what legal change this makes, (2) the practical impact, (3) use plain language suitable for non-lawyers."""

    try:
        openai_client = get_openai_client()
        deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", model)

        logger.info(f"Generating explanation for amendment {amendment.id} using {deployment}")

        response = openai_client.responses.create(
            model=deployment,
            input=prompt,
            reasoning={"effort": "low"},  # GPT-5 reasoning control
            text={"verbosity": "medium"},  # GPT-5 output control
        )

        explanation = response.output_text.strip()
        timestamp = datetime.utcnow()

        logger.info(f"Successfully generated explanation for amendment {amendment.id}")

        return explanation, deployment, timestamp

    except Exception as e:
        logger.error(f"Failed to generate explanation for amendment {amendment.id}: {e}")
        # Return error message as explanation
        error_msg = f"Error generating explanation: {str(e)[:200]}"
        return error_msg, model, datetime.utcnow()


def add_explanations_to_amendments(amendments: list[Amendment], model: str = "gpt-5-mini") -> list[Amendment]:
    """
    Generate AI explanations for a list of amendments.

    Args:
        amendments: List of Amendment objects
        model: Model name to use (default: gpt-5-mini)

    Returns:
        List of amendments with ai_explanation fields populated
    """
    logger.info(f"Generating explanations for {len(amendments)} amendments using {model}")

    for i, amendment in enumerate(amendments, 1):
        # Skip if already has explanation
        if amendment.ai_explanation:
            logger.info(f"[{i}/{len(amendments)}] Skipping {amendment.id} - already has explanation")
            continue

        # Skip commencement orders (not substantive changes)
        if amendment.type_of_effect and "coming into force" in amendment.type_of_effect.lower():
            logger.info(f"[{i}/{len(amendments)}] Skipping {amendment.id} - commencement order")
            continue

        logger.info(f"[{i}/{len(amendments)}] Generating explanation for {amendment.id}")

        try:
            explanation, model_used, timestamp = generate_explanation(amendment, model)

            # Update amendment object
            amendment.ai_explanation = explanation
            amendment.ai_explanation_model = model_used
            amendment.ai_explanation_timestamp = timestamp

        except Exception as e:
            logger.error(f"Failed to process amendment {amendment.id}: {e}")
            # Continue with next amendment
            continue

    explained_count = sum(1 for a in amendments if a.ai_explanation)
    logger.info(f"Generated explanations for {explained_count}/{len(amendments)} amendments")

    return amendments
