import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastembed import SparseTextEmbedding
from openai import APIConnectionError, APITimeoutError, AzureOpenAI, RateLimitError
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

# Parallelism config - keep low to avoid Azure OpenAI rate limits
DEFAULT_MAX_WORKERS = int(os.environ.get("EMBEDDING_MAX_WORKERS", "5"))

# Azure OpenAI supports up to 2048 texts per request, but large batches can
# hit token limits. 100 is a safe default that balances throughput and reliability.
DENSE_BATCH_CHUNK_SIZE = 100


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
                logger.info("Azure OpenAI client initialised")
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


def generate_dense_embedding_with_retry(text: str, max_retries: int = MAX_RETRIES) -> list[float]:
    """Generate dense embedding for a single text with retry logic.

    For batch embedding, prefer generate_dense_embeddings_batch() which uses
    the native batch API for dramatically better throughput.
    """
    results = _embed_dense_chunk([text], max_retries=max_retries)
    return results[0]


def _embed_dense_chunk(
    texts: list[str], max_retries: int = MAX_RETRIES
) -> list[list[float]]:
    """Send a chunk of texts to Azure OpenAI embeddings API in a single request.

    Args:
        texts: List of texts to embed (should be <= DENSE_BATCH_CHUNK_SIZE).
        max_retries: Maximum retry attempts on transient errors.

    Returns:
        List of embedding vectors in the same order as input texts.
    """
    # Truncate very long texts (OpenAI limit ~8K tokens per text ≈ 30K chars)
    truncated = [t[:30000] if len(t) > 30000 else t for t in texts]

    client = get_openai_client()

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_DEPLOYMENT, input=truncated, dimensions=EMBEDDING_DIMENSIONS
            )
            # API returns embeddings sorted by index, but sort explicitly to be safe
            sorted_data = sorted(response.data, key=lambda d: d.index)
            return [d.embedding for d in sorted_data]

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            if attempt == max_retries - 1:
                logger.error(
                    f"Failed to generate dense embeddings for {len(texts)} texts "
                    f"after {max_retries} retries: {e}"
                )
                raise

            backoff = min(BASE_BACKOFF * (2**attempt), MAX_BACKOFF)
            jitter = random.uniform(0, backoff * 0.1)
            sleep_time = backoff + jitter
            error_type = type(e).__name__
            logger.warning(
                f"{error_type}: {e}, retrying in {sleep_time:.1f}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Non-retryable error generating embeddings: {type(e).__name__}: {e}")
            raise

    raise Exception(f"Failed to generate embeddings after {max_retries} retries")


def generate_dense_embedding(text: str) -> list[float]:
    """Generate dense embedding (use generate_dense_embeddings_batch for bulk work).

    Args:
        text: Text to embed

    Returns:
        1024-dimensional vector
    """
    return generate_dense_embedding_with_retry(text)


def generate_dense_embeddings_batch(
    texts: list[str], max_workers: int | None = None, progress_callback=None
) -> list[list[float]]:
    """Generate dense embeddings using native batch API with parallel chunking.

    Splits texts into chunks of DENSE_BATCH_CHUNK_SIZE and sends each chunk
    as a single API request. Chunks are processed in parallel using a thread pool.

    Args:
        texts: List of texts to embed
        max_workers: Number of concurrent chunk requests (default from EMBEDDING_MAX_WORKERS env or 5)
        progress_callback: Optional callback function(completed_count) for progress updates

    Returns:
        List of 1024-dimensional vectors in same order as input texts
    """
    if not texts:
        return []

    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS

    # Split into chunks for batch API requests
    chunks = [
        texts[i : i + DENSE_BATCH_CHUNK_SIZE]
        for i in range(0, len(texts), DENSE_BATCH_CHUNK_SIZE)
    ]

    # Single chunk — no need for thread pool overhead
    if len(chunks) == 1:
        results = _embed_dense_chunk(chunks[0])
        if progress_callback:
            progress_callback(len(results))
        return results

    # Multiple chunks — process in parallel
    all_results: list[list[float] | None] = [None] * len(texts)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_offset = {
            executor.submit(_embed_dense_chunk, chunk): i * DENSE_BATCH_CHUNK_SIZE
            for i, chunk in enumerate(chunks)
        }

        for future in as_completed(future_to_offset):
            offset = future_to_offset[future]
            try:
                chunk_results = future.result()
                for j, embedding in enumerate(chunk_results):
                    all_results[offset + j] = embedding
                completed += len(chunk_results)

                if progress_callback:
                    progress_callback(completed)

            except Exception as e:
                # Fill failed chunk with zero vectors
                chunk_size = min(DENSE_BATCH_CHUNK_SIZE, len(texts) - offset)
                logger.error(
                    f"Failed to generate embeddings for chunk at offset {offset} "
                    f"({chunk_size} texts): {e}"
                )
                for j in range(chunk_size):
                    all_results[offset + j] = [0.0] * EMBEDDING_DIMENSIONS
                completed += chunk_size

    return all_results  # type: ignore[return-value]


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


def generate_sparse_embeddings_batch(texts: list[str]) -> list[SparseVector]:
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


def generate_hybrid_embeddings(text: str) -> tuple[list[float], SparseVector]:
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


async def generate_hybrid_embeddings_async(text: str) -> tuple[list[float], SparseVector]:
    """Async version: runs dense (network) and sparse (CPU) concurrently off the event loop."""
    import asyncio

    dense, sparse = await asyncio.gather(
        asyncio.to_thread(generate_dense_embedding, text),
        asyncio.to_thread(generate_sparse_embedding, text),
    )
    return dense, sparse


def generate_hybrid_embeddings_batch(
    texts: list[str], max_workers: int | None = None, progress_callback=None
) -> list[tuple[list[float], SparseVector]]:
    """
    Generate hybrid embeddings for multiple texts in parallel.

    Args:
        texts: List of texts to embed
        max_workers: Number of concurrent workers (default from EMBEDDING_MAX_WORKERS env or 5)
        progress_callback: Optional callback for progress updates

    Returns:
        List of (dense_vector, sparse_vector) tuples in same order as input
    """
    if not texts:
        return []

    if max_workers is None:
        max_workers = DEFAULT_MAX_WORKERS

    dense_embeddings = generate_dense_embeddings_batch(
        texts, max_workers=max_workers, progress_callback=progress_callback
    )
    sparse_embeddings = generate_sparse_embeddings_batch(texts)

    return list(zip(dense_embeddings, sparse_embeddings))
