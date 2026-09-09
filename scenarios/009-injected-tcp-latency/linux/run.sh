#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); exec "$ROOT/common/linux/netns_netem_lab.sh" latency "${1:-100ms}" 18449
