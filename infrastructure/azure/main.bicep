@description('Main deployment template for Lex Research API')
@minLength(3)
@maxLength(24)
param applicationName string = 'lex-research'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Container image for the backend')
param containerImage string = 'lex-backend:latest'

@description('Environment for deployment')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'prod'

@description('Qdrant Cloud URL')
@secure()
param qdrantCloudUrl string

@description('Qdrant Cloud API Key')
@secure()
param qdrantCloudApiKey string

@description('Azure OpenAI API Key')
@secure()
param azureOpenAIApiKey string

@description('Azure OpenAI Endpoint')
param azureOpenAIEndpoint string

@description('Azure OpenAI Embedding Model')
param azureOpenAIEmbeddingModel string = 'text-embedding-3-large'

// Variables
var resourcePrefix = '${applicationName}-${environment}'
var containerAppName = '${resourcePrefix}-api'
var containerEnvironmentName = '${resourcePrefix}-env'
var apiManagementName = '${resourcePrefix}-apim'
var logAnalyticsName = '${resourcePrefix}-logs'
var appInsightsName = '${resourcePrefix}-insights'
var acrName = '${applicationName}${environment}acr'

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// Azure Container Registry
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Container Apps Environment
resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'app-insights-connection-string'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'qdrant-cloud-url'
          value: qdrantCloudUrl
        }
        {
          name: 'qdrant-cloud-api-key'
          value: qdrantCloudApiKey
        }
        {
          name: 'azure-openai-api-key'
          value: azureOpenAIApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'lex-backend'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'app-insights-connection-string'
            }
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'ENVIRONMENT'
              value: environment
            }
            {
              name: 'USE_CLOUD_QDRANT'
              value: 'true'
            }
            {
              name: 'QDRANT_CLOUD_URL'
              secretRef: 'qdrant-cloud-url'
            }
            {
              name: 'QDRANT_CLOUD_API_KEY'
              secretRef: 'qdrant-cloud-api-key'
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_EMBEDDING_MODEL'
              value: azureOpenAIEmbeddingModel
            }
            {
              name: 'FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER'
              value: 'true'
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthcheck'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthcheck'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// API Management
resource apiManagement 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: apiManagementName
  location: location
  sku: {
    name: 'BasicV2'
    capacity: 1
  }
  properties: {
    publisherEmail: 'lex@cabinetoffice.gov.uk'
    publisherName: 'Incubator for AI - Lex API'
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'false'
    }
  }
}

// Backend configuration for Container App
resource apiBackend 'Microsoft.ApiManagement/service/backends@2023-05-01-preview' = {
  parent: apiManagement
  name: 'lex-backend'
  properties: {
    description: 'Lex Research API Backend'
    url: 'https://${containerApp.properties.configuration.ingress.fqdn}'
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// API definition
resource api 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apiManagement
  name: 'lex-research-api'
  properties: {
    displayName: 'Lex Research API'
    description: 'Free UK legal research API for AI agents and researchers'
    path: ''
    protocols: ['https']
    subscriptionRequired: false
    format: 'openapi+json'
    value: loadTextContent('api-definition.json')
  }
}

// Rate limiting policy
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = {
  parent: api
  name: 'policy'
  dependsOn: [
    apiBackend
  ]
  properties: {
    value: loadTextContent('api-policies.xml')
    format: 'xml'
  }
}

// Using ACR admin credentials for simplicity

// Note: MCP Server will be configured manually through Azure portal
// as the mcpServers resource type is not yet generally available

// Outputs
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output apiManagementUrl string = apiManagement.properties.gatewayUrl
output mcpServerUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}/mcp'
output resourceGroupName string = resourceGroup().name
output acrName string = acr.name