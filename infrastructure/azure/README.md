# Lex API Azure Deployment

Deploy the Lex FastAPI backend with MCP server to Azure Container Apps and API Management.

Built by the [Incubator for AI](https://ai.gov.uk) to harness AI for public good.

## Architecture

- **Azure Container Apps**: Hosts the FastAPI backend with scale-to-zero
- **Azure API Management Basic V2**: Provides rate limiting, documentation, and API gateway
- **Azure Container Registry**: Stores the container images with admin credentials
- **Application Insights**: Monitoring and telemetry

## Rate Limits

- **20 requests per minute** per IP address (1200/hour)
- **100 requests per 5 minutes** per IP address (sustained rate)
- 429 responses with retry headers when limits exceeded
- No API keys required - free for all researchers

## Prerequisites

- Azure CLI installed and logged in
- Docker installed
- Access to the `rg-lex` resource group

## Quick Deployment

```bash
# Deploy to production
./deploy.sh

# Deploy to staging
ENVIRONMENT=staging ./deploy.sh

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
    environment=prod \
    containerImage=your-registry.azurecr.io/lex-backend:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RESOURCE_GROUP` | `rg-lex` | Azure resource group |
| `LOCATION` | `uksouth` | Azure region |
| `APPLICATION_NAME` | `lex` | Application name prefix |
| `ENVIRONMENT` | `prod` | Environment (dev/staging/prod) |
| `SUBSCRIPTION_ID` | (current) | Azure subscription ID |

## API Endpoints

After deployment, the API will be available through API Management at:

- **Health Check**: `GET /healthcheck`
- **Legislation Search**: `POST /legislation/search`
- **Section Search**: `POST /legislation/section/search`
- **Caselaw Search**: `POST /caselaw/search`
- **MCP Server**: Direct to Container App at `/mcp` (for AI agents)

### Rate Limited Access
All endpoints go through API Management with IP-based rate limiting.

## MCP Integration

The deployment exposes an MCP (Model Context Protocol) server for AI agents with two configuration options:

### Option 1: Direct Container App Access
Use the direct Container App URL for immediate access:
```json
{
  "mcpServers": {
    "lex": {
      "command": "uvx",
      "args": ["mcp-proxy", "https://your-app-name.region.azurecontainerapps.io/mcp"]
    }
  }
}
```

### Option 2: Azure API Management MCP Server (Recommended)
For enterprise governance and enhanced security, configure the MCP server through Azure API Management:

#### Prerequisites
- Azure API Management Basic V2, Standard V2, or Premium V2 tier
- Join the "AI Gateway Early update group" if using classic tiers

#### Configuration Steps
1. **Access Preview Features**: Navigate to Azure Portal with MCP feature flag:
   ```
   https://portal.azure.com?Microsoft_Azure_ApiManagement=mcp
   ```

2. **Navigate to MCP Configuration**:
   - Go to your API Management instance (`lex-prod-apim`)
   - Under "APIs", select "MCP servers"
   - Click "+ Create MCP server"

3. **Configure Existing MCP Server**:
   - Choose "Expose an existing MCP server"
   - **MCP server base URL**: `https://your-app-name.region.azurecontainerapps.io/mcp`
   - **Transport type**: "Streamable HTTP"
   - **Name**: `lex-research-mcp`
   - **Base path**: `/mcp-tools`
   - **Description**: `Lex Research API - UK Legal Data MCP Server for AI Agents`

4. **Apply MCP Policies**: Copy the policy configuration from [`mcp-server-policy.xml`](mcp-server-policy.xml) to your MCP server policies section

5. **Use Enhanced MCP Endpoint**:
   ```json
   {
     "mcpServers": {
       "lex": {
         "command": "uvx",
         "args": ["mcp-proxy", "https://lex-prod-apim.azure-api.net/mcp-tools"]
       }
     }
   }
   ```

#### Benefits of API Management MCP Configuration
- ✅ **Enterprise Governance**: Rate limiting, authentication, and monitoring
- ✅ **Enhanced Security**: JWT authentication, IP filtering, policy enforcement
- ✅ **Better Monitoring**: Azure Monitor integration, correlation IDs
- ✅ **Standardized Discovery**: AI agents can discover tools through API Management
- ✅ **MCP Protocol Compliance**: Supports MCP version 2025-06-18

## Monitoring

- **Application Insights**: Automatic logging and telemetry
- **Container Apps**: Built-in metrics and scaling
- **API Management**: Request analytics and rate limit monitoring

## Scaling

The Container Apps deployment:
- Scales to zero when idle (cost savings)
- Scales up to 10 instances based on HTTP requests
- 50 concurrent requests per instance trigger scaling

## Cost Optimization

- Container Apps: Pay only for active usage
- API Management Basic V2: Fixed monthly cost
- Application Insights: Pay per data ingested
- Container Registry: Storage costs only

## Support

For questions or issues:
- GitHub: [github.com/i-dot-ai/lex](https://github.com/i-dot-ai/lex)
- Email: [lex@cabinetoffice.gov.uk](mailto:lex@cabinetoffice.gov.uk)
- Website: [ai.gov.uk](https://ai.gov.uk)