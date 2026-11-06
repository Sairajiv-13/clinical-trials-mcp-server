"""Exercise the real server over newline-delimited JSON-RPC."""

import json
import os
import queue
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.conftest import load_fixture


def test_stdio_validates_before_dispatch() -> None:
    requests: list[str] = []
    study = json.dumps(load_fixture("study_recruiting.json")).encode()

    class Registry(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(study)))
            self.end_headers()
            self.wfile.write(study)

        def log_message(self, format, *args) -> None:
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Registry) as registry:
        worker = threading.Thread(target=registry.serve_forever, daemon=True)
        worker.start()
        env = {
            **os.environ,
            "CT_MCP_BASE_URL": f"http://127.0.0.1:{registry.server_port}/api/v2",
            "CT_MCP_MAX_RETRIES": "0",
            "CT_MCP_TIMEOUT_SECONDS": "2",
        }
        proc = subprocess.Popen(
            [sys.executable, "-m", "clinical_trials_mcp.server", "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=env,
        )
        lines: queue.Queue[str] = queue.Queue()
        captured: list[str] = []

        def collect() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                captured.append(line)
                lines.put(line)

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()

        def send(method, params=None, request_id=None):
            assert proc.stdin is not None
            message = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                message["params"] = params
            if request_id is not None:
                message["id"] = request_id
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            if request_id is None:
                return None
            reply = json.loads(lines.get(timeout=15))
            assert reply["jsonrpc"] == "2.0" and reply["id"] == request_id
            return reply

        try:
            initialized = send(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "clientInfo": {"name": "wire-test", "version": "1"},
                    "capabilities": {},
                },
                1,
            )
            assert initialized["result"]["serverInfo"]["name"] == "clinical-trials-mcp"
            send("notifications/initialized")
            for request_id, (name, arguments) in enumerate(
                [
                    ("get_trial", {"nct_id": "nct06001122"}),
                    ("eligibility_check", {"nct_id": "NCT１２３４５６７８"}),
                    ("recruiting_sites", {"nct_id": "../studies"}),
                    ("search_trials", {"page_size": 0}),
                    ("search_trials", {"page_size": 51}),
                    ("search_trials", {"page_size": "10"}),
                    ("search_trials", {"page_size": True}),
                    ("search_trials", {"phases": ["PHASE2", "bogus"]}),
                    ("search_trials", {"unexpected": 1}),
                ],
                start=2,
            ):
                reply = send("tools/call", {"name": name, "arguments": arguments}, request_id)
                assert reply["error"]["code"] == -32602
                assert "result" not in reply
            assert requests == []
            result = send(
                "tools/call",
                {"name": "get_trial", "arguments": {"nct_id": "NCT06001122"}},
                11,
            )
            assert result["result"]["structuredContent"]["nct_id"] == "NCT06001122"
            assert requests == ["/api/v2/studies/NCT06001122?format=json"]
        finally:
            assert proc.stdin is not None
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            reader.join(timeout=2)
            registry.shutdown()
            worker.join(timeout=2)
        assert proc.returncode == 0
        assert [json.loads(line)["id"] for line in captured] == list(range(1, 12))
