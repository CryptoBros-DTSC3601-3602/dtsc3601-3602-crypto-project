"""Reserve at most one retraining run per rolling window and cooldown."""
import hashlib
import heapq
import json
import math
import os
import re
import time
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

WINDOW = 100
COOLDOWN = 7 * 86400


def evaluated_predictions(table):
    """Yield prediction IDs and boolean outcomes from a consistent, paginated table scan."""
    options = dict(
        ProjectionExpression="prediction_id, correct",
        FilterExpression="attribute_exists(evaluated_at) AND attribute_type(correct, :bool)",
        ExpressionAttributeValues={":bool": "BOOL"},
        ConsistentRead=True,
    )
    while True:
        page = table.scan(**options)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        options["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def rolling_window(rows):
    """Return the newest prediction ID and count correct once a full window exists."""
    # Prediction IDs use UTC YYYYMMDDTHHMMSSZ, including historical records.
    newest = heapq.nlargest(WINDOW, rows, key=lambda row: row["prediction_id"])
    if len(newest) < WINDOW:
        return None
    return newest[0]["prediction_id"], sum(row["correct"] for row in newest)


def reserve(db, table, run, window, now):
    """Claim one eligible window and set its cooldown in the same transaction."""
    latest, score = window
    try:
        db.transact_write_items(TransactItems=[
            {"Update": {
                "TableName": table, "Key": {"id": {"S": "control"}},
                "UpdateExpression": "SET next_allowed = :next, latest_prediction = :latest",
                "ConditionExpression": "(attribute_not_exists(next_allowed) OR next_allowed <= :now) AND (attribute_not_exists(latest_prediction) OR latest_prediction < :latest)",
                "ExpressionAttributeValues": {
                    ":now": {"N": str(now)}, ":next": {"N": str(now + COOLDOWN)},
                    ":latest": {"S": latest},
                },
            }},
            {"Put": {"TableName": table, "Item": {
                "id": {"S": run}, "status": {"S": "reserved"}, "window_end": {"S": latest},
                "correct_of_100": {"N": str(score)}, "started_at": {"N": str(now)},
            }, "ConditionExpression": "attribute_not_exists(id)"}},
        ])
    except ClientError as error:
        reasons = error.response.get("CancellationReasons", [])
        if error.response["Error"]["Code"] == "TransactionCanceledException" and any(
            reason.get("Code") == "ConditionalCheckFailed" for reason in reasons
        ):
            return False
        raise
    return True


def check_serving(run_record, preview=False):
    """Replay archived candles and verify the selected model produced a valid forecast."""
    dynamo = boto3.resource("dynamodb")
    forecast = dynamo.Table(os.environ["PREDICTIONS_TABLE"]).get_item(
        Key={"prediction_id": run_record["window_end"]}, ConsistentRead=True)["Item"]
    obj = boto3.client("s3").get_object(Bucket=os.environ["DATA_BUCKET"], Key=forecast["raw_s3_key"])
    with obj["Body"] as stream:
        payload = {"candles": json.load(stream)["candles"]}
    if preview:
        payload["preview_run"] = run_record["id"]
    response = boto3.client("lambda").invoke(FunctionName=os.environ["INFERENCE_FUNCTION"],
                                             Payload=json.dumps(payload).encode())
    if response.get("FunctionError"):
        raise ValueError("Serving check failed")
    result = json.loads(response["Payload"].read())
    probs = result["probabilities"]
    if not (result["model_run"] == run_record["id"]
            and re.fullmatch(r"sha256:[0-9a-f]{64}", result["model_digest"])
            and result["prediction"] in {"UP", "DOWN", "FLAT"}
            and result["prediction"] in probs and probs.keys() <= {"UP", "DOWN", "FLAT"}
            and all(0 <= p <= 1 for p in probs.values()) and math.isclose(sum(probs.values()), 1)
            and 0 < result["close"] < math.inf and result["bar_time_utc"]):
        raise ValueError("Invalid candidate forecast")
    return {"run": run_record["id"], "digest": result["model_digest"]}


def switch_model(table, record, previous, target, rollback=False):
    """Atomically update the model selected for inference and its release history."""
    # Change the serving pointer and release history together, including on retry.
    encode = TypeSerializer().serialize
    expected, status = ("verifying", "rolled_back") if rollback else ("validated", "verifying")
    control_values = {":target": encode(target), ":previous": encode(previous)}
    condition = "active_model = :previous"
    if not previous:
        condition = "(" + condition + " OR attribute_not_exists(active_model))"
    history_values = {":expected": encode(expected), ":status": encode(status)}
    update = "SET #s = :status"
    if not rollback:
        condition += " AND latest_prediction = :window"
        control_values[":window"] = encode(record["window_end"])
        update += ", previous_model = :previous, candidate_model = :candidate"
        history_values.update({":previous": encode(previous), ":candidate": encode(target)})
    boto3.client("dynamodb").transact_write_items(TransactItems=[
        {"Update": {"TableName": table.name, "Key": {"id": encode("control")},
                    "ConditionExpression": condition, "UpdateExpression": "SET active_model = :target",
                    "ExpressionAttributeValues": control_values}},
        {"Update": {"TableName": table.name, "Key": {"id": encode(record["id"])},
                    "ConditionExpression": "#s = :expected", "UpdateExpression": update,
                    "ExpressionAttributeNames": {"#s": "status"}, "ExpressionAttributeValues": history_values}},
    ])


def release(table, run, action):
    """Apply a promotion, verification or recovery command to a recorded run. Check its state before switching or restoring the serving model."""
    record = table.get_item(Key={"id": run}, ConsistentRead=True)["Item"]
    status = record["status"]
    if action == "promote":
        if status in ("deployed", "verifying"):
            return
        expected_uri = f"s3://{os.environ['DATA_BUCKET']}/retraining/artifacts/{run}/output/model.tar.gz"
        if status != "validated" or record["artifact"] != expected_uri:
            raise ValueError("Release requires the validated artifact from this run")
        target = check_serving(record, preview=True)
        control = table.get_item(Key={"id": "control"}, ConsistentRead=True)["Item"]
        switch_model(table, record, control.get("active_model", {}), target)
        return
    if action == "recover":
        if status == "verifying":
            switch_model(table, record, record["candidate_model"], record["previous_model"], rollback=True)
            return
        if status in ("rolled_back", "release_failed", "deployed"):
            return
        expected, final = "validated", "release_failed"
    elif action == "verify":
        if status == "deployed":
            return
        if status != "verifying" or check_serving(record) != record["candidate_model"]:
            raise ValueError("Production did not serve the selected candidate")
        expected, final = "verifying", "deployed"
    else:
        raise ValueError("Unknown release action")
    table.update_item(Key={"id": run}, UpdateExpression="SET #s = :final",
                      ConditionExpression="#s = :expected", ExpressionAttributeNames={"#s": "status"},
                      ExpressionAttributeValues={":expected": expected, ":final": final})


def handler(event, context):
    """Handle eligibility, training status and release commands from Step Functions."""
    run = "btc-" + hashlib.sha256(event["execution"].encode()).hexdigest()[:32]
    dynamo = boto3.resource("dynamodb")
    history = dynamo.Table(os.environ["RETRAINING_TABLE"])
    if event.get("release_action"):
        release(history, run, event["release_action"])
        return {}
    if event.get("status"):
        values = {":status": event["status"]}
        names = {"#s": "status"}
        update = "SET #s = :status"
        if event["status"] == "validated":
            bucket = os.environ["DATA_BUCKET"]
            report = boto3.client("s3").get_object(Bucket=bucket, Key=f"retraining/{run}/metrics.json")
            metrics = json.loads(report["Body"].read(), parse_float=Decimal)
            values.update({":metrics": metrics, ":artifact": event["artifact"]})
            names.update({"#metrics": "metrics", "#artifact": "artifact"})
            update += ", #metrics = :metrics, #artifact = :artifact"
        history.update_item(Key={"id": run}, UpdateExpression=update,
                            ConditionExpression="attribute_exists(id)",
                            ExpressionAttributeNames=names, ExpressionAttributeValues=values)
        return {"auto_release": bool(os.getenv("INFERENCE_FUNCTION"))}
    previous = history.get_item(Key={"id": run}, ConsistentRead=True).get("Item")
    if previous:
        return {"train": previous["status"] == "reserved", "run": run}
    window = rolling_window(evaluated_predictions(dynamo.Table(os.environ["PREDICTIONS_TABLE"])))
    train = bool(window and window[1] < 55 and reserve(
        boto3.client("dynamodb"), history.name, run, window, int(time.time())))
    return {"train": train, "run": run}
