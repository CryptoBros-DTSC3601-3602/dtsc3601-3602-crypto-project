import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "prediction"))

os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("DATA_BUCKET", "test-bucket")
os.environ.setdefault("PREDICTIONS_TABLE", "test-table")

import app


def test_ms_to_iso():
    assert app.ms_to_iso(0) == "1970-01-01T00:00:00Z"


def test_decimal():
    assert str(app.decimal(100123.45)) == "100123.45"


def test_private_prediction_saved_for_evaluation(monkeypatch):
    import io
    import json
    from unittest.mock import Mock

    candles = [{"open_time_utc": "2026-01-02T00:00:00Z", "close": 101}]
    inferred = {"prediction": "FLAT", "probabilities": {"FLAT": 0.6}, "model_digest": "sha256:456",
                "close": 100, "bar_time_utc": "2026-01-01T23:45:00Z"}
    client = Mock()
    client.invoke.return_value = {"Payload": io.BytesIO(json.dumps(inferred).encode())}
    monkeypatch.setattr(app.boto3, "client", lambda *args, **kwargs: client)
    monkeypatch.setattr(app, "INFERENCE_FUNCTION", "private-inference")
    monkeypatch.setattr(app, "INFERENCE_IMAGE", "candidate@sha256:123")
    monkeypatch.setattr(app, "fetch_candles", lambda: candles)
    monkeypatch.setattr(app, "store_raw_data", lambda now, rows: "sample")
    table = Mock()
    monkeypatch.setattr(app, "predictions", table)
    app.handler({}, None)
    item = table.put_item.call_args.kwargs["Item"]
    assert json.loads(client.invoke.call_args.kwargs["Payload"]) == {"candles": candles}
    assert (item["status"], item["prediction"], item["close"]) == ("completed", "FLAT", 100)
    assert item["bar_time_utc"] == inferred["bar_time_utc"]
    assert item["inference_function"] == "private-inference"
    assert item["inference_image"] == "candidate@sha256:123"
    assert item["model_digest"] == "sha256:456"


def test_function_error_cannot_be_recorded_as_prediction(monkeypatch):
    from unittest.mock import Mock
    import pytest

    client = Mock()
    client.invoke.return_value = {"FunctionError": "Unhandled"}
    monkeypatch.setattr(app, "INFERENCE_FUNCTION", "private-inference")
    monkeypatch.setattr(app.boto3, "client", lambda *args, **kwargs: client)
    with pytest.raises(RuntimeError, match="inference Lambda failed"):
        app.invoke_prediction([])
