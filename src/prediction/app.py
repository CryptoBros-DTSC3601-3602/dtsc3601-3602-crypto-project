import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

import boto3


REGION = os.environ["AWS_REGION"]
BUCKET_NAME = os.environ["DATA_BUCKET"]
TABLE_NAME = os.environ["PREDICTIONS_TABLE"]
SAGEMAKER_ENDPOINT = os.environ.get("SAGEMAKER_ENDPOINT", "")

INFERENCE_IMAGE = os.environ.get("INFERENCE_IMAGE", "")
INFERENCE_FUNCTION = os.environ.get("INFERENCE_FUNCTION", "")

BINANCE_URL = "https://api.binance.us/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "15m"
LIMIT = 120

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
sagemaker = boto3.client("sagemaker-runtime", region_name=REGION)
predictions = dynamodb.Table(TABLE_NAME)


def utc_now():
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def iso_utc(value):
    """Format an aware datetime in UTC with a trailing Z for storage."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def ms_to_iso(timestamp_ms):
    """Convert an exchange timestamp in Unix milliseconds to an ISO UTC timestamp."""
    return iso_utc(datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc))


def fetch_candles():
    """Request recent BTCUSDT bars and return up to 120 completed candles with numeric prices and UTC timestamps."""
    params = urlencode({
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT + 1,
    })

    with urlopen(f"{BINANCE_URL}?{params}", timeout=15) as response:
        raw = json.load(response)

    now_ms = int(utc_now().timestamp() * 1000)
    completed = [candle for candle in raw if candle[6] < now_ms][-LIMIT:]

    candles = []
    for candle in completed:
        candles.append({
            "open_time": candle[0],
            "open_time_utc": ms_to_iso(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
            "close_time": candle[6],
            "close_time_utc": ms_to_iso(candle[6]),
            "quote_asset_volume": float(candle[7]),
            "number_of_trades": candle[8],
            "taker_buy_base_asset_volume": float(candle[9]),
            "taker_buy_quote_asset_volume": float(candle[10]),
        })
    return candles


def decimal(value):
    """Convert a numeric value through its string representation for DynamoDB decimal storage."""
    return Decimal(str(value))


def invoke_prediction(candles):
    """Send candles to the configured inference service and return the forecast record. Mark the record pending when no service is configured."""
    if INFERENCE_FUNCTION:
        response = boto3.client("lambda", region_name=REGION).invoke(
            FunctionName=INFERENCE_FUNCTION,
            Payload=json.dumps({"candles": candles}).encode(),
        )
        if response.get("FunctionError"):
            raise RuntimeError("Private inference Lambda failed")
        body = json.loads(response["Payload"].read())
        body["status"] = "completed"
        return body
    if not SAGEMAKER_ENDPOINT:
        return {
            "status": "pending_sagemaker",
            "prediction": None,
            "probabilities": {},
        }

    response = sagemaker.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType="application/json",
        Accept="application/json",
        Body=json.dumps({"candles": candles}),
    )
    body = json.loads(response["Body"].read())
    body["status"] = "completed"
    return body


def store_raw_data(now, candles):
    """Write the input candle window to a timestamped S3 object and return its key for forecast replay."""
    key = (
        f"serverless/predictions/raw/binance/{SYMBOL}/"
        f"{now.strftime('%Y/%m/%d/%H-%M-%S')}.json"
    )
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps({
            "source": "Binance.US",
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "ingested_at_utc": iso_utc(now),
            "candle_count": len(candles),
            "candles": candles,
        }),
        ContentType="application/json",
    )
    return key


def handler(event, context):
    """Archive the completed candle window and record its one-hour forecast and model identity."""
    now = utc_now()

    try:
        candles = fetch_candles()
        raw_key = store_raw_data(now, candles)
        prediction = invoke_prediction(candles)

        latest = candles[-1] if candles else {}
        latest_close = prediction.get("close", latest.get("close"))
        prediction_id = now.strftime("%Y%m%dT%H%M%SZ")
        item = {
            "prediction_id": prediction_id,
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "horizon_minutes": 60,
            "created_at": iso_utc(now),
            "bar_time_utc": prediction.get("bar_time_utc", latest.get("open_time_utc")),
            "close": decimal(latest_close) if latest_close is not None else None,
            "status": prediction["status"],
            "prediction": prediction.get("prediction"),
            "probabilities": {
                label: decimal(probability)
                for label, probability in prediction.get("probabilities", {}).items()
            },
            "raw_s3_key": raw_key,
            "endpoint_name": (SAGEMAKER_ENDPOINT or None) if not INFERENCE_FUNCTION else None,
            "inference_function": INFERENCE_FUNCTION or None,
            "model_digest": prediction.get("model_digest") or None,
            "model_run": prediction.get("model_run"),
            "inference_image": (INFERENCE_IMAGE or None) if INFERENCE_FUNCTION else None,
        }

        predictions.put_item(Item={key: value for key, value in item.items() if value is not None})

        return {
            "statusCode": 200,
            "body": json.dumps({
                "prediction_id": prediction_id,
                "prediction_status": prediction["status"],
                "candle_count": len(candles),
                "raw_s3_key": raw_key,
            }),
        }
    except (HTTPError, URLError, TimeoutError) as error:
        print(json.dumps({"error": "market_data_fetch_failed", "detail": str(error)}))
        raise
