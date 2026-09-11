#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${NETA_LAB_OUTPUT_DIR:-$ROOT/out/linux-$(date -u +%Y%m%dT%H%M%SZ)}"
TARGET_HOST="${NETA_LAB_TARGET_HOST:-}"
SCENARIOS="${NETA_LAB_SCENARIOS:-all}"

usage() {
  cat <<'EOF'
Usage: automation/run-linux-suite.sh [--target-host HOST] [--scenarios all|ID,ID,...] [--output-dir DIR] [--list]

Runs the non-interactive Linux NETA Lab scenarios and writes per-scenario logs plus
summary.tsv and summary.json. Scenarios that require a second host to initiate an
inbound connection (016, the inbound half of 017, and the connected phase of 018)
are intentionally reported as PEER_REQUIRED; the full-cycle orchestrator drives
those two-host steps.

Environment equivalents:
  NETA_LAB_TARGET_HOST   controlled peer/target host for outbound scenarios
  NETA_LAB_SCENARIOS     all or comma-separated numeric IDs
  NETA_LAB_OUTPUT_DIR    result directory
EOF
}

list_scenarios() {
  find "$ROOT/scenarios" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
}

while (($#)); do
  case "$1" in
    --target-host) TARGET_HOST="${2:?--target-host requires HOST}"; shift 2 ;;
    --scenarios) SCENARIOS="${2:?--scenarios requires a value}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:?--output-dir requires DIR}"; shift 2 ;;
    --list) list_scenarios; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

mkdir -p "$OUTPUT_DIR"
SUMMARY_TSV="$OUTPUT_DIR/summary.tsv"
printf 'scenario\tstatus\texit_code\tnote\n' >"$SUMMARY_TSV"

selected() {
  local id="$1"
  [[ "$SCENARIOS" == "all" ]] && return 0
  case ",$SCENARIOS," in *",$id,"*) return 0 ;; *) return 1 ;; esac
}

record() {
  printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >>"$SUMMARY_TSV"
}

run_case() {
  local id="$1" dir="$2" script="$dir/linux/run.sh" log="$OUTPUT_DIR/$id.log" rc=0
  if [[ ! -x "$script" ]]; then
    if [[ -f "$script" ]]; then chmod +x "$script"; else record "$id" "NOT_APPLICABLE" 0 "no standalone Linux run.sh"; return; fi
  fi
  cp "$dir/expected.yaml" "$OUTPUT_DIR/$id.expected.yaml" 2>/dev/null || true

  echo "=== NETA-LAB-$id ===" | tee "$log"
  case "$id" in
    001) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_HTTP_PORT:-18080}" "${NETA_LAB_BEACON_COUNT:-12}" "${NETA_LAB_BEACON_INTERVAL:-1}" >>"$log" 2>&1 || rc=$? ;;
    002) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_HTTPS_PORT:-18443}" "${NETA_LAB_BEACON_COUNT:-12}" "${NETA_LAB_BEACON_INTERVAL:-1}" >>"$log" 2>&1 || rc=$? ;;
    003) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_DOWNLOAD_PORT:-18081}" "${NETA_LAB_DOWNLOAD_MIB:-50}" >>"$log" 2>&1 || rc=$? ;;
    007) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_UPLOAD_PORT:-18447}" >>"$log" 2>&1 || rc=$? ;;
    008) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_BASELINE_PORT:-18448}" >>"$log" 2>&1 || rc=$? ;;
    014) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_SHORT_PORT:-18454}" "${NETA_LAB_SHORT_COUNT:-100}" >>"$log" 2>&1 || rc=$? ;;
    015) [[ -n "$TARGET_HOST" ]] || { record "$id" "TARGET_REQUIRED" 2 "set --target-host"; return; }
         "$script" "$TARGET_HOST" "${NETA_LAB_BURST_PORT:-18455}" "${NETA_LAB_BURST_COUNT:-250}" "${NETA_LAB_BURST_PARALLEL:-20}" >>"$log" 2>&1 || rc=$? ;;
    016) record "$id" "PEER_REQUIRED" 0 "full-cycle orchestrator starts server and drives client from peer"; return ;;
    017) record "$id" "PEER_REQUIRED" 0 "full-cycle orchestrator coordinates inbound and outbound peers"; return ;;
    018) record "$id" "PEER_REQUIRED" 0 "full-cycle orchestrator preserves idle-listener phase, then drives one peer connection"; return ;;
    *)   "$script" >>"$log" 2>&1 || rc=$? ;;
  esac

  if ((rc == 0)); then record "$id" "PASS" 0 "scenario command completed"; else record "$id" "FAIL" "$rc" "see $id.log"; fi
}

while IFS= read -r dir; do
  base="$(basename "$dir")"; id="${base%%-*}"
  selected "$id" || continue
  case "$id" in 004|005|006) record "$id" "NOT_APPLICABLE" 0 "Windows-only scenario" ;; *) run_case "$id" "$dir" ;; esac
done < <(find "$ROOT/scenarios" -mindepth 1 -maxdepth 1 -type d | sort)

python3 - "$SUMMARY_TSV" "$OUTPUT_DIR/summary.json" <<'PY'
import csv, json, sys
src, dst = sys.argv[1:]
with open(src, newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f, delimiter='\t'))
with open(dst, 'w', encoding='utf-8') as f:
    json.dump({"platform":"linux","results":rows}, f, indent=2)
    f.write("\n")
PY

cat "$SUMMARY_TSV"
if awk -F '\t' 'NR>1 && ($2=="FAIL" || $2=="TARGET_REQUIRED") {bad=1} END{exit bad?0:1}' "$SUMMARY_TSV"; then
  echo "NETA Linux lab suite: FAIL" >&2
  exit 1
fi
echo "NETA Linux lab suite: command phase complete"
