"""Observer-owned HTTP client boundary for restart-aware regression tests."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


class RegressionProxy:
    def __init__(self, service):
        self.error = None
        mutex = threading.Lock()
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.forward()

            def do_POST(self):
                self.forward()

            def forward(self):
                permitted = {("GET", "/state"), ("POST", "/webhook"), ("POST", "/__replay/restart")}
                if (self.command, self.path) not in permitted:
                    self.send_error(404)
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 131072:
                    self.send_error(413)
                    return
                body = self.rfile.read(size)
                try:
                    with mutex:
                        service.check_cancelled()
                        if self.path == "/__replay/restart":
                            service.stop()
                            service.start()
                            status, content = 200, b'{"restarted":true}'
                        else:
                            with httpx.Client(timeout=3, trust_env=False) as client:
                                response = client.request(self.command, service.url + self.path, content=body, headers={"Content-Type": "application/json"})
                            status, content = response.status_code, response.content[:65536]
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as exc:  # noqa: BLE001 - record transport failure separately.
                    proxy.error = type(exc).__name__
                    self.send_error(503, "regression service unavailable")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
