"""Serve recorded chat responses on loopback and exercise the real HTTP adapter."""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread

from datawheel.pipeline import run


@contextmanager
def fixture_server(recordings: list[dict]):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            index = len(requests)
            requests.append({"path": self.path, "body": body, "headers": dict(self.headers)})
            if index >= len(recordings):
                self.send_error(400, "No recorded response remains")
                return
            recording = recordings[index]
            stage = json.loads(body["messages"][-1]["content"])["stage"]
            if stage != recording["stage"] or body["model"] != recording["model"]:
                self.send_error(400, "Unexpected role or model for recorded response")
                return
            response = recording.get("raw_body")
            if response is None:
                response = json.dumps(recording["response"])
            encoded = response.encode()
            self.send_response(recording.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            pass  # Expected requests are available in the returned request log.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    here = Path(__file__).parent
    config = json.loads((here / "config.json").read_text())
    recordings = json.loads((here / "responses.json").read_text())
    with fixture_server(recordings) as (endpoint, requests), tempfile.TemporaryDirectory() as directory:
        config["endpoint"] = endpoint
        config_path = Path(directory) / "config.json"
        config_path.write_text(json.dumps(config))
        summary = run(here / "seeds.jsonl", args.output, rounds=2, budget=6, keep=6,
                      adapter_spec="datawheel.chat_adapter:ChatAdapter", adapter_config=config_path)
        print(f"HTTP replay only: {len(requests)} calls, {summary['exported_records']} exported records")
        print(f"Report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()
