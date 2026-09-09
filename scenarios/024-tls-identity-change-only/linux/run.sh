#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd)
exec "$ROOT/scenarios/022-tls-identity-rotation/linux/run.sh" "${1:-18464}"
