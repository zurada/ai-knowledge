#!/usr/bin/env bash
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
RG="zurada-shop-rg"
LOCATION="westeurope"
ACR_NAME="zuradadshopacr"          # globally unique, lowercase, no hyphens
APP_ENV="zurada-shop-env"
APP_NAME="zurada-shop"
TAG="$(date +%Y%m%d%H%M%S)"
IMAGE="zurada-shop:$TAG"
DOMAIN="shop.zurada.tech"
# ─────────────────────────────────────────────────────────────────────────────

echo "==> Logging in to Azure"
az account show &>/dev/null || az login

echo "==> Registering resource providers (idempotent)"
az provider register -n Microsoft.App --wait --output none
az provider register -n Microsoft.OperationalInsights --wait --output none

echo "==> Creating resource group: $RG"
az group create --name "$RG" --location "$LOCATION" --output none

echo "==> Creating Azure Container Registry (skipping if exists)"
if ! az acr show --name "$ACR_NAME" &>/dev/null; then
  az acr create \
    --name "$ACR_NAME" \
    --resource-group "$RG" \
    --sku Basic \
    --admin-enabled true \
    --output none
else
  echo "  ACR '$ACR_NAME' already exists, reusing."
fi

ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

echo "==> Rebuilding products.json from CSV"
python3 build_json.py

echo "==> Building Docker image locally (linux/amd64 for Azure)"
docker build --platform linux/amd64 -t "$ACR_SERVER/$IMAGE" ./shop

echo "==> Pushing image to ACR: $ACR_SERVER"
echo "$ACR_PASS" | docker login "$ACR_SERVER" -u "$ACR_USER" --password-stdin
docker push "$ACR_SERVER/$IMAGE"

echo "==> Creating Container Apps environment (skipping if exists)"
if ! az containerapp env show --name "$APP_ENV" --resource-group "$RG" &>/dev/null; then
  az containerapp env create \
    --name "$APP_ENV" \
    --resource-group "$RG" \
    --location "$LOCATION" \
    --output none
else
  echo "  Environment '$APP_ENV' already exists, reusing."
fi

echo "==> Creating or updating Container App"
if ! az containerapp show --name "$APP_NAME" --resource-group "$RG" &>/dev/null; then
  az containerapp create \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --environment "$APP_ENV" \
    --image "$ACR_SERVER/$IMAGE" \
    --registry-server "$ACR_SERVER" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --target-port 80 \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 2 \
    --cpu 0.25 \
    --memory 0.5Gi \
    --output none
else
  echo "  Container App '$APP_NAME' already exists, updating image."
  az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --image "$ACR_SERVER/$IMAGE" \
    --output none
fi

APP_FQDN=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv)

echo ""
echo "✅ Shop deployed at: https://$APP_FQDN"
echo ""
echo "── Custom domain (shop.zurada.tech) ─────────────────────────────────────"
echo "1. Add CNAME in your DNS:"
echo "   shop  →  $APP_FQDN"
echo ""
echo "2. After DNS propagates (~5 min), bind the domain:"
echo "   az containerapp hostname add \\"
echo "     --name $APP_NAME --resource-group $RG --hostname $DOMAIN"
echo ""
echo "3. Issue managed SSL certificate:"
echo "   az containerapp hostname bind \\"
echo "     --name $APP_NAME --resource-group $RG \\"
echo "     --hostname $DOMAIN --validation-method CNAME"
