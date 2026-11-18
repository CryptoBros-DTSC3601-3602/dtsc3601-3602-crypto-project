import json

import joblib
import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "return_1",
    "return_3",
    "return_6",
    "return_12",
    "ema_ratio",
    "rsi_14",
    "volatility_12",
    "volume_ratio",
    "range_pct",
    "close_position",
    "buy_volume_ratio",
    "hour_sin",
    "hour_cos",
    "body_pct",
    "upper_wick_pct",
    "lower_wick_pct",
]


def model_fn(model_dir):
    package = joblib.load(f"{model_dir}/btcusdt_direction_15m_60m.joblib")
    return package["model"]


def input_fn(request_body, request_content_type):
    if request_content_type != "application/json":
        raise ValueError(f"Unsupported content type: {request_content_type}")
    payload = json.loads(request_body)
    return pd.DataFrame(payload["candles"])


def create_latest_features(candles):
    frame = candles.copy()
    frame["open_time_utc"] = pd.to_datetime(frame["open_time_utc"], utc=True)
    frame = frame.sort_values("open_time_utc").drop_duplicates("open_time_utc")
    frame = frame.set_index("open_time_utc")

    bars = frame.resample("15min", label="right", closed="right").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "taker_buy_base_asset_volume": "sum",
    }).dropna(subset=["open", "high", "low", "close"])
    bars = bars.reset_index()

    close = bars["close"]
    bars["return_1"] = close.pct_change(1)
    bars["return_3"] = close.pct_change(3)
    bars["return_6"] = close.pct_change(6)
    bars["return_12"] = close.pct_change(12)

    ema_fast = close.ewm(span=6, adjust=False).mean()
    ema_slow = close.ewm(span=18, adjust=False).mean()
    bars["ema_ratio"] = ema_fast / ema_slow - 1

    delta = close.diff()
    gains = delta.clip(lower=0).rolling(14).mean()
    losses = -delta.clip(upper=0).rolling(14).mean()
    relative_strength = gains / losses.replace(0, np.nan)
    bars["rsi_14"] = 100 - (100 / (1 + relative_strength))

    log_return = np.log(close).diff()
    bars["volatility_12"] = log_return.rolling(12).std()
    bars["volume_ratio"] = bars["volume"] / bars["volume"].rolling(12).mean()
    bars["range_pct"] = (bars["high"] - bars["low"]) / bars["close"]
    bars["close_position"] = (
        (bars["close"] - bars["low"])
        / (bars["high"] - bars["low"]).replace(0, np.nan)
    )
    bars["buy_volume_ratio"] = (
        bars["taker_buy_base_asset_volume"] / bars["volume"].replace(0, np.nan)
    )

    hour = bars["open_time_utc"].dt.hour + bars["open_time_utc"].dt.minute / 60
    bars["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    bars["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    bars["body_pct"] = (bars["close"] - bars["open"]) / bars["close"]
    bars["upper_wick_pct"] = (
        bars["high"] - bars[["open", "close"]].max(axis=1)
    ) / bars["close"]
    bars["lower_wick_pct"] = (
        bars[["open", "close"]].min(axis=1) - bars["low"]
    ) / bars["close"]

    bars = bars.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS)
    if bars.empty:
        raise ValueError("Not enough completed candles to create model features.")
    return bars.tail(1)


def predict_fn(latest_candles, model):
    row = create_latest_features(latest_candles)
    probabilities = model.predict_proba(row[FEATURE_COLUMNS])[0]
    predicted_class = int(model.predict(row[FEATURE_COLUMNS])[0])
    return {
        "prediction": {-1: "DOWN", 0: "FLAT", 1: "UP"}[predicted_class],
        "probabilities": {
            {-1: "DOWN", 0: "FLAT", 1: "UP"}[label]: float(probability)
            for label, probability in zip(model.classes_, probabilities)
        },
        "bar_time_utc": row["open_time_utc"].iloc[0].isoformat(),
        "close": float(row["close"].iloc[0]),
    }


def output_fn(prediction, accept):
    if accept != "application/json":
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps(prediction), "application/json"
