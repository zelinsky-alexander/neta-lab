#!/usr/bin/env bash
set -euo pipefail
CMD=${1:?usage: $0 <prepare|server|client|fingerprint> ...}; shift
case "$CMD" in
prepare)
  DIR=${1:?dir}; HOST=${2:-neta-lab.local}; mkdir -p "$DIR"
  openssl req -x509 -newkey rsa:2048 -nodes -days 7 -keyout "$DIR/ca.key" -out "$DIR/ca.pem" -subj "/CN=NETA Lab CA" >/dev/null 2>&1
  for ID in A B; do
    openssl req -newkey rsa:2048 -nodes -keyout "$DIR/server-$ID.key" -out "$DIR/server-$ID.csr" -subj "/CN=$HOST" >/dev/null 2>&1
    printf 'subjectAltName=DNS:%s\nextendedKeyUsage=serverAuth\n' "$HOST" > "$DIR/server-$ID.ext"
    openssl x509 -req -in "$DIR/server-$ID.csr" -CA "$DIR/ca.pem" -CAkey "$DIR/ca.key" -CAcreateserial -days 7 -out "$DIR/server-$ID.pem" -extfile "$DIR/server-$ID.ext" >/dev/null 2>&1
  done
  ;;
server)
  DIR=${1:?dir}; ID=${2:?A-or-B}; ADDR=${3:-127.0.0.1}; PORT=${4:-18461}
  exec openssl s_server -quiet -www -accept "$ADDR:$PORT" -cert "$DIR/server-$ID.pem" -key "$DIR/server-$ID.key"
  ;;
client)
  DIR=${1:?dir}; ADDR=${2:-127.0.0.1}; PORT=${3:-18461}; HOST=${4:-neta-lab.local}
  printf 'GET / HTTP/1.0\r\nHost: %s\r\n\r\n' "$HOST" | openssl s_client -quiet -verify_return_error -verify_hostname "$HOST" -servername "$HOST" -CAfile "$DIR/ca.pem" -connect "$ADDR:$PORT"
  ;;
fingerprint)
  DIR=${1:?dir}; ID=${2:?A-or-B}
  LEAF=$(openssl x509 -in "$DIR/server-$ID.pem" -outform DER | sha256sum | awk '{print $1}')
  SPKI=$(openssl x509 -in "$DIR/server-$ID.pem" -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}')
  echo "identity=$ID leaf_sha256=$LEAF spki_sha256=$SPKI"
  ;;
*) echo "unknown command: $CMD" >&2; exit 2;;
esac
