from pathlib import Path

import boto3
import joblib
import pandas as pd
import pytest
from moto import mock_aws

from src.retraining import app
from training.train import save_candidate, training_features, validate


@pytest.fixture
def tables(monkeypatch):
    monkeypatch.setenv("RETRAINING_TABLE", "history")
    monkeypatch.setenv("PREDICTIONS_TABLE", "predictions")
    with mock_aws():
        dynamo = boto3.resource("dynamodb", region_name="us-east-2")
        for name, key in (("history", "id"), ("predictions", "prediction_id")):
            dynamo.create_table(TableName=name, KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
                                AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
                                BillingMode="PAY_PER_REQUEST")
        yield dynamo.Table("predictions"), dynamo.Table("history")


def test_decision_and_atomic_cooldown(tables, monkeypatch):
    predictions, history = tables
    now = 2000000000
    monkeypatch.setattr(app, "time", type("Clock", (), {"time": lambda: now}))
    def check(execution):
        return app.handler({"execution": execution}, None)["train"]

    with predictions.batch_writer() as writer:
        for n in range(99):
            writer.put_item(Item={"prediction_id": f"{n:03}", "correct": n < 55, "evaluated_at": "done"})
        writer.put_item(Item={"prediction_id": "999", "status": "pending_sagemaker"})
    assert not check("short")
    predictions.put_item(Item={"prediction_id": "099", "correct": False, "evaluated_at": "done"})
    assert not check("exactly55")
    predictions.put_item(Item={"prediction_id": "100", "correct": False, "evaluated_at": "done"})
    assert check("first")
    assert check("first")  # replay recovers the same reservation and training job name
    assert not check("competitor")
    predictions.put_item(Item={"prediction_id": "101", "correct": False, "evaluated_at": "done"})
    now += app.COOLDOWN - 1
    assert not check("early")
    now += 1
    assert check("second")
    app.handler({"execution": "second", "status": "failed"}, None)
    assert not check("second")
    now += app.COOLDOWN
    assert not check("same-window")
    assert history.scan()["Count"] == 3


def test_paginated_scan_advances_past_empty_page():
    class Table:
        def scan(self, **options):
            if "ExclusiveStartKey" not in options:
                return {"Items": [], "LastEvaluatedKey": {"prediction_id": "x"}}
            assert options["ExclusiveStartKey"] == {"prediction_id": "x"}
            return {"Items": [{"prediction_id": "y", "correct": True}]}
    assert list(app.evaluated_predictions(Table())) == [{"prediction_id": "y", "correct": True}]


def test_training_and_quality_gate(tmp_path):
    candles = pd.read_csv(Path(__file__).resolve().parents[1] / "data/sample_btcusdt_15m.csv")
    model, metrics = validate(candles)
    assert metrics["train_rows"] == 136
    assert metrics["test_rows"] == 35
    assert metrics["importance"]["rows"] == 35
    assert "volatility_12" in metrics["importance"]["scores"]
    with pytest.raises(ValueError):
        save_candidate(model, {**metrics, "accuracy": 0.549}, tmp_path)
    assert not list(tmp_path.iterdir())
    save_candidate(model, {**metrics, "accuracy": 0.55}, tmp_path)
    assert joblib.load(tmp_path / "btcusdt_direction_15m_60m.joblib")["model"].classes_.size == 3


def test_exchange_gap_resets_features_and_excludes_cross_gap_targets():
    candles = pd.read_csv(Path(__file__).resolve().parents[1] / "data/sample_btcusdt_15m.csv")
    before, after = candles.iloc[:100], candles.iloc[106:]
    actual = training_features(pd.concat([before, after]))
    expected = pd.concat([training_features(before), training_features(after)], ignore_index=True)
    pd.testing.assert_frame_equal(actual, expected)
    assert not actual.empty


def test_candidate_history_records_version_and_metrics(tables, monkeypatch):
    _, history = tables
    import hashlib
    import json
    from decimal import Decimal

    execution = "workflow-execution"
    run = "btc-" + hashlib.sha256(execution.encode()).hexdigest()[:32]
    history.put_item(Item={"id": run, "status": "reserved", "correct_of_100": 49})
    monkeypatch.setenv("DATA_BUCKET", "training-fixture")
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket="training-fixture", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    s3.put_object(Bucket="training-fixture", Key=f"retraining/{run}/metrics.json",
                  Body=json.dumps({"accuracy": 0.6, "test_rows": 35}).encode())
    artifact = f"s3://training-fixture/retraining/artifacts/{run}/output/model.tar.gz"
    event = {"execution": execution, "status": "validated", "artifact": artifact}
    app.handler(event, None)
    app.handler(event, None)
    item = history.get_item(Key={"id": run})["Item"]
    assert item["status"] == "validated"
    assert item["metrics"]["accuracy"] == Decimal("0.6")
    assert item["artifact"] == artifact
    assert item["correct_of_100"] == 49


