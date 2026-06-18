#!/usr/bin/env bash
# Trigger Maestro repricing for 6 USD custom assets in DEV.
# Usage: export CERBERUS_TOKEN=$(sesame-cli impersonate --env=DEV "EdgeLab Employees")
#        bash reprice_maestro.sh

TOKEN="${CERBERUS_TOKEN:?Set CERBERUS_TOKEN first}"
BASE="https://api.dev.edge-lab.ch/maestro/pricing"

for ID in \
  04cc4f53-e24f-45aa-85d0-5e975e67bfbd \
  0f53a356-651b-485b-b70f-4a024f6aac0a \
  d91d5307-2c1b-46ce-a33b-cdd2ba61be42 \
  3c20198f-2c5c-433d-a72d-b2de598f381b \
  364b461b-96cb-4c73-9048-e7f78eb8c407 \
  4464fe55-26c7-4e3b-bfc0-c691901b4590
do
  echo -n "$ID: "
  curl -sS --request PUT \
    --url "$BASE/$ID" \
    --header "Authorization: Bearer $TOKEN" \
    --header "Content-Type: application/json" \
    -w "HTTP %{http_code}\n" -o /dev/null
done

echo "Done. Wait 1-2 min, then refresh Excel (Ctrl+Shift+F9)."
