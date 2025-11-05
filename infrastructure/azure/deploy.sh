#!/bin/bash

# Lex API Deployment Script
# Deploy FastAPI backend + MCP server to Azure
# Built by the Incubator for AI

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-lex}"
LOCATION="${LOCATION:-uksouth}"
APPLICATION_NAME="${APPLICATION_NAME:-lex}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
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
            ACR_NAME="${APPLICATION_NAME}${ENVIRONMENT}acr"
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
            environment="$ENVIRONMENT" \
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
        
        API_MANAGEMENT_URL=$(az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs.apiManagementUrl.value" -o tsv)
        
        MCP_SERVER_URL=$(az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs.mcpServerUrl.value" -o tsv)
        
        echo ""
        log_success "Deployment completed successfully!"
        echo ""
        echo "📍 Container App URL: $CONTAINER_APP_URL"
        echo "🌐 API Management URL: $API_MANAGEMENT_URL"
        echo "🤖 MCP Server URL: $MCP_SERVER_URL"
        echo ""
        echo "🔗 Try the API:"
        echo "  curl $API_MANAGEMENT_URL/healthcheck"
        echo ""
        echo "🤖 Add MCP server to Claude Desktop:"
        echo "  Add '$MCP_SERVER_URL' to your MCP configuration"
        echo ""
    fi
}

# Main execution
main() {
    log_info "Starting Lex API deployment..."
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Location: $LOCATION"
    log_info "Application: $APPLICATION_NAME"
    log_info "Environment: $ENVIRONMENT"
    echo ""
    
    check_prerequisites
    set_subscription
    
    # Build and push container image
    container_image=$(build_and_push_image)
    
    # Deploy infrastructure
    deploy_infrastructure "$container_image"
    
    # Show results
    get_outputs
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi