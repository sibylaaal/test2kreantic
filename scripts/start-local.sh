#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Install Docker Desktop/Engine and try again." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker Engine is not running or this user cannot access it." >&2
    echo "Start Docker and check access to the Docker socket, then retry." >&2
    exit 1
fi

if ! command -v astro >/dev/null 2>&1; then
    echo "Astro CLI is required. Install it from https://www.astronomer.io/docs/astro/cli/install-cli" >&2
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required so this script can wait for the service health endpoints." >&2
    exit 1
fi

cd "$ROOT_DIR"
docker compose up --build -d

services=(
    "crm|CRM"
    "billing|Billing"
    "invoicing|Invoicing"
    "notification|Notification"
)

for service in "${services[@]}"; do
    compose_service="${service%%|*}"
    name="${service#*|}"
    host_port="$(docker compose port "$compose_service" 8000)"
    host_port="${host_port##*:}"
    url="http://localhost:${host_port}/health"
    printf 'Waiting for %s' "$name"
    for attempt in {1..60}; do
        if curl --fail --silent "$url" >/dev/null; then
            echo " ready"
            break
        fi
        if [[ "$attempt" -eq 60 ]]; then
            echo
            echo "$name did not become healthy. Inspect logs with: docker compose logs $name" >&2
            exit 1
        fi
        printf '.'
        sleep 2
    done
done

cd "$ROOT_DIR/astro"
if [[ ! -f .astro/config.yaml ]]; then
    echo "Astro project config is missing from $ROOT_DIR/astro/.astro/config.yaml" >&2
    echo "Restore the project configuration file, then retry." >&2
    exit 1
fi
astro dev start --wait 5m --no-browser

echo
echo "Telecom learning environment is running."
echo "CRM:          http://localhost:8001/docs"
echo "Billing:      http://localhost:8002/docs"
echo "Invoicing:    http://localhost:8003/docs"
echo "Notification: http://localhost:8004/docs"
echo "Airflow:      use the URL printed by Astro CLI (for this run: http://astro.localhost:6563)"
