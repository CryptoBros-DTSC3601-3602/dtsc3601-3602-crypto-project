import json
from decimal import Decimal

import boto3
from moto import mock_aws

from src.dashboard import app, snapshot


@mock_aws
def test_pipeline_records_reach_public_dashboard(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TABLE", "dashboard")
    monkeypatch.setenv("PREDICTIONS_TABLE", "predictions")
    monkeypatch.setenv("RETRAINING_TABLE", "training")
    monkeypatch.setenv("INFERENCE_IMAGE", "private-registry/image@sha256:abcd")
    db = boto3.resource("dynamodb")
    tables = {}
    for name, key in (("predictions", "prediction_id"), ("training", "id"), ("dashboard", "id")):
        tables[name] = db.create_table(
            TableName=name, KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    assert json.loads(app.handler({"rawPath": "/api/dashboard"}, None)["body"])["forecast"] is None
    table = tables["predictions"]
    with table.batch_writer() as batch:
        for index in range(102):
            batch.put_item(Item={
                "prediction_id": f"{index:03}", "status": "completed", "prediction": "FLAT",
                "correct": index > 1, "close": Decimal("101.5"), "probabilities": {"FLAT": Decimal("0.6")},
                "inference_image": "private-registry/image@sha256:1234", "raw_s3_key": "private",
            })
    table.put_item(Item={"prediction_id": "999", "status": "pending_sagemaker"})
    tables["training"].put_item(Item={"id": "control", "next_allowed": 1})
    tables["training"].put_item(Item={
        "id": "btc-test", "started_at": 10, "status": "validated",
        "artifact": "s3://private/model.tar.gz", "metrics": {"accuracy": Decimal("0.61"), "test_rows": 151},
    })

    snapshot.handler({}, None)
    public = app.handler({"rawPath": "/api/dashboard"}, None)
    data = json.loads(public["body"])
    assert data["forecast"]["close"] == 101.5
    assert data["forecast"]["model_digest"] == "sha256:1234"
    assert data["active_model_digest"] == "sha256:abcd"
    assert data["accuracy"]["outcomes"] == [1] * 100
    assert data["accuracy"]["total_correct"] == 100
    assert data["accuracy"]["total_scored"] == 102
    assert [run["id"] for run in data["training_runs"]] == ["btc-test"]
    assert data["training_runs"][0]["accuracy"] == 0.61
    assert "private" not in public["body"]
    assert app.handler({"rawPath": "/"}, None)["statusCode"] == 200

    digest = "sha256:" + "f" * 64
    tables["training"].put_item(Item={"id": "control", "active_model": {"run": "btc-test", "digest": digest}})
    table.update_item(Key={"prediction_id": "101"}, UpdateExpression="SET model_digest = :digest",
                      ExpressionAttributeValues={":digest": digest})
    snapshot.handler({}, None)
    released = json.loads(app.handler({"rawPath": "/api/dashboard"}, None)["body"])
    assert released["active_model_digest"] == released["forecast"]["model_digest"] == digest
