"""Train, evaluate and run inference on the bundled candles without AWS access."""
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cryptobros.modeling import predict_latest
from training.train import validate


def main():
    """Print chronological holdout metrics and the last sample candle's forecast."""
    path = PROJECT_ROOT / "data" / "sample_btcusdt_15m.csv"
    candles = pd.read_csv(path)
    model, metrics = validate(candles)
    print(f"Training rows: {metrics['train_rows']} | Test rows: {metrics['test_rows']}")
    print(f"Holdout accuracy: {metrics['accuracy']:.1%}")
    # The latest candle can be forecast before its own one-hour outcome exists.
    print(predict_latest(model, candles))


if __name__ == "__main__":
    main()
