import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import urlopen

import boto3
from botocore.exceptions import ClientError


TABLE_NAME = os.environ["PREDICTIONS_TABLE"]
FLAT_THRESHOLD = Decimal(os.environ.get("FLAT_THRESHOLD", "0.002"))
HORIZON_MINUTES = int(os.environ.get("HORIZON_MINUTES", "60"))
BINANCE_URL = "https://api.binance.us/api/v3/klines"

table = boto3.resource("dynamodb").Table(TABLE_NAME)


def direction(return_value):
    """Map a realized return to a class; both threshold endpoints count as FLAT."""
    if return_value > FLAT_THRESHOLD:
        return "UP"
    if return_value < -FLAT_THRESHOLD:
        return "DOWN"
    return "FLAT"


def fetch_candle_at(timestamp):
    """Fetch the close for the target candle as a Decimal. Return None while the market candle is unavailable or open."""
    target_ms = int(timestamp.timestamp() * 1000)
    query = urlencode({
        "symbol": "BTCUSDT",
        "interval": "15m",
        "startTime": target_ms,
        "limit": 1,
    })
    with urlopen(f"{BINANCE_URL}?{query}", timeout=15) as response:
        candles = json.load(response)
    if not candles or candles[0][6] >= int(datetime.now(timezone.utc).timestamp() * 1000):
        return None
    return Decimal(str(candles[0][4]))


def pending_items():
    """Yield completed, unscored records across every DynamoDB scan page."""
    options = {
        "FilterExpression": "#status = :completed AND attribute_not_exists(evaluated_at)",
        "ExpressionAttributeNames": {"#status": "status"},
        "ExpressionAttributeValues": {":completed": "completed"},
    }
    while True:
        page = table.scan(**options)
        yield from page["Items"]
        if "LastEvaluatedKey" not in page:
            return
        options["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def handler(event, context):
    """Score mature forecasts against the target candle and skip previously evaluated rows."""
    evaluated = 0
    for item in pending_items():
        bar_time = datetime.fromisoformat(item["bar_time_utc"].replace("Z", "+00:00"))
        target_time = bar_time + timedelta(minutes=HORIZON_MINUTES)
        if target_time > datetime.now(timezone.utc):
            continue

        actual_close = fetch_candle_at(target_time)
        if actual_close is None:
            continue

        predicted_close = Decimal(str(item["close"]))
        actual_direction = direction(actual_close / predicted_close - 1)
        correct = actual_direction == item["prediction"]
        try:
            table.update_item(
                Key={"prediction_id": item["prediction_id"]},
                ConditionExpression="attribute_not_exists(evaluated_at) AND attribute_exists(prediction_id)",
                UpdateExpression=(
                    "SET evaluated_at = :evaluated, actual_close = :actual_close, "
                    "actual_direction = :actual_direction, correct = :correct"
                ),
                ExpressionAttributeValues={
                    ":evaluated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    ":actual_close": actual_close,
                    ":actual_direction": actual_direction,
                    ":correct": correct,
                },
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                continue
            raise
        evaluated += 1

    return {"evaluated": evaluated}
