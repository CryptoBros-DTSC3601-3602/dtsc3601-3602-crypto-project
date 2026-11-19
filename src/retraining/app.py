"""Reserve at most one retraining run per rolling window and cooldown."""
import hashlib
import heapq
import json
import os
import time
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

WINDOW = 100
COOLDOWN = 7 * 86400


def evaluated_predictions(table):
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
    # Prediction IDs use UTC YYYYMMDDTHHMMSSZ, including historical records.
    newest = heapq.nlargest(WINDOW, rows, key=lambda row: row["prediction_id"])
    if len(newest) < WINDOW:
        return None
    return newest[0]["prediction_id"], sum(row["correct"] for row in newest)


def reserve(db, table, run, window, now):
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


def handler(event, context):
    run = "btc-" + hashlib.sha256(event["execution"].encode()).hexdigest()[:32]
    dynamo = boto3.resource("dynamodb")
    history = dynamo.Table(os.environ["RETRAINING_TABLE"])
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
        return {}
    previous = history.get_item(Key={"id": run}, ConsistentRead=True).get("Item")
    if previous:
        return {"train": previous["status"] == "reserved", "run": run}
    window = rolling_window(evaluated_predictions(dynamo.Table(os.environ["PREDICTIONS_TABLE"])))
    train = bool(window and window[1] < 55 and reserve(
        boto3.client("dynamodb"), history.name, run, window, int(time.time())))
    return {"train": train, "run": run}
