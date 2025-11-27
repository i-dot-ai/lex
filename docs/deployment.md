# Deployment Guide

Deploy Lex to run your own instance of the UK legal data API.

## Deployment Options

| Option | Best For | Database | Cost |
|--------|----------|----------|------|
| **Docker Compose** | Local development, testing | Local Qdrant | Free |
| **Azure** | Production, public API | Qdrant Cloud | ~£175/month |

This guide covers Azure and Docker Compose. The architecture can be adapted to **AWS**, **GCP**, or **Kubernetes** - we welcome PRs for additional deployment targets.

---

## Docker Compose (Local)

Run Lex locally with Docker Compose for development or private use.

### Prerequisites

- Docker & Docker Compose
- Azure OpenAI credentials (for embeddings)
- 8GB+ RAM recommended

### Setup

```bash
# Clone repository
git clone https://github.com/i-dot-ai/lex.git && cd lex

# Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI credentials

# Start services
docker compose up -d

# Load sample data
make ingest-all-sample

# Visit http://localhost:8000
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| Backend | 8000 | FastAPI + MCP server |
| Qdrant | 6333 | Vector database |
| Pipeline | - | Data ingestion worker |

### Data Ingestion

```bash
# Sample data (quick testing)
make ingest-all-sample

# Full dataset (production use - takes several hours)
make ingest-all-full

# Individual collections
make ingest-legislation-sample
make ingest-caselaw-sample
```

### Environment Variables

```bash
# Required
AZURE_OPENAI_API_KEY=your-key
AZURE_RESOURCE_NAME=your-resource-name
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Optional
USE_CLOUD_QDRANT=false          # Use local Qdrant
ENVIRONMENT=localhost
```

---

## Azure (Production)

Deploy to Azure Container Apps with Qdrant Cloud for a production-ready public API.

### Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Container App  │────▶│  Qdrant Cloud   │
│  (FastAPI+MCP)  │     │                 │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Redis Cache    │     │ App Insights    │
│  (Rate Limits)  │     │ (Monitoring)    │
└─────────────────┘     └─────────────────┘
```

### Prerequisites

- Azure CLI installed and logged in (`az login`)
- Docker installed
- Qdrant Cloud account with cluster
- Azure OpenAI credentials

### Setup

1. **Configure environment**

```bash
cp .env.example .env
```

Edit `.env` with production credentials:

```bash
# Qdrant Cloud
QDRANT_CLOUD_URL=https://your-cluster.cloud.qdrant.io:6333
QDRANT_CLOUD_API_KEY=your-qdrant-api-key

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Analytics (optional)
POSTHOG_KEY=your-posthog-key
POSTHOG_HOST=https://eu.i.posthog.com
```

2. **Deploy**

```bash
./infrastructure/azure/deploy.sh
```

The script will:
- Build and push container image to Azure Container Registry
- Deploy infrastructure via Bicep template
- Configure secrets and environment variables
- Output the deployment URLs

3. **Verify deployment**

```bash
curl https://your-app.azurecontainerapps.io/healthcheck
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RESOURCE_GROUP` | `rg-lex` | Azure resource group |
| `LOCATION` | `uksouth` | Azure region |
| `APPLICATION_NAME` | `lex` | Resource name prefix |

### Resources Created

- **Container App**: Hosts the API with auto-scaling (1-10 instances)
- **Container Registry**: Stores Docker images
- **Redis Cache**: Rate limiting and caching
- **Log Analytics**: Centralised logging
- **Application Insights**: Performance monitoring

### Rate Limits

Default rate limits (configurable in Bicep):

- 60 requests per minute per IP
- 1000 requests per hour per IP

### Scaling

The Container App scales automatically:
- Minimum: 1 replica (always warm)
- Maximum: 10 replicas
- Scale trigger: 50 concurrent requests per instance

### Costs

Estimated monthly cost: **~£175/month**

This includes Container App, Redis Cache, Container Registry, Log Analytics, Application Insights, and Qdrant Cloud. Costs may increase with higher traffic as the Container App scales and log volume grows.

---

## Populating Data

After deployment, populate the vector database:

### Using Qdrant Cloud (Recommended)

Contact the Lex team for access to the production dataset snapshot, or run the ingestion pipeline yourself.

### Self-Hosted Ingestion

```bash
# Run locally with cloud Qdrant
USE_CLOUD_QDRANT=true docker compose up -d

# Ingest full dataset (8+ hours)
make ingest-all-full

# Create performance indexes
uv run python scripts/create_payload_indexes.py
```

---

## Adapting to Other Platforms

### AWS

Replace Azure-specific components:
- Container App → ECS Fargate or Lambda
- Redis Cache → ElastiCache
- Container Registry → ECR
- Application Insights → CloudWatch

### GCP

Replace Azure-specific components:
- Container App → Cloud Run
- Redis Cache → Memorystore
- Container Registry → Artifact Registry
- Application Insights → Cloud Monitoring

### Kubernetes

Use the backend Dockerfile directly:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lex-api
spec:
  template:
    spec:
      containers:
      - name: lex-backend
        image: your-registry/lex-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: USE_CLOUD_QDRANT
          value: "true"
        # ... other env vars
```

---

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues.

## Support

- GitHub: [github.com/i-dot-ai/lex](https://github.com/i-dot-ai/lex)
- Website: [ai.gov.uk](https://ai.gov.uk)
