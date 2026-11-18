import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import urlopen

import boto3


TABLE_NAME = os.environ["PREDICTIONS_TABLE"]
FLAT_THRESHOLD = Decimal(os.environ.get("FLAT_THRESHOLD", "0.002"))
HORIZON_MINUTES = int(os.environ.get("HORIZON_MINUTES", "60"))
BINANCE_URL = "https://api.binance.us/api/v3/klines"

table = boto3.resource("dynamodb").Table(TABLE_NAME)


def direction(return_value):
    if return_value > FLAT_THRESHOLD:
        return "UP"
    if return_value < -FLAT_THRESHOLD:
        return "DOWN"
    return "FLAT"


def fetch_candle_at(timestamp):
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


def handler(event, context):
    response = table.scan(
        FilterExpression="#status = :completed AND attribute_not_exists(evaluated_at)",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":completed": "completed"},
    )
    evaluated = 0

    for item in response.get("Items", []):
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
        table.update_item(
            Key={"prediction_id": item["prediction_id"]},
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
        evaluated += 1

    return {"evaluated": evaluated}
