"""Serve the dashboard locally with sample data or read-only AWS data."""
import argparse
import json
import sys
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
    "accuracy": {"outcomes": [int((index * 39) % 73 < 46) for index in range(100)],
                 "total_correct": 151, "total_scored": 250},
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
            try:
                snapshot = self.server.load_snapshot()
            except Exception as error:
                self.log_error("AWS snapshot read failed (%s)", type(error).__name__)
                self.send_error(503, "AWS dashboard data unavailable")
                return
            content_type, body = "application/json", json.dumps(snapshot).encode()
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


def aws_snapshot_reader():
    import boto3
    sys.path.insert(0, str(STATIC.parents[2]))
    from src.dashboard.snapshot import read_snapshot

    session = boto3.Session(profile_name="dtsc3601-crypto", region_name="us-east-2")
    identity = session.client("sts").get_caller_identity()
    if identity["Arn"] != "arn:aws:iam::879022683465:user/AashutoshPanchal":
        raise RuntimeError("Unexpected AWS identity for the project dashboard")
    cloudformation = session.client("cloudformation")
    stack_name = "dtsc3601-crypto-serverless"

    def load():
        stack = cloudformation.describe_stacks(StackName=stack_name)["Stacks"][0]
        outputs = {v["OutputKey"]: v["OutputValue"] for v in stack["Outputs"]}
        params = {v["ParameterKey"]: v["ParameterValue"] for v in stack["Parameters"]}
        history = None
        if params.get("TrainingImage"):
            history = cloudformation.describe_stack_resource(
                StackName=stack_name, LogicalResourceId="RetrainingTable"
            )["StackResourceDetail"]["PhysicalResourceId"]
        return read_snapshot(session.resource("dynamodb"), outputs["PredictionsTableName"],
                             history, params.get("InferenceImage"))

    return load


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aws", action="store_true", help="read live AWS project data")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    reader = aws_snapshot_reader() if args.aws else lambda: FIXTURE
    with ThreadingHTTPServer(("127.0.0.1", args.port), Preview) as server:
        server.load_snapshot = reader
        server.serve_forever()
