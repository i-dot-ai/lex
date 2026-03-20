# Qdrant Cloud Hosting Cost Estimate

Cost analysis for Qdrant Cloud deployment. For the system overview, see [system-architecture.md](system-architecture.md). For search performance characteristics, see [search-architecture.md](search-architecture.md).

**Last Updated:** March 2026

## Dataset Overview

- **Total Vectors:** ~8.4M points across 8 collections
  - caselaw_section: 4,723,735
  - legislation_section: 2,098,225
  - amendment: 892,210
  - embedding_cache: 238,600
  - legislation: 219,685
  - explanatory_note: 88,956
  - caselaw: 69,970
  - caselaw_summary: 61,107

- **Vector Dimensions:** 1024D dense (text-embedding-3-large) + ~200D sparse (BM25)
- **Payload Size:** ~3 KB average per document (full text + metadata)

## Cloud Configuration

### Recommended Setup (Production)

**Region:** UK South (uksouth)

**Resources:**
- RAM: 16 GiB (minimum for quantization with `always_ram=True`)
- vCPUs: 4
- Disk Space: 128 GiB
- Nodes: 1 Node
- Replication Factor: 1

**Note:** Quantization optimisation requires extra RAM headroom. 4GB causes OOM during index rebuilds.

**Quantisation:** Scalar (INT8)
- Reduces vector storage by ~60%
- Minimal accuracy impact (<2%)
- Essential for cost-effective hosting

### Cost Breakdown

**Monthly:** ~$200-250/month (16GB RAM tier)

*VAT excluded. Check [Qdrant pricing](https://qdrant.tech/pricing/) for current rates.*

## Storage Requirements

### With Scalar Quantisation (Recommended)
- Dense vectors: ~8 GB (quantised from ~32 GB)
- Sparse vectors: ~5 GB (cannot quantise)
- Payload data: ~20 GB
- **Total: ~33 GB**

### Without Quantisation
- Dense vectors: ~32 GB
- Sparse vectors: ~5 GB
- Payload data: ~20 GB
- **Total: ~57 GB**

## Cost Optimisation Notes

1. **Scalar Quantisation is Critical**
   - Saves ~$20-25/month by reducing required disk/RAM
   - Enable per-collection after initial migration
   - Negligible quality impact for legal search

2. **Single-Node is Adequate for Dev/Staging**
   - Production may want replication_factor=2 for HA (doubles cost to ~$120/month)

3. **Disk Space Buffer**
   - Current dataset: ~33 GB with quantisation
   - Recommended provision: 48-64 GB for growth headroom

4. **Regional Considerations**
   - UK South chosen for data residency (UK legal documents)
   - Other regions may have different pricing

## Enabling Quantisation

Quantisation is enabled by default in schema files (`src/lex/*/qdrant_schema.py`).

To enable on existing collections, run:

```bash
uv run python scripts/maintenance/enable_quantization.py
```

Collections transition: grey → yellow (optimising) → green (complete).

**Warning**: Optimisation temporarily increases memory usage. With 8M+ points, 4GB RAM causes OOM. Use 16GB+ during index rebuilds.

## Troubleshooting

### Grey Collection Status
If a Qdrant node restarts during optimisation, collections may go "grey" (paused). Trigger optimisers to resume:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import OptimizersConfigDiff

client = QdrantClient(url=QDRANT_URL, api_key=API_KEY)
client.update_collection(
    collection_name="collection_name",
    optimizers_config=OptimizersConfigDiff(indexing_threshold=10000)
)
```

### Check Status
```python
for name in collections:
    info = client.get_collection(name)
    print(f'{name}: {info.status}')  # green = ready, yellow = optimising, grey = paused
```

## Alternative: Self-Hosted

For comparison, running Qdrant on your own infrastructure:
- Similar specs on AWS EC2: ~$100-150/month (16GB RAM instance)
- Azure: ~$120-180/month
- Requires managing updates, monitoring, backups yourself

## References

- [Qdrant Pricing Calculator](https://qdrant.tech/pricing/)
- [Quantization Guide](https://qdrant.tech/documentation/guides/quantization/)
- [Cloud Documentation](https://qdrant.tech/documentation/cloud/)
