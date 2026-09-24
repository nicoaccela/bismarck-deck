#!/bin/bash
# Render control for the Bismarck deck site, via the Render API.
#   ./render.sh key       save your Render API key in the macOS Keychain (one time)
#   ./render.sh deploy    create the service (first time) or trigger a redeploy
#   ./render.sh status    URL, latest deploy status, presenter link
set -euo pipefail
cd "$(dirname "$0")"
API=https://api.render.com/v1
NAME=bismarck-deck
REPO=https://github.com/nicoaccela/bismarck-deck
KC=(-a render -s render-api)

if [ "${1:-}" = key ]; then
  read -rsp "Paste Render API key (rnd_...): " k; echo
  security add-generic-password -U "${KC[@]}" -w "$k" && echo "Saved to Keychain."
  exit 0
fi

TOKEN=$(security find-generic-password "${KC[@]}" -w 2>/dev/null) || { echo "No key. Run: ./render.sh key"; exit 1; }
r() { curl -sS -f -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" -H "Content-Type: application/json" "$@"; }

SID=$(r "$API/services?name=$NAME&limit=20" | jq -r '.[0].service.id // empty')

status() {
  [ -n "$SID" ] || { echo "No service yet. Run: ./render.sh deploy"; exit 1; }
  URL=$(r "$API/services/$SID" | jq -r '.serviceDetails.url')
  PK=$(r "$API/services/$SID/env-vars?limit=50" | jq -r '.[] | .envVar | select(.key=="PRESENTER_KEY") | .value')
  echo "Deploy:    $(r "$API/services/$SID/deploys?limit=1" | jq -r '.[0].deploy.status')"
  echo "Audience:  $URL/follow"
  echo "Presenter: $URL/?presenter=$PK"
}

case "${1:-status}" in
  deploy)
    if [ -z "$SID" ]; then
      OWNER=$(r "$API/owners?limit=20" | jq -r '.[0].owner.id')
      body=$(jq -n --arg o "$OWNER" --arg n "$NAME" --arg repo "$REPO" '{
        type:"web_service", name:$n, ownerId:$o, repo:$repo, branch:"main", autoDeploy:"yes",
        serviceDetails:{runtime:"python", plan:"starter", region:"ohio", healthCheckPath:"/robots.txt",
          envSpecificDetails:{buildCommand:"pip install -r requirements.txt", startCommand:"python3 server.py"}},
        envVars:[{key:"PRESENTER_KEY", generateValue:true}]}')
      SID=$(r -X POST "$API/services" -d "$body" | jq -r '.service.id')
      echo "Created $SID"
    else
      r -X POST "$API/services/$SID/deploys" -d '{}' >/dev/null && echo "Redeploy triggered for $SID"
    fi
    for i in $(seq 1 60); do
      st=$(r "$API/services/$SID/deploys?limit=1" | jq -r '.[0].deploy.status')
      echo "  $st"; case "$st" in live) break;; *failed*|canceled|deactivated) exit 1;; esac; sleep 10
    done
    status ;;
  status) status ;;
  *) sed -n 2,5p "$0"; exit 1 ;;
esac
