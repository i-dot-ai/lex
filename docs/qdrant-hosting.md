# Qdrant Cloud Hosting Cost Estimate

**Last Updated:** October 2025

## Dataset Overview

- **Total Vectors:** ~4M points across 7 collections
  - legislation_section: 997,461
  - caselaw_section: 2,403,490
  - embedding_cache: 333,000+
  - legislation: 125,255
  - explanatory_note: 82,344
  - caselaw: 30,512
  - amendment: 32

- **Vector Dimensions:** 1024D dense (text-embedding-3-large) + ~200D sparse (BM25)
- **Payload Size:** ~3 KB average per document (full text + metadata)

## Cloud Configuration

### Recommended Setup (Production)

**Region:** UK South (uksouth)

**Resources:**
- RAM: 4 GiB
- vCPUs: 1.0 vCPU
- Disk Space: 16 GiB
- Nodes: 1 Node
- Replication Factor: 1

**Quantization:** Scalar (INT8)
- Reduces vector storage by ~60%
- Minimal accuracy impact (<2%)
- Essential for cost-effective hosting

### Cost Breakdown

**Hourly:** $0.0822/hour

**Monthly:** $60.17/month*

*\* Approximated average price. VAT excluded.*

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

After migration, enable scalar quantization per collection:

```python
from qdrant_client import models

qdrant_client.update_collection(
    collection_name="legislation_section",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=True
        )
    )
)
```

## Alternative: Self-Hosted

For comparison, running Qdrant on your own infrastructure:
- Similar specs on AWS EC2 t3.medium: ~$30-35/month
- Azure B2s: ~$35-40/month
- Requires managing updates, monitoring, backups yourself

Qdrant Cloud premium: $60/month vs self-hosted: ~$35/month = **$25/month convenience premium**

## References

- [Qdrant Pricing Calculator](https://qdrant.tech/pricing/)
- [Quantization Guide](https://qdrant.tech/documentation/guides/quantization/)
- [Cloud Documentation](https://qdrant.tech/documentation/cloud/)
