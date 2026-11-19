from pathlib import Path

import boto3
import joblib
import pandas as pd
import pytest
from moto import mock_aws

from src.retraining import app
from training.train import save_candidate, validate


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
    with pytest.raises(ValueError):
        save_candidate(model, {**metrics, "accuracy": 0.549}, tmp_path)
    assert not list(tmp_path.iterdir())
    save_candidate(model, {**metrics, "accuracy": 0.55}, tmp_path)
    assert joblib.load(tmp_path / "btcusdt_direction_15m_60m.joblib")["model"].classes_.size == 3


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
