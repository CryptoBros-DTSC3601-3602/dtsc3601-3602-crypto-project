"""Publish a sanitized public snapshot on the dashboard schedule."""
import heapq
import json
import os
from datetime import datetime, timezone

import boto3


def scan(table, projection, filter_expression, names, values):
    options = {
        "ProjectionExpression": projection,
        "FilterExpression": filter_expression,
        "ExpressionAttributeNames": names,
    }
    if values:
        options["ExpressionAttributeValues"] = values
    while True:
        page = table.scan(**options)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        options["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def model_digest(image):
    if not image:
        return None
    _, separator, digest = image.partition("@sha256:")
    return "sha256:" + digest if separator else None


def build_snapshot(newest, history, image):
    if newest:
        forecast = {key: newest.get(key) for key in ("prediction", "created_at", "bar_time_utc")}
        forecast["close"] = float(newest["close"]) if newest.get("close") is not None else None
        forecast["probabilities"] = {
            label: float(probability)
            for label, probability in newest.get("probabilities", {}).items()
            if label in {"UP", "DOWN", "FLAT"}
        }
        forecast["model_digest"] = model_digest(newest.get("inference_image"))
    else:
        forecast = None

    runs = []
    for run in heapq.nlargest(10, history, key=lambda row: (row["started_at"], row["id"])):
        metrics = run.get("metrics", {})
        runs.append({
            "id": run["id"],
            "started_at": datetime.fromtimestamp(int(run["started_at"]), timezone.utc).isoformat(),
            "status": run["status"],
            "accuracy": float(metrics["accuracy"]) if "accuracy" in metrics else None,
            "test_rows": int(metrics["test_rows"]) if "test_rows" in metrics else None,
        })
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": forecast,
        "training_runs": runs,
        "active_model_digest": model_digest(image),
    }


def handler(event, context):
    dynamo = boto3.resource("dynamodb")
    completed = scan(
        dynamo.Table(os.environ["PREDICTIONS_TABLE"]),
        "prediction_id, prediction, created_at, bar_time_utc, #close, probabilities, inference_image, correct",
        "#status = :completed", {"#status": "status", "#close": "close"}, {":completed": "completed"},
    )
    latest = None
    # Keep a bounded, chronologically sorted heap while reading all scan pages.
    evaluated = []
    for row in completed:
        key = row["prediction_id"]
        if row.get("prediction") in {"UP", "DOWN", "FLAT"} and (
            latest is None or key > latest["prediction_id"]
        ):
            latest = row
        if isinstance(row.get("correct"), bool):
            entry = (key, row["correct"])
            if len(evaluated) < 100:
                heapq.heappush(evaluated, entry)
            else:
                heapq.heappushpop(evaluated, entry)

    history_table = os.getenv("RETRAINING_TABLE")
    history = scan(dynamo.Table(history_table), "id, started_at, #status, #metrics",
                   "attribute_exists(started_at)", {"#status": "status", "#metrics": "metrics"},
                   {}) if history_table else []
    snapshot = build_snapshot(latest, history, os.getenv("INFERENCE_IMAGE"))
    snapshot["accuracy"] = {"outcomes": [int(correct) for _, correct in sorted(evaluated)]}
    snapshot["training_configured"] = bool(history_table)
    dynamo.Table(os.environ["DASHBOARD_TABLE"]).put_item(
        Item={"id": "dashboard", "payload": json.dumps(snapshot)}
    )
    return {"published": True}
