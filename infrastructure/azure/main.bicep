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
var storageAccountName = '${applicationName}downloads'

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
resource containerEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' = {
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

// Storage Account for Bulk Downloads
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
  tags: {
    Application: applicationName
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource downloadsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'downloads'
  properties: {
    publicAccess: 'Blob'
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2025-07-01' = {
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
            bindingType: 'Auto'
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


// Container Apps Job for Weekly Bulk Export
resource exportJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${resourcePrefix}-export-job'
  location: location
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: '0 3 * * 0'  // Every Sunday at 03:00 UTC
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 21600  // 6 hour timeout for 7.3M documents
      replicaRetryLimit: 2
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'  // pragma: allowlist secret
        }
      ]
      secrets: [
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
          name: 'storage-connection-string'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'export-job'
          image: containerImage
          command: ['uv', 'run', 'python', 'scripts/bulk_export_parquet.py']
          resources: {
            cpu: json('2.0')
            memory: '4Gi'  // Max for 2 CPU in consumption plan; streaming approach is memory-efficient
          }
          env: [
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
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'storage-connection-string'  // pragma: allowlist secret
            }
            {
              name: 'BULK_DOWNLOAD_CONTAINER'
              value: 'downloads'
            }
            {
              name: 'DOWNLOADS_BASE_URL'
              value: 'https://${storageAccount.name}.blob.core.windows.net/downloads'
            }
          ]
        }
      ]
    }
  }
}

// Container Apps Job for Daily Data Ingest
resource ingestJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${resourcePrefix}-ingest-job'
  location: location
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: '0 2 * * *'  // Daily at 02:00 UTC
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 14400  // 4 hour timeout
      replicaRetryLimit: 1
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'  // pragma: allowlist secret
        }
      ]
      secrets: [
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
          name: 'ingest-job'
          image: containerImage
          command: ['uv', 'run', 'python', '-m', 'lex.ingest', '--mode', 'amendments-led']
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
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
          ]
        }
      ]
    }
  }
}

// Container Apps Job for Weekly Deep Ingest (5-year amendments lookback)
resource weeklyIngestJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${resourcePrefix}-weekly-ingest-job'
  location: location
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: '0 2 * * 6'  // Saturday 02:00 UTC
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 86400  // 24 hour timeout
      replicaRetryLimit: 1
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'  // pragma: allowlist secret
        }
      ]
      secrets: [
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
          name: 'weekly-ingest-job'
          image: containerImage
          command: ['uv', 'run', 'python', '-m', 'lex.ingest', '--mode', 'amendments-led', '--years-back', '5']
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
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
          ]
        }
      ]
    }
  }
}

// Container Apps Job for Monthly Full Ingest (all historical data)
resource monthlyIngestJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${resourcePrefix}-monthly-ingest-job'
  location: location
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: '0 1 1 * *'  // 1st of month, 01:00 UTC
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 604800  // 1 week timeout
      replicaRetryLimit: 1
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'  // pragma: allowlist secret
        }
      ]
      secrets: [
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
          name: 'monthly-ingest-job'
          image: containerImage
          command: ['uv', 'run', 'python', '-m', 'lex.ingest', '--mode', 'full']
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
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
          ]
        }
      ]
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
output storageAccountName string = storageAccount.name
output downloadsBaseUrl string = 'https://${storageAccount.name}.blob.core.windows.net/downloads'