"""Private synchronous Lambda entrypoint for the packaged direction model."""
from pathlib import Path

import pandas as pd

from inference import model_fn, predict_fn


model = model_fn(Path(__file__).parent)


def handler(event, context):
    return predict_fn(pd.DataFrame(event["candles"]), model)
