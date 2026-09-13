#!/usr/bin/env bash
set -euo pipefail

RUN_ID="linux-$(date -u +%Y%m%dT%H%M%SZ)-$$"
TMP="$(mktemp -d -t neta-lab-006-XXXXXX)"
COPIED="$TMP/system-update-helper"
ID_OUT="$TMP/id.txt"
HOST_OUT="$TMP/hostname.txt"
UNAME_OUT="$TMP/uname.txt"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT INT TERM

for tool in sh cp sha256sum id hostname uname readlink; do command -v "$tool" >/dev/null || { echo "required tool missing: $tool" >&2; exit 2; }; done

SOURCE_LINK="$(command -v sh)"
SOURCE="$(readlink -f "$SOURCE_LINK")"
cp "$SOURCE" "$COPIED"
chmod 0700 "$COPIED"

SOURCE_SHA256="$(sha256sum "$SOURCE" | awk '{print $1}')"
COPIED_SHA256="$(sha256sum "$COPIED" | awk '{print $1}')"
[[ "$SOURCE_SHA256" == "$COPIED_SHA256" ]] || { echo "copied executable hash mismatch" >&2; exit 1; }
[[ "$SOURCE" != "$COPIED" ]] || { echo "copied executable path did not change" >&2; exit 1; }

PACKAGE_PROVENANCE="unavailable"
if command -v dpkg-query >/dev/null 2>&1; then
  pkg="$(dpkg-query -S "$SOURCE" 2>/dev/null | head -n1 | cut -d: -f1 || true)"
  if [[ -n "$pkg" ]]; then
    PACKAGE_PROVENANCE="$(dpkg-query -W -f='dpkg:${Package}:${Version}:${db:Status-Abbrev}' "$pkg" 2>/dev/null || printf unavailable)"
  fi
elif command -v rpm >/dev/null 2>&1; then
  PACKAGE_PROVENANCE="$(rpm -qf --qf 'rpm:%{NAME}:%{VERSION}-%{RELEASE}' "$SOURCE" 2>/dev/null || printf unavailable)"
fi

printf 'scenario=NETA-LAB-006\nrun_id=%s\nsource_executable=%s\ncopied_executable=%s\nsource_sha256=%s\ncopied_sha256=%s\nsource_package_provenance=%s\n' \
  "$RUN_ID" "$SOURCE" "$COPIED" "$SOURCE_SHA256" "$COPIED_SHA256" "$PACKAGE_PROVENANCE"

ID_BIN="$(command -v id)"
HOSTNAME_BIN="$(command -v hostname)"
UNAME_BIN="$(command -v uname)"
"$COPIED" -c '"$1" >"$4"; "$2" >"$5"; "$3" -a >"$6"' \
  neta-lab-006 "$ID_BIN" "$HOSTNAME_BIN" "$UNAME_BIN" "$ID_OUT" "$HOST_OUT" "$UNAME_OUT"

[[ -s "$ID_OUT" && -s "$HOST_OUT" && -s "$UNAME_OUT" ]] || { echo "child-process output missing" >&2; exit 1; }
printf 'children=id,hostname,uname\nNETA-LAB-006 Linux process chain complete\n'
