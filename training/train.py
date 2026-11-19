"""SageMaker batch training entrypoint. Only passing candidates emit a model."""
import json
import os
from pathlib import Path

import boto3
import pandas as pd

from feature_engineering import create_features
from historical_backfill import convert_to_csv, fetch_historical_data, TOTAL_CANDLES, INTERVAL_MS
from modeling import save_model, train_direction_model


def validate(candles):
    features = create_features(candles, timeframe="15min", horizon_bars=4, flat_threshold=0.002)
    # Purge four rows so training labels cannot use prices in the holdout.
    return train_direction_model(features, gap_bars=4)


def main():
    bucket = os.environ["DATA_BUCKET"]
    prefix = "retraining/" + os.environ["RUN_ID"]
    rows = fetch_historical_data()
    times = [row["open_time"] for row in rows]
    if len(times) != TOTAL_CANDLES or any(b - a != INTERVAL_MS for a, b in zip(times, times[1:])):
        raise ValueError("Training requires a complete year of consecutive candles")
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=f"{prefix}/candles.csv", Body=convert_to_csv(rows).encode())
    model, metrics = validate(pd.DataFrame(rows))
    s3.put_object(Bucket=bucket, Key=f"{prefix}/metrics.json", Body=json.dumps(metrics).encode())
    save_candidate(model, metrics, Path("/opt/ml/model"))


def save_candidate(model, metrics, directory):
    if not (metrics["test_rows"] > 0 and 0.55 <= metrics["accuracy"] <= 1):
        raise ValueError("Chronological holdout accuracy below candidate quality gate")
    save_model(model, metrics, directory / "btcusdt_direction_15m_60m.joblib")


if __name__ == "__main__":
    main()
