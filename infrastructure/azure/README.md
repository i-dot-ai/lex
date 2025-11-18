# Lex API Azure Deployment

Deploy the Lex FastAPI backend with MCP server to Azure Container Apps.

Built by the [Incubator for AI](https://ai.gov.uk) to harness AI for public good.

## Architecture

- **Azure Container Apps**: Hosts the FastAPI backend with scale-to-zero
- **Azure Cache for Redis**: Caching and rate limiting
- **Azure Container Registry**: Stores the container images
- **Application Insights**: Monitoring and telemetry
- **Static Files**: Documentation served directly from Container App

## Rate Limits

- **60 requests per minute** per IP address
- **1000 requests per hour** per IP address
- 429 responses with retry headers when limits exceeded
- No API keys required - rate limited for public use

## Prerequisites

- Azure CLI installed and logged in
- Docker installed
- Access to the `rg-lex` resource group
- `.env` file with required credentials

## Quick Deployment

```bash
# Deploy to production
./deploy.sh

# Deploy with custom resource group
RESOURCE_GROUP=my-rg ./deploy.sh
```

## Manual Deployment

```bash
# 1. Build and push container image
az acr login --name your-registry
docker build -f src/backend/Dockerfile -t your-registry.azurecr.io/lex-backend:latest .
docker push your-registry.azurecr.io/lex-backend:latest

# 2. Deploy infrastructure
az deployment group create \
  --resource-group rg-lex \
  --template-file main.bicep \
  --parameters \
    applicationName=lex \
    containerImage=your-registry.azurecr.io/lex-backend:latest \
    qdrantCloudUrl="your-qdrant-url" \
    qdrantCloudApiKey="your-qdrant-key" \  # pragma: allowlist secret
    azureOpenAIApiKey="your-openai-key" \  # pragma: allowlist secret
    azureOpenAIEndpoint="your-openai-endpoint"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RESOURCE_GROUP` | `rg-lex` | Azure resource group |
| `LOCATION` | `uksouth` | Azure region |
| `APPLICATION_NAME` | `lex` | Application name prefix |
| `SUBSCRIPTION_ID` | (current) | Azure subscription ID |

## Required .env Variables

```bash
QDRANT_CLOUD_URL=https://your-cluster.cloud.qdrant.io:6333
QDRANT_CLOUD_API_KEY=your-api-key
AZURE_OPENAI_API_KEY=your-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

## API Endpoints

After deployment, the API will be available at the Container App URL:

- **Root**: Documentation webpage
- **Health Check**: `GET /healthcheck`
- **API Docs**: `GET /api/docs`
- **Legislation Search**: `POST /legislation/search`
- **Section Search**: `POST /legislation/section/search`
- **Caselaw Search**: `POST /caselaw/search`
- **MCP Server**: `GET/POST /mcp`

## MCP Integration

Configure Claude Desktop to use the MCP server:

```json
{
  "mcpServers": {
    "lex-research": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://your-app-name.region.azurecontainerapps.io/mcp"]
    }
  }
}
```

## Monitoring

- **Application Insights**: Automatic logging and telemetry
- **Container Apps**: Built-in metrics and scaling
- **Redis Cache**: Connection and performance metrics

## Scaling

The Container Apps deployment:

- Scales to zero when idle (cost savings)
- Scales up to 10 instances based on HTTP requests
- 50 concurrent requests per instance trigger scaling

## Support

For questions or issues:

- GitHub: [github.com/i-dot-ai/lex](https://github.com/i-dot-ai/lex)
- Email: [lex@cabinetoffice.gov.uk](mailto:lex@cabinetoffice.gov.uk)
- Website: [ai.gov.uk](https://ai.gov.uk)