@pytest.mark.parametrize("verify_ok", [True, False])
@pytest.mark.parametrize("previous", [{}, {"run": "prior", "digest": "sha256:previous"}])
def test_release_and_recovery_are_atomic_and_retryable(tables, monkeypatch, verify_ok, previous):
    _, table = tables
    monkeypatch.setenv("DATA_BUCKET", "project")
    run = "btc-" + "1" * 32
    target = {"run": run, "digest": "sha256:" + "1" * 64}
    control = {"id": "control", "latest_prediction": "100"}
    if previous:
        control["active_model"] = previous
    table.put_item(Item=control)
    table.put_item(Item={"id": run, "status": "validated", "window_end": "100",
                         "artifact": f"s3://project/retraining/artifacts/{run}/output/model.tar.gz"})

    def check(record, preview=False):
        if preview or verify_ok:
            return target
        raise ValueError("Verification failed")

    def get(key):
        return table.get_item(Key={"id": key})["Item"]

    monkeypatch.setattr(app, "check_serving", check)
    for _ in range(2):
        app.release(table, run, "promote")
    assert get("control")["active_model"] == target
    assert get(run)["previous_model"] == previous
    if verify_ok:
        for _ in range(2):
            app.release(table, run, "verify")
        assert get(run)["status"] == "deployed"
    else:
        with pytest.raises(ValueError, match="Verification failed"):
            app.release(table, run, "verify")
        for _ in range(2):
            app.release(table, run, "recover")
        assert get("control")["active_model"] == previous
        assert get(run)["status"] == "rolled_back"


def test_failed_preview_keeps_current_selection(tables, monkeypatch):
    _, table = tables
    monkeypatch.setenv("DATA_BUCKET", "project")
    table.put_item(Item={"id": "blocked", "status": "validated", "artifact": "wrong"})
    with pytest.raises(ValueError, match="validated artifact"):
        app.release(table, "blocked", "promote")
    app.release(table, "blocked", "recover")
    assert table.get_item(Key={"id": "blocked"})["Item"]["status"] == "release_failed"
    assert "Item" not in table.get_item(Key={"id": "control"})


def test_private_release_probe_replays_archived_forecast_and_checks_identity(tables, monkeypatch):
    import io
    import json
    from unittest.mock import Mock

    predictions, _ = tables
    monkeypatch.setenv("DATA_BUCKET", "probe-candles")
    monkeypatch.setenv("INFERENCE_FUNCTION", "private")
    key = "serverless/predictions/raw/binance/BTCUSDT/sample.json"
    predictions.put_item(Item={"prediction_id": "100", "raw_s3_key": key})
    candles = [{"close": 100}]
    clients = boto3.client
    s3 = clients("s3")
    s3.create_bucket(Bucket="probe-candles", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    s3.put_object(Bucket="probe-candles", Key=key, Body=json.dumps({"candles": candles}))
    run = "btc-" + "2" * 32
    digest = "sha256:" + "1" * 64
    result = dict(model_run=run, model_digest=digest, probabilities={"FLAT": 1},
                  close=100, prediction="FLAT", bar_time_utc="2026-11-21T12:00:00Z")
    function = Mock()
    function.invoke.side_effect = lambda **kwargs: {"Payload": io.BytesIO(json.dumps(result).encode())}
    monkeypatch.setattr(app.boto3, "client", lambda name: function if name == "lambda" else clients(name))
    record = {"id": run, "window_end": "100"}
    assert app.check_serving(record, preview=True) == {"run": run, "digest": digest}
    assert json.loads(function.invoke.call_args.kwargs["Payload"]) == {"candles": candles, "preview_run": run}
    result["model_run"] = "baseline"
    with pytest.raises(ValueError, match="Invalid candidate forecast"):
        app.check_serving(record)
    assert json.loads(function.invoke.call_args.kwargs["Payload"]) == {"candles": candles}
