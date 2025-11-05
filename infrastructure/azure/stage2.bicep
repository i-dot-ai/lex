@description('Stage 2: Configure ACR authentication for Container App')

@description('Name of the Container App')
param containerAppName string

@description('Principal ID of the Container App managed identity')
param containerAppIdentityPrincipalId string

@description('Name of the Azure Container Registry')
param acrName string

@description('Login server of the Azure Container Registry')
param acrLoginServer string

@description('Container image to deploy')
param containerImage string

// Get existing resources
resource containerApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: containerAppName
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

// Role assignment: Grant Container App managed identity AcrPull access to ACR
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, containerAppIdentityPrincipalId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull role
    principalId: containerAppIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Update Container App with ACR registry configuration
resource containerAppUpdate 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: containerApp.location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerApp.properties.managedEnvironmentId
    configuration: {
      ingress: containerApp.properties.configuration.ingress
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: containerApp.properties.configuration.secrets
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
          env: containerApp.properties.template.containers[0].env
          probes: containerApp.properties.template.containers[0].probes
        }
      ]
      scale: containerApp.properties.template.scale
    }
  }
  dependsOn: [
    acrPullRoleAssignment
  ]
}

output containerAppUrl string = 'https://${containerAppUpdate.properties.configuration.ingress.fqdn}'