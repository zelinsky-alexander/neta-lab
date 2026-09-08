#!/usr/bin/env python3
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SCENARIO_ID = "NETA-LAB-005"
STAGE_BYTES = (
    b"NETA-LAB-005 benign staging artifact\n"
    b"This deterministic text is inert and must never be executed.\n"
    b"Purpose: validate signed-system-utility behavioral evidence.\n"
)


def log_event(event, handler, run_id=""):
    record = {
        "scenario": SCENARIO_ID,
        "event": event,
        "run_id": run_id,
        "client": handler.client_address[0],
        "timestamp_unix": time.time(),
        "path": handler.path,
    }
    print(json.dumps(record, sort_keys=True), flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "NETA-Lab-005/1"

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        run_id = query.get("run_id", [""])[0]

        if parsed.path == "/stage.txt":
            log_event("stage_download", self, run_id)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(STAGE_BYTES)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(STAGE_BYTES)
            return

        if parsed.path == "/callback":
            header_run_id = self.headers.get("X-NETA-Lab-Run", "")
            effective_run_id = header_run_id or run_id
            log_event("callback", self, effective_run_id)
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not found")

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="NETA-LAB-005 controlled HTTP server")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18580)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(
        json.dumps(
            {
                "scenario": SCENARIO_ID,
                "event": "server_started",
                "bind": args.bind,
                "port": args.port,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
