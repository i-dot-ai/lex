@description('Main deployment template for Lex API - Simplified Architecture')
@minLength(3)
@maxLength(24)
param applicationName string = 'lex'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Container image for the backend')
param containerImage string = 'lex-backend:latest'

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

@description('PostHog API Key')
@secure()
param posthogKey string = ''

@description('PostHog Host URL')
param posthogHost string = 'https://eu.i.posthog.com'

@description('Custom domain hostname (optional). Requires DNS CNAME and TXT records configured first.')
param customDomain string = ''

@description('Rate limit per minute')
param rateLimitPerMinute int = 60

@description('Rate limit per hour')
param rateLimitPerHour int = 1000

// Variables
var resourcePrefix = applicationName
var containerAppName = '${resourcePrefix}-api'
var containerEnvironmentName = '${resourcePrefix}-env'
var logAnalyticsName = '${resourcePrefix}-logs'
var appInsightsName = '${resourcePrefix}-insights'
var acrName = '${applicationName}acr'
var redisName = '${resourcePrefix}-cache'

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

// Managed Certificate for custom domain
resource managedCertificate 'Microsoft.App/managedEnvironments/managedCertificates@2024-03-01' = if (!empty(customDomain)) {
  parent: containerEnvironment
  name: 'cert-${replace(customDomain, '.', '-')}'
  location: location
  properties: {
    subjectName: customDomain
    domainControlValidation: 'CNAME'
  }
}

// Azure Cache for Redis
resource redisCache 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0  // C0 - smallest instance
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      'maxmemory-reserved': '30'
      'maxfragmentationmemory-reserved': '30'
      'maxmemory-delta': '30'
    }
    publicNetworkAccess: 'Enabled'
  }
  tags: {
    Application: applicationName
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
        customDomains: !empty(customDomain) ? [
          {
            name: customDomain
            certificateId: managedCertificate.id
            bindingType: 'SniEnabled'
          }
        ] : []
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
          passwordSecretRef: 'acr-password'  // pragma: allowlist secret
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
        {
          name: 'redis-primary-key'
          value: redisCache.listKeys().primaryKey
        }
        {
          name: 'posthog-key'
          value: posthogKey
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
              secretRef: 'app-insights-connection-string'  // pragma: allowlist secret
            }
            {
              name: 'PORT'
              value: '8000'
            }
            {
              name: 'USE_CLOUD_QDRANT'
              value: 'true'
            }
            {
              name: 'QDRANT_CLOUD_URL'
              secretRef: 'qdrant-cloud-url'  // pragma: allowlist secret
            }
            {
              name: 'QDRANT_CLOUD_API_KEY'
              secretRef: 'qdrant-cloud-api-key'  // pragma: allowlist secret
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'azure-openai-api-key'  // pragma: allowlist secret
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
            {
              name: 'REDIS_URL'
              value: 'rediss://${redisCache.properties.hostName}:${redisCache.properties.sslPort}'
            }
            {
              name: 'REDIS_PASSWORD'
              secretRef: 'redis-primary-key'  // pragma: allowlist secret
            }
            {
              name: 'RATE_LIMIT_PER_MINUTE'
              value: string(rateLimitPerMinute)
            }
            {
              name: 'RATE_LIMIT_PER_HOUR'
              value: string(rateLimitPerHour)
            }
            {
              name: 'POSTHOG_KEY'
              secretRef: 'posthog-key'  // pragma: allowlist secret
            }
            {
              name: 'POSTHOG_HOST'
              value: posthogHost
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


// Outputs
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output mcpEndpointUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}/mcp'
output apiDocsUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}/api/docs'
output resourceGroupName string = resourceGroup().name
output acrName string = acr.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output redisHostname string = redisCache.properties.hostName
output redisSslPort int = redisCache.properties.sslPort