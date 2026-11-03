#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v astro >/dev/null 2>&1; then
    (cd "$ROOT_DIR/astro" && astro dev stop)
fi

cd "$ROOT_DIR"
docker compose down
