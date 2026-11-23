"""Private synchronous Lambda entrypoint for the packaged direction model."""
import hashlib
import io
import os
import re
from functools import lru_cache
from pathlib import Path

import boto3
import joblib
import pandas as pd

from inference import model_fn, predict_fn
from candidate_artifact import read_candidate


model = model_fn(Path(__file__).parent)


@lru_cache(maxsize=2)
def candidate(run, expected_digest):
    """Load a trusted run's S3 model and return the fitted estimator and SHA-256 digest. Reject invalid run IDs, oversized archives or digest mismatches."""
    if not re.fullmatch(r"btc-[0-9a-f]{32}", run):
        raise ValueError("Invalid training run")
    obj = boto3.client("s3").get_object(Bucket=os.environ["DATA_BUCKET"],
        Key=f"retraining/artifacts/{run}/output/model.tar.gz")
    with obj["Body"] as stream:
        if obj["ContentLength"] > 34 * 1024 * 1024:
            raise ValueError("Oversized candidate")
        raw, _ = read_candidate(io.BytesIO(stream.read()))
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if expected_digest and expected_digest != digest:
        raise ValueError("Candidate digest mismatch")
    return joblib.load(io.BytesIO(raw))["model"], digest


def handler(event, context):
    """Load the selected model and return its identity with a forecast for the supplied candles."""
    selected = {}
    if event.get("preview_run"):
        selected = {"run": event["preview_run"]}
    elif os.getenv("RETRAINING_TABLE"):
        table = boto3.resource("dynamodb").Table(os.environ["RETRAINING_TABLE"])
        control = table.get_item(Key={"id": "control"}, ConsistentRead=True).get("Item", {})
        selected = control.get("active_model", {})
    estimator, digest = (candidate(selected["run"], selected.get("digest")) if selected
                         else (model, os.getenv("INFERENCE_IMAGE", "").partition("@")[2]))
    result = predict_fn(pd.DataFrame(event["candles"]), estimator)
    result.update(model_digest=digest, model_run=selected.get("run", "baseline"))
    return result
