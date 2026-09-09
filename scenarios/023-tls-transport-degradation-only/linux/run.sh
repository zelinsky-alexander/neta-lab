#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$DIR/../../.." && pwd)
exec "$ROOT/common/linux/tls_netns_lab.sh" degradation NETA-LAB-023 "${1:-18463}"
