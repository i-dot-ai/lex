import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from fastembed import SparseTextEmbedding
from openai import AzureOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from qdrant_client.models import SparseVector

from lex.settings import EMBEDDING_DEPLOYMENT, EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

# Initialize Azure OpenAI client
_openai_client = None
_openai_client_lock = threading.Lock()

# Initialize FastEmbed BM25 model (lazy loading)
_sparse_model = None
_sparse_model_lock = threading.Lock()

# Rate limiting config
MAX_RETRIES = 10
BASE_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 120.0  # Cap backoff at 2 minutes


def get_openai_client() -> AzureOpenAI:
    """Lazy load Azure OpenAI client (thread-safe)."""
    global _openai_client
    if _openai_client is None:
        with _openai_client_lock:
            # Double-check after acquiring lock
            if _openai_client is None:
                logger.info("Initializing Azure OpenAI client...")
                _openai_client = AzureOpenAI(
                    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                    api_version="2024-02-01",
                    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                    max_retries=0,  # We handle retries manually
                    timeout=60.0,  # 60 second timeout for embedding generation
                )
                logger.info("Azure OpenAI client initialized")
    return _openai_client


def get_sparse_model() -> SparseTextEmbedding:
    """Lazy load sparse model to avoid initialization on import (thread-safe)."""
    global _sparse_model
    if _sparse_model is None:
        with _sparse_model_lock:
            # Double-check after acquiring lock
            if _sparse_model is None:
                logger.info("Initializing FastEmbed BM25 model...")
                _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
                logger.info("FastEmbed BM25 model initialized")
    return _sparse_model


def generate_dense_embedding_with_retry(text: str, max_retries: int = MAX_RETRIES) -> List[float]:
    """
    Generate dense embedding using Azure OpenAI with retry logic for rate limits.

    Args:
        text: Text to embed (max ~8K tokens for text-embedding-3-large)
        max_retries: Maximum number of retry attempts

    Returns:
        1024-dimensional vector

    Raises:
        Exception: If embedding generation fails after all retries
    """
    # Truncate very long texts (OpenAI limit ~8K tokens ≈ 30K chars)
    if len(text) > 30000:
        text = text[:30000]

    client = get_openai_client()

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_DEPLOYMENT, input=text, dimensions=EMBEDDING_DIMENSIONS
            )
            return response.data[0].embedding

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            # Transient errors - retry with exponential backoff + jitter
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate dense embedding after {max_retries} retries: {e}")
                raise

            # Exponential backoff with jitter and cap
            backoff = min(BASE_BACKOFF * (2**attempt), MAX_BACKOFF)
            jitter = random.uniform(0, backoff * 0.1)  # Add up to 10% jitter
            sleep_time = backoff + jitter
            error_type = type(e).__name__
            logger.warning(
                f"{error_type}: {e}, retrying in {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(sleep_time)

        except Exception as e:
            # Non-transient errors - fail immediately
            logger.error(f"Non-retryable error generating embedding: {type(e).__name__}: {e}")
            raise

    # Should never reach here, but if we do, raise
    raise Exception(f"Failed to generate embedding after {max_retries} retries")


def generate_dense_embedding(text: str) -> List[float]:
    """Generate dense embedding (use generate_dense_embeddings_batch for parallel processing).

    Args:
        text: Text to embed

    Returns:
        1024-dimensional vector
    """
    return generate_dense_embedding_with_retry(text)


def generate_dense_embeddings_batch(
    texts: List[str], max_workers: int = 25, progress_callback=None
) -> List[List[float]]:
    """Generate dense embeddings for multiple texts in parallel with rate limit handling.

    Args:
        texts: List of texts to embed
        max_workers: Number of concurrent workers (default 25)
        progress_callback: Optional callback function(completed_count) for progress updates

    Returns:
        List of 1024-dimensional vectors in same order as input texts
    """
    if not texts:
        return []

    results: List[Optional[List[float]]] = [None] * len(texts)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_idx = {
            executor.submit(generate_dense_embedding_with_retry, text): idx
            for idx, text in enumerate(texts)
        }

        # Collect results as they complete
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
                completed += 1

                if progress_callback and completed % 10 == 0:
                    progress_callback(completed)

            except Exception as e:
                logger.error(f"Failed to generate embedding for text {idx}: {e}")
                results[idx] = [0.0] * EMBEDDING_DIMENSIONS

    # Type checker: results is guaranteed to have no None values due to exception handling
    return results  # type: ignore[return-value]


def generate_sparse_embedding(text: str) -> SparseVector:
    """
    Generate sparse BM25 embedding using FastEmbed.

    Args:
        text: Text to embed

    Returns:
        SparseVector with indices and values arrays

    Example:
        SparseVector(indices=[12, 45, 234], values=[0.8, 0.6, 0.4])
    """
    try:
        model = get_sparse_model()
        embeddings = list(model.embed([text]))

        if not embeddings:
            logger.warning("FastEmbed returned no embeddings")
            return SparseVector(indices=[], values=[])

        embedding = embeddings[0]

        # Convert to SparseVector format Qdrant expects
        return SparseVector(
            indices=[int(idx) for idx in embedding.indices],
            values=[float(val) for val in embedding.values],
        )
    except Exception as e:
        logger.error(f"Failed to generate sparse embedding: {e}")
        return SparseVector(indices=[], values=[])


def generate_sparse_embeddings_batch(texts: List[str]) -> List[SparseVector]:
    """
    Generate sparse BM25 embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed

    Returns:
        List of SparseVectors in same order as input texts
    """
    if not texts:
        return []

    try:
        model = get_sparse_model()
        embeddings = list(model.embed(texts))

        return [
            SparseVector(
                indices=[int(idx) for idx in emb.indices], values=[float(val) for val in emb.values]
            )
            for emb in embeddings
        ]
    except Exception as e:
        logger.error(f"Failed to generate sparse embeddings batch: {e}")
        return [SparseVector(indices=[], values=[]) for _ in texts]


def generate_hybrid_embeddings(text: str) -> Tuple[List[float], SparseVector]:
    """Generate both dense and sparse embeddings for hybrid search.

    Args:
        text: Text to embed

    Returns:
        Tuple of (dense_vector, sparse_vector)

    Example:
        ([0.1, 0.2, ...], SparseVector(indices=[12, 45], values=[0.8, 0.6]))
    """
    dense = generate_dense_embedding(text)
    sparse = generate_sparse_embedding(text)
    return dense, sparse


def generate_hybrid_embeddings_batch(
    texts: List[str], max_workers: int = 25, progress_callback=None
) -> List[Tuple[List[float], SparseVector]]:
    """
    Generate hybrid embeddings for multiple texts in parallel.

    Args:
        texts: List of texts to embed
        max_workers: Number of concurrent workers for dense embeddings (default 25)
        progress_callback: Optional callback for progress updates

    Returns:
        List of (dense_vector, sparse_vector) tuples in same order as input
    """
    if not texts:
        return []

    dense_embeddings = generate_dense_embeddings_batch(
        texts, max_workers=max_workers, progress_callback=progress_callback
    )
    sparse_embeddings = generate_sparse_embeddings_batch(texts)

    return list(zip(dense_embeddings, sparse_embeddings))
