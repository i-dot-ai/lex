#!/bin/bash

# Lex API Deployment Script
# Deploy FastAPI backend + MCP server to Azure
# Built by the Incubator for AI

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-lex}"
LOCATION="${LOCATION:-uksouth}"
APPLICATION_NAME="${APPLICATION_NAME:-lex}"
SUBSCRIPTION_ID="${SUBSCRIPTION_ID:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Please run 'az login' first."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Set subscription
set_subscription() {
    if [ -n "$SUBSCRIPTION_ID" ]; then
        log_info "Setting subscription to $SUBSCRIPTION_ID"
        az account set --subscription "$SUBSCRIPTION_ID"
    else
        log_info "Using current subscription: $(az account show --query name -o tsv)"
    fi
}

# Build and push container image
build_and_push_image() {
    {
        log_info "Building and pushing container image..."
        
        # Get container registry name (assumes it exists in the resource group)
        ACR_NAME=$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || echo "")
        
        if [ -z "$ACR_NAME" ]; then
            log_warning "No Azure Container Registry found. Creating one..."
            ACR_NAME="${APPLICATION_NAME}acr"
            az acr create \
                --resource-group "$RESOURCE_GROUP" \
                --name "$ACR_NAME" \
                --sku Basic \
                --location "$LOCATION" >/dev/null
        fi
        
        log_info "Using Azure Container Registry: $ACR_NAME"
        
        # Login to ACR
        az acr login --name "$ACR_NAME" >/dev/null
        
        # Build and push image
        IMAGE_TAG="${ACR_NAME}.azurecr.io/lex-backend:latest"
        
        log_info "Building image: $IMAGE_TAG"
        docker build --platform linux/amd64 -f src/backend/Dockerfile -t "$IMAGE_TAG" . >/dev/null
        
        log_info "Pushing image to registry..."
        docker push "$IMAGE_TAG" >/dev/null
        
        log_success "Container image built and pushed successfully"
    } >&2
    
    # Return only the image tag
    echo "${ACR_NAME}.azurecr.io/lex-backend:latest"
}

# Deploy infrastructure
deploy_infrastructure() {
    local container_image="$1"
    
    log_info "Deploying infrastructure..."
    
    # Load credentials from .env file
    if [ -f ".env" ]; then
        QDRANT_CLOUD_URL=$(grep "^QDRANT_CLOUD_URL=" .env | cut -d '=' -f2)
        QDRANT_CLOUD_API_KEY=$(grep "^QDRANT_CLOUD_API_KEY=" .env | cut -d '=' -f2)
        AZURE_OPENAI_API_KEY=$(grep "^AZURE_OPENAI_API_KEY=" .env | cut -d '=' -f2)
        AZURE_OPENAI_ENDPOINT=$(grep "^AZURE_OPENAI_ENDPOINT=" .env | cut -d '=' -f2)
        AZURE_OPENAI_EMBEDDING_MODEL=$(grep "^AZURE_OPENAI_EMBEDDING_MODEL=" .env | cut -d '=' -f2)
    fi
    
    # Set default embedding model if not specified
    AZURE_OPENAI_EMBEDDING_MODEL="${AZURE_OPENAI_EMBEDDING_MODEL:-text-embedding-3-large}"
    
    if [ -z "$QDRANT_CLOUD_URL" ] || [ -z "$QDRANT_CLOUD_API_KEY" ]; then
        log_error "QDRANT_CLOUD_URL and QDRANT_CLOUD_API_KEY must be set in .env file"
        exit 1
    fi
    
    if [ -z "$AZURE_OPENAI_API_KEY" ] || [ -z "$AZURE_OPENAI_ENDPOINT" ]; then
        log_error "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in .env file"
        exit 1
    fi
    
    # Deploy using Bicep
    az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --template-file infrastructure/azure/main.bicep \
        --parameters \
            applicationName="$APPLICATION_NAME" \
            location="$LOCATION" \
            containerImage="$container_image" \
            qdrantCloudUrl="$QDRANT_CLOUD_URL" \
            qdrantCloudApiKey="$QDRANT_CLOUD_API_KEY" \
            azureOpenAIApiKey="$AZURE_OPENAI_API_KEY" \
            azureOpenAIEndpoint="$AZURE_OPENAI_ENDPOINT" \
            azureOpenAIEmbeddingModel="$AZURE_OPENAI_EMBEDDING_MODEL"
    
    log_success "Infrastructure deployment completed"
}

# Get deployment outputs
get_outputs() {
    log_info "Getting deployment outputs..."
    
    # Get latest deployment
    DEPLOYMENT_NAME=$(az deployment group list \
        --resource-group "$RESOURCE_GROUP" \
        --query "[0].name" -o tsv)
    
    if [ -n "$DEPLOYMENT_NAME" ]; then
        CONTAINER_APP_URL=$(az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs.containerAppUrl.value" -o tsv)
        
        MCP_ENDPOINT_URL=$(az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs.mcpEndpointUrl.value" -o tsv)
        
        API_DOCS_URL=$(az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs.apiDocsUrl.value" -o tsv)
        
        echo ""
        log_success "Simplified Lex API deployment completed successfully!"
        echo ""
        echo "🌐 Container App URL: $CONTAINER_APP_URL"
        echo "📚 Documentation: $CONTAINER_APP_URL (root page)"
        echo "🔧 API Documentation: $API_DOCS_URL"
        echo "🤖 MCP Server URL: $MCP_ENDPOINT_URL"
        echo ""
        echo "🔗 Try the API:"
        echo "  curl $CONTAINER_APP_URL/healthcheck"
        echo ""
        echo "📖 View documentation:"
        echo "  Open $CONTAINER_APP_URL"
        echo ""
        echo "🤖 Add MCP server to Claude Desktop:"
        echo '  {'
        echo '    "mcpServers": {'
        echo '      "lex-research": {'
        echo '        "command": "npx",'
        echo "        \"args\": [\"-y\", \"mcp-remote@latest\", \"$MCP_ENDPOINT_URL\"]"
        echo '      }'
        echo '    }'
        echo '  }'
        echo ""
        log_success "✅ No more API Management or Storage Account needed!"
        echo "💰 Cost reduced by ~£200/month"
        echo "🚀 Better performance with direct Container App access"
        echo "🔧 No more 64KB response truncation issues"
        echo ""
    fi
}

# Simplified deployment - no APIM import needed
verify_container_app() {
    log_info "Verifying Container App deployment..."
    
    # Get Container App FQDN
    local container_app_fqdn=$(az containerapp show --name "${APPLICATION_NAME}-api" --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn --output tsv 2>/dev/null || echo "")
    
    if [ -n "$container_app_fqdn" ]; then
        local app_url="https://${container_app_fqdn}"
        log_info "Testing Container App health endpoint..."
        
        # Test health endpoint with timeout
        if curl -f -s --max-time 30 "$app_url/healthcheck" >/dev/null 2>&1; then
            log_success "Container App is healthy and responding"
        else
            log_warning "Container App health check failed - may still be starting up"
        fi
    else
        log_warning "Could not retrieve Container App FQDN"
    fi
}

# Documentation is now served directly from Container App
# No separate deployment needed

# Main execution
main() {
    log_info "Starting Lex API deployment..."
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Location: $LOCATION"
    log_info "Application: $APPLICATION_NAME"
    echo ""
    
    check_prerequisites
    set_subscription
    
    # Build and push container image
    container_image=$(build_and_push_image)
    
    # Deploy infrastructure
    deploy_infrastructure "$container_image"
    
    # Verify Container App deployment
    verify_container_app
    
    # Show results
    get_outputs
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi