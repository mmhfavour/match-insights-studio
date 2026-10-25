// Match Insights Studio on Azure Container Apps.
// Deploys: Log Analytics, Container Apps environment, a container registry, a user-assigned managed identity,
// and the app (one replica so the live match keeps running for judges). After deploying, grant the
// identity the "Azure AI User" role on your Foundry resource (scripts/deploy.sh does this) so the
// agents call the model with no keys.

@description('Base name for resources')
param name string = 'mis'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Container image, e.g. <registry>.azurecr.io/match-insights-studio:latest')
param image string

@description('Foundry project endpoint, e.g. https://<resource>.services.ai.azure.com/api/projects/<project>')
param foundryProjectEndpoint string = ''

@description('Foundry model deployment name, e.g. gpt-5-mini')
param foundryModel string = ''

@description('Replay speed multiplier for the live match')
param replaySpeed string = '20'

var suffix = uniqueString(resourceGroup().id)

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${name}-logs-${suffix}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: replace('${name}acr${suffix}', '-', '')
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${name}-id-${suffix}'
  location: location
}

// AcrPull for the app identity
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, 'acrpull')
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${name}-env-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${name}-app'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  dependsOn: [ acrPull ]
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
      registries: [ { server: acr.properties.loginServer, identity: identity.id } ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_MODEL', value: foundryModel }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'REPLAY_SPEED', value: replaySpeed }
            { name: 'LOOP_REPLAY', value: '1' }
          ]
          probes: [ { type: 'Liveness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 30 } ]
        }
      ]
      // One replica: the live match state and its WebSocket fan-out live in memory.
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output registry string = acr.properties.loginServer
output identityClientId string = identity.properties.clientId
