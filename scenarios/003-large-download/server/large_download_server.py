#!/usr/bin/env python3
"""Controlled deterministic large-download server for NETA-LAB-003."""

from __future__ import annotations

import argparse
import http.server
import json
import time
from urllib.parse import parse_qs, urlparse

MIB = 1024 * 1024
CHUNK = (b"NETA-LAB-003-CONTROLLED-PAYLOAD\n" * 2048)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "NETA-Lab/003"
    default_size_mib = 300
    minimum_duration_seconds = 8.0

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/large-download":
            self.send_error(404)
            return

        query = parse_qs(parsed.query)
        try:
            size_mib = int(query.get("size_mib", [str(self.default_size_mib)])[0])
        except ValueError:
            self.send_error(400, "invalid size_mib")
            return
        if size_mib <= 0 or size_mib > 1024:
            self.send_error(400, "size_mib must be between 1 and 1024")
            return

        total = size_mib * MIB
        run_id = self.headers.get("X-NETA-Lab-Run", "unknown")
        scenario = self.headers.get("X-NETA-Lab-Scenario", "unknown")
        started = time.time()
        record = {
            "event": "download_start",
            "timestamp_unix": started,
            "client": self.client_address[0],
            "path": parsed.path,
            "run_id": run_id,
            "scenario": scenario,
            "payload_bytes": total,
        }
        print(json.dumps(record), flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(total))
        self.end_headers()

        remaining = total
        sent = 0
        pacing_started = time.monotonic()
        try:
            while remaining > 0:
                piece = CHUNK[: min(len(CHUNK), remaining)]
                self.wfile.write(piece)
                remaining -= len(piece)
                sent += len(piece)
                if self.minimum_duration_seconds > 0:
                    target_elapsed = self.minimum_duration_seconds * sent / total
                    delay = target_elapsed - (time.monotonic() - pacing_started)
                    if delay > 0:
                        time.sleep(delay)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print(json.dumps({
                "event": "download_interrupted",
                "timestamp_unix": time.time(),
                "run_id": run_id,
                "scenario": scenario,
                "bytes_remaining": remaining,
            }), flush=True)
            return

        print(json.dumps({
            "event": "download_complete",
            "timestamp_unix": time.time(),
            "run_id": run_id,
            "scenario": scenario,
            "payload_bytes": total,
            "duration_seconds": time.time() - started,
        }), flush=True)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NETA-LAB-003 controlled download server")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--size-mib", type=int, default=300)
    parser.add_argument("--minimum-duration-seconds", type=float, default=8.0)
    args = parser.parse_args()
    if args.size_mib <= 0 or args.size_mib > 1024:
        parser.error("--size-mib must be between 1 and 1024")
    if args.minimum_duration_seconds < 0 or args.minimum_duration_seconds > 120:
        parser.error("--minimum-duration-seconds must be between 0 and 120")

    Handler.default_size_mib = args.size_mib
    Handler.minimum_duration_seconds = args.minimum_duration_seconds
    server = http.server.ThreadingHTTPServer((args.bind, args.port), Handler)
    print(
        f"NETA-LAB-003 server listening on http://{args.bind}:{args.port} "
        f"default_payload={args.size_mib} MiB",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
