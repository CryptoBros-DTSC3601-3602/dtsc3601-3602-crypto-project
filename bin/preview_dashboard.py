"""Preview the dashboard locally with labeled fixture data."""
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "src/dashboard/static"
NOW = datetime.now(timezone.utc).isoformat()
DIGEST = "sha256:9b2c80503af34db98bfb370835c11010ced4123d062b2347efe037ab9c71e424"
FIXTURE = {
    "updated_at": NOW, "active_model_digest": DIGEST, "training_configured": True,
    "forecast": {
        "prediction": "UP", "close": 94982.20, "created_at": NOW, "model_digest": DIGEST,
        "probabilities": {"UP": 0.68, "FLAT": 0.22, "DOWN": 0.10},
    },
    "accuracy": {"outcomes": [int((index * 39) % 73 < 46) for index in range(100)]},
    "training_runs": [
        {"id": "Sample run 03", "started_at": NOW, "status": "validated", "accuracy": 0.61, "test_rows": 6890},
        {"id": "Sample run 02", "started_at": NOW, "status": "failed", "accuracy": None, "test_rows": None},
        {"id": "Sample run 01", "started_at": NOW, "status": "validated", "accuracy": 0.57, "test_rows": 6838},
    ],
    "sample": True,
}
FILES = {"/": ("index.html", "text/html"), "/dashboard.css": ("dashboard.css", "text/css"),
         "/dashboard.js": ("dashboard.js", "text/javascript")}


class Preview(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/dashboard":
            content_type, body = "application/json", json.dumps(FIXTURE).encode()
        elif self.path in FILES:
            filename, content_type = FILES[self.path]
            body = (STATIC / filename).read_bytes()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Preview).serve_forever()
