import importlib.util
import os
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("PREDICTIONS_TABLE", "test-table")

module_path = Path(__file__).resolve().parents[1] / "src" / "evaluation" / "app.py"
module_spec = importlib.util.spec_from_file_location("evaluation_app", module_path)
app = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(app)


def test_direction_uses_flat_threshold():
    assert app.direction(Decimal("0.003")) == "UP"
    assert app.direction(Decimal("-0.003")) == "DOWN"
    assert app.direction(Decimal("0.001")) == "FLAT"
