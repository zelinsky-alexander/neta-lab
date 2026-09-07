#!/usr/bin/env python3
"""Minimal controlled HTTP/HTTPS endpoint for NETA Lab beacon scenarios."""

from __future__ import annotations

import argparse
import http.server
import json
import ssl
import time


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "NETA-Lab/1"

    def do_GET(self) -> None:
        now = time.time()
        run_id = self.headers.get("X-NETA-Lab-Run", "unknown")
        scenario = self.headers.get("X-NETA-Lab-Scenario", "unknown")
        record = {
            "timestamp_unix": now,
            "client": self.client_address[0],
            "path": self.path,
            "run_id": run_id,
            "scenario": scenario,
        }
        print(json.dumps(record), flush=True)
        payload = b"NETA-LAB-OK\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a controlled NETA Lab HTTP(S) server")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--cert", help="PEM certificate; enables HTTPS when used with --key")
    parser.add_argument("--key", help="PEM private key; enables HTTPS when used with --cert")
    args = parser.parse_args()

    if bool(args.cert) != bool(args.key):
        parser.error("--cert and --key must be supplied together")

    server = http.server.ThreadingHTTPServer((args.bind, args.port), Handler)
    scheme = "http"
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    print(f"NETA Lab server listening on {scheme}://{args.bind}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
