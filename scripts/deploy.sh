#!/usr/bin/env bash
# One-command deploy to Azure Container Apps (builds the image in the cloud from this folder).
#
# Required:  az login, and a Foundry project with a deployed model.
#   export FOUNDRY_PROJECT_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
#   export FOUNDRY_MODEL="gpt-5-mini"                       # your deployment name
#   export FOUNDRY_RESOURCE_ID="/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/<resource>"
# Optional:  RG, LOCATION, APP, REPLAY_SPEED
set -euo pipefail

RG="${RG:-match-insights-rg}"
LOCATION="${LOCATION:-eastus2}"
APP="${APP:-match-insights-studio}"
REPLAY_SPEED="${REPLAY_SPEED:-20}"

cd "$(dirname "$0")/.."

az group create --name "$RG" --location "$LOCATION" --output none

az containerapp up \
  --name "$APP" --resource-group "$RG" --location "$LOCATION" \
  --source . --ingress external --target-port 8000 \
  --env-vars "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:-}" "FOUNDRY_MODEL=${FOUNDRY_MODEL:-}" \
             "REPLAY_SPEED=$REPLAY_SPEED" "LOOP_REPLAY=1"

# Keyless access to Foundry: system-assigned identity + Azure AI User on the Foundry resource.
az containerapp identity assign --name "$APP" --resource-group "$RG" --system-assigned --output none
PRINCIPAL_ID=$(az containerapp show --name "$APP" --resource-group "$RG" --query identity.principalId -o tsv)
if [[ -n "${FOUNDRY_RESOURCE_ID:-}" ]]; then
  az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
    --role "Azure AI User" --scope "$FOUNDRY_RESOURCE_ID" --output none || true
fi

# One replica: match state and WebSocket fan-out live in memory.
az containerapp update --name "$APP" --resource-group "$RG" --min-replicas 1 --max-replicas 1 --output none

URL=$(az containerapp show --name "$APP" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "Viewer:   https://$URL/"
echo "Producer: https://$URL/producer"
echo "Replay:   https://$URL/replay"
