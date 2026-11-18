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
