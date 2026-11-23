# Forecasting walkthrough

## 1. Train and evaluate locally

Open the repository root in PowerShell and follow **Install locally** and **Run the project** in the [README](../README.md). The bundled CSV has 200 completed candles. The example discards indicator warm-up rows and rows without a future label, then reserves the last 20% of usable examples for evaluation. A four-bar gap prevents training labels from reaching into the test period.

You should see 136 training rows, 35 test rows, holdout accuracy, and a forecast dictionary. Accuracy is the fraction of correct direction labels among those 35 examples. A single additional correct prediction changes it by about 2.9 percentage points.

## 2. Save a model and inspect a forecast

Start the installed interpreter with `.\.venv\Scripts\python` and enter the following Python from the repository root:

```python
import joblib
import pandas as pd
from training.train import validate
from cryptobros.modeling import predict_latest, save_model

candles = pd.read_csv("data/sample_btcusdt_15m.csv")
model, metrics = validate(candles)
print(metrics["confusion_matrix"])
save_model(model, metrics, "models/student.joblib")
saved = joblib.load("models/student.joblib")
print(predict_latest(saved["model"], candles))
```

The confusion matrix uses DOWN, FLAT, UP on both axes. Rows are observed classes and columns are predictions. Inspect the off-diagonal counts to see which directions are confused. The forecast's timestamp identifies the candle used for inference. Its probabilities describe each direction one hour later. Type `exit()` to leave Python.

## 3. Explore the dashboard and diagnose problems

Run `.\.venv\Scripts\python bin/preview_dashboard.py` and open `http://127.0.0.1:8000`. The local site labels its sample data. Press Ctrl+C to stop it. On the live site, compare the sample counts for the latest 100 and all-time accuracy. Feature importance shows the average change in accuracy after shuffling one input. Its evaluation dates describe the model explanation sample.

If features are empty, check the candle columns, chronological order and window length. Start with the complete sample CSV. If live accuracy is empty, compare the forecast issue time with its one-hour horizon and the next evaluation job. In AWS, inspect the forecast's DynamoDB record and the evaluation Lambda logs before diagnosing model quality. For release problems, inspect Step Functions execution history and the run's S3 metrics.

To run regression checks locally in PowerShell:

```powershell
.\.venv\Scripts\python -m pip install -r tests/requirements.txt
$env:AWS_DEFAULT_REGION = "us-east-2"
$env:AWS_EC2_METADATA_DISABLED = "true"
.\.venv\Scripts\python -m pytest -q tests
```

The AWS-backed notebooks under `notebooks/` use the project S3 profile. The offline tutorial and sample dashboard require only the checked-in data. Keep credentials in your own AWS profile.
