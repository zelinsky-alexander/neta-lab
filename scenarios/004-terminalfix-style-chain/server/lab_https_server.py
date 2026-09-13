#!/usr/bin/env python3
"""Controlled HTTPS server for NETA-LAB-004.

Serves one benign payload and accepts one callback endpoint. Uses only Python's
standard library and writes JSON-line ground truth to stdout. The payload route
is configurable so the same scenario ID can serve platform-specific payloads.
"""

from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SCENARIO_ID = "NETA-LAB-004"
DEFAULT_PAYLOAD_ROUTE = "/payload/neta-lab-004-payload.exe"
CALLBACK_ROUTE = "/callback"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(event: str, handler: BaseHTTPRequestHandler, **extra: object) -> None:
    record = {
        "timestamp": utc_now(),
        "scenario": SCENARIO_ID,
        "event": event,
        "client": handler.client_address[0],
        "path": handler.path,
    }
    record.update(extra)
    print(json.dumps(record, sort_keys=True), flush=True)


class LabHandler(BaseHTTPRequestHandler):
    server_version = "NETA-Lab/004"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlsplit(self.path)
        run_id = self.headers.get("X-NETA-Lab-Run", "")
        payload_route: str = self.server.payload_route  # type: ignore[attr-defined]

        if parsed.path == payload_route:
            payload_path: Path = self.server.payload_path  # type: ignore[attr-defined]
            if not payload_path.is_file():
                emit("payload_missing", self, run_id=run_id, payload=str(payload_path))
                self.send_error(404, "Build or provide the benign payload before running the scenario")
                return

            data = payload_path.read_bytes()
            emit("payload_download", self, run_id=run_id, bytes=len(data), payload_route=payload_route)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path == CALLBACK_ROUTE:
            query = parse_qs(parsed.query)
            callback_run_id = query.get("run_id", [run_id])[0]
            emit("payload_callback", self, run_id=callback_run_id)
            body = b'{"status":"ok","scenario":"NETA-LAB-004"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        emit("unexpected_request", self, run_id=run_id)
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="NETA-LAB-004 controlled HTTPS server")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18443)
    parser.add_argument("--cert", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument(
        "--payload",
        type=Path,
        default=here / "payload" / "neta-lab-004-payload.exe",
        help="Path to the benign platform payload",
    )
    parser.add_argument(
        "--payload-route",
        default=DEFAULT_PAYLOAD_ROUTE,
        help="HTTPS path used to serve the selected platform payload",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.payload_route.startswith("/"):
        raise SystemExit("--payload-route must start with /")

    httpd = ThreadingHTTPServer((args.bind, args.port), LabHandler)
    httpd.payload_path = args.payload.resolve()  # type: ignore[attr-defined]
    httpd.payload_route = args.payload_route  # type: ignore[attr-defined]

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(args.cert), keyfile=str(args.key))
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(
        json.dumps(
            {
                "timestamp": utc_now(),
                "scenario": SCENARIO_ID,
                "event": "server_started",
                "bind": args.bind,
                "port": args.port,
                "payload": str(httpd.payload_path),
                "payload_route": httpd.payload_route,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
