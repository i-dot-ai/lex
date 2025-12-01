# Qdrant Cloud Hosting Cost Estimate

**Last Updated:** November 2025

## Dataset Overview

- **Total Vectors:** ~5M points across 7 collections
  - caselaw_section: 2,403,490
  - legislation_section: 1,472,584
  - amendment: 892,210
  - legislation: 155,989
  - explanatory_note: 82,344
  - caselaw: 30,512
  - embedding_cache: 333,000+

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

**Quantization:** Scalar (INT8)
- Reduces vector storage by ~60%
- Minimal accuracy impact (<2%)
- Essential for cost-effective hosting

### Cost Breakdown

**Monthly:** ~$200-250/month (16GB RAM tier)

*VAT excluded. Check [Qdrant pricing](https://qdrant.tech/pricing/) for current rates.*

## Storage Requirements

### With Scalar Quantization (Recommended)
- Dense vectors: ~4 GB (quantized from 16 GB)
- Sparse vectors: ~3.2 GB (cannot quantize)
- Payload data: ~12 GB
- **Total: ~19 GB**

### Without Quantization
- Dense vectors: ~16 GB
- Sparse vectors: ~3.2 GB
- Payload data: ~12 GB
- **Total: ~31 GB**

## Cost Optimization Notes

1. **Scalar Quantization is Critical**
   - Saves ~$20-25/month by reducing required disk/RAM
   - Enable per-collection after initial migration
   - Negligible quality impact for legal search

2. **Single-Node is Adequate for Dev/Staging**
   - Production may want replication_factor=2 for HA (doubles cost to ~$120/month)

3. **Disk Space Buffer**
   - Current dataset: ~19 GB with quantization
   - Recommended provision: 24-32 GB for growth headroom

4. **Regional Considerations**
   - UK South chosen for data residency (UK legal documents)
   - Other regions may have different pricing

## Enabling Quantization

Quantization is enabled by default in schema files (`src/lex/*/qdrant_schema.py`).

To enable on existing collections, run:

```bash
uv run python scripts/enable_quantization.py
```

Collections transition: grey → yellow (optimising) → green (complete).

**Warning:** Optimisation temporarily increases memory usage. With 5M points, 4GB RAM causes OOM. Use 16GB+ during index rebuilds.

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
