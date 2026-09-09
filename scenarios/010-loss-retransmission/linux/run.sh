#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); exec "$ROOT/common/linux/netns_netem_lab.sh" loss "${1:-5%}" 18450
