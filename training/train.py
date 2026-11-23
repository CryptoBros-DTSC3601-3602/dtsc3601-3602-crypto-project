"""SageMaker batch training entrypoint. Only passing candidates emit a model."""
import json
import os
from pathlib import Path

import boto3
import pandas as pd

from cryptobros.feature_engineering import create_features
from cryptobros.historical_backfill import convert_to_csv, fetch_historical_data, TOTAL_CANDLES, INTERVAL_MS
from cryptobros.modeling import save_model, train_direction_model


def training_features(candles):
    """Build labeled rows independently inside consecutive 15-minute candle segments."""
    times = candles["open_time"]
    if not times.is_monotonic_increasing or not times.is_unique or (times % INTERVAL_MS != 0).any():
        raise ValueError("Training candles must be ordered, unique and on 15-minute boundaries")
    # Restart indicators and discard incomplete targets at each exchange data gap.
    segments = times.diff().ne(INTERVAL_MS).cumsum()
    return pd.concat([
        create_features(segment, timeframe="15min", horizon_bars=4, flat_threshold=0.002)
        for _, segment in candles.groupby(segments, sort=False)
    ], ignore_index=True)


def validate(candles):
    """Fit on earlier candles and return the estimator and chronological holdout metrics."""
    features = training_features(candles)
    # Purge four rows so training labels cannot use prices in the holdout.
    return train_direction_model(features, gap_bars=4, explain=True)


def main():
    """Download the annual candle window, train and write run-specific inputs and metrics to S3. Emit a model artifact only if validation passes."""
    bucket = os.environ["DATA_BUCKET"]
    prefix = "retraining/" + os.environ["RUN_ID"]
    rows = fetch_historical_data()
    if not 0.99 * TOTAL_CANDLES <= len(rows) <= TOTAL_CANDLES:
        raise ValueError("Training requires at least 99% of the year's 15-minute candles")
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=f"{prefix}/candles.csv", Body=convert_to_csv(rows).encode())
    model, metrics = validate(pd.DataFrame(rows))
    metrics["observed_candles"] = len(rows)
    metrics["missing_candles"] = TOTAL_CANDLES - len(rows)
    s3.put_object(Bucket=bucket, Key=f"{prefix}/metrics.json", Body=json.dumps(metrics).encode())
    save_candidate(model, metrics, Path("/opt/ml/model"))


def save_candidate(model, metrics, directory):
    """Write the serving artifact only when the holdout meets the release threshold."""
    if not (metrics["test_rows"] > 0 and 0.55 <= metrics["accuracy"] <= 1):
        raise ValueError("Chronological holdout accuracy below candidate quality gate")
    save_model(model, metrics, directory / "btcusdt_direction_15m_60m.joblib")


if __name__ == "__main__":
    main()
