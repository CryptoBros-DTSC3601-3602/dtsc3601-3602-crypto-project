"""Serve the website and its public, read-only JSON endpoint."""
import json
import os
from pathlib import Path

import boto3


STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
}


def response(status, body, content_type, cache="no-store"):
    return {
        "statusCode": status,
        "headers": {
            "content-type": content_type,
            "cache-control": cache,
            "x-content-type-options": "nosniff",
            "content-security-policy": "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        },
        "body": body,
    }


def handler(event, context):
    path = event.get("rawPath", "/")
    if path in FILES:
        filename, content_type = FILES[path]
        return response(200, (STATIC / filename).read_text(encoding="utf-8"),
                        content_type, "public, max-age=300")
    if path != "/api/dashboard":
        return response(404, "Not found", "text/plain")

    item = boto3.resource("dynamodb").Table(os.environ["DASHBOARD_TABLE"]).get_item(
        Key={"id": "dashboard"}
    ).get("Item")
    body = item["payload"] if item else json.dumps({
        "updated_at": None, "forecast": None, "accuracy": {"outcomes": []},
        "training_runs": [], "training_configured": None, "active_model_digest": None,
    })
    return response(200, body, "application/json", "public, max-age=60")
