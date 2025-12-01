# Search Architecture

Why Lex uses hybrid search and how it works.

## The Problem

Legal search needs both:
- **Exact keyword matching** - finding "Section 3(2)(a)"
- **Semantic understanding** - finding "intellectual property infringement"

Single-method approaches fail:
- Dense-only: misses exact citations
- Sparse-only: can't understand synonyms or concepts

## The Solution: Hybrid Vectors

### Dense Vectors (1024D Azure OpenAI)
- Semantic meaning and conceptual relationships
- Understands synonyms: "IP" ↔ "copyright" ↔ "patents"
- Works across vocabulary mismatches

### Sparse Vectors (BM25 via FastEmbed)
- Exact term matching for citations
- Predictable, explainable results
- No model training required
- 10% storage vs dense vectors

**Code**: `src/lex/core/embeddings.py`

## Fusion Strategies

### DBSF for Legislation

**Distribution-Based Score Fusion** uses statistical normalization:
1. Normalizes scores using mean ± 3σ
2. Maps to [0, 1] range
3. Sums normalized scores

**Why**: Better for legislation where semantic understanding matters alongside exact matching.

**Ratio**: 3x dense, 0.8x sparse (dense-favoring)

**Code**: `src/backend/legislation/search.py:334`

### RRF for Caselaw

**Reciprocal Rank Fusion** uses rank positions:
1. Converts scores to ranks (1st, 2nd, 3rd)
2. Calculates `1/(rank + 60)` for each
3. Sums reciprocal ranks

**Why**: Simpler, no tuning needed, works universally.

**Code**: `src/backend/caselaw/search.py:82`

## Performance Optimizations

### 1. Scalar Quantization (INT8)
All collections use INT8 scalar quantization:
- **4x memory reduction** (float32 → int8)
- **20-50% faster searches** (fewer memory transfers)
- **<1% accuracy loss** (Qdrant rescores with original vectors)

Config: `quantile=0.99, always_ram=True`

**Memory sizing** (5M points, 1024D):
- Original vectors: ~20GB (float32)
- Quantized vectors: ~5GB (int8, kept in RAM)
- Sparse + HNSW overhead: ~3-5GB
- **Minimum RAM**: 16GB recommended

**Script**: `scripts/enable_quantization.py`

### 2. Reduced Section Limit
```python
# Reduced from 500 to 200 sections
# 60% faster queries, no quality loss
```

### 3. Exclude Text Payloads
```python
# When include_text=False
# 60% faster, 90% less data transfer
```

### 4. Embedding Cache
- Qdrant collection with 333K+ cached embeddings
- O(1) lookup via UUID5(SHA-256(query))
- **35x speedup** for repeated queries

**Code**: `src/lex/core/embedding_cache.py`

## Performance Characteristics

**Measured latencies** (November 2025, post-quantization):

| Endpoint | Latency |
|----------|---------|
| `/legislation/search` | ~3s |
| `/legislation/section/search` | ~0.6s |
| `/caselaw/search` | ~3.4s |
| `/caselaw/reference` | ~0.2s |
| `/amendment/search` | ~0.15s |
| `/explanatory_note/section/search` | ~2s |

**Breakdown**:
- Embedding generation: 50-100ms (cached: <5ms)
- Qdrant vector search: 150-500ms
- Result aggregation + metadata: varies by endpoint

**Relevance**:
- Semantic queries: 90%+ relevant in top 10
- Exact citations: 100% precision (BM25)
- Mixed queries: 85%+ relevant

## Known Limitations

**1. Very Short Queries** (1-2 words)
- Insufficient context for semantic understanding
- BM25 provides baseline relevance

**2. Negation**
- Embeddings don't capture "NOT" logic well
- Example: "copyright but not trademarks" still returns trademarks

**3. Archaic Legal Language**
- Pre-1900 acts use obsolete terminology
- BM25 catches exact terms, semantics struggle

**4. Large Documents**
- Truncation at 30K chars (OpenAI limit)
- Long judgments split into paragraph sections

## Trade-offs

### What We Gave Up
- **Storage**: 32GB vs 8GB (sparse-only) for 4M points
- **Latency**: 250ms vs 80ms (BM25-only)
- **Complexity**: Two models, two fusion algorithms

### What We Gained
- **Relevance**: 2x better across diverse query types
- **No tuning**: RRF/DBSF work out-of-the-box
- **Future-proof**: Can swap models without reindexing
- **Scalability**: Handles 4M points, sub-200ms cached

## Why This Matters

Research confirms hybrid search outperforms single methods:
- IBM: "three-way retrieval is optimal for RAG"
- Microsoft: "RRF gives improved relevance"
- Lex testing: DBSF outperforms RRF for legislation

**Worth it**: Relevance quality impossible with single-method search.

## Code References

**Core Implementation**:
- `src/lex/core/embeddings.py` - Dense + sparse generation
- `src/lex/core/embedding_cache.py` - Qdrant caching
- `src/backend/legislation/search.py:270-388` - DBSF fusion
- `src/backend/caselaw/search.py:54-118` - RRF fusion

**Vector Config**:
- `src/lex/*/qdrant_schema.py` - Collection schemas
- 1024D COSINE (dense), BM25 DOT (sparse)
- In-memory sparse index for speed
