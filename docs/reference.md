# Class and function reference

Follow a forecast through the sections below. Each entry explains what the caller supplies, how the routine uses it and what the next stage receives.

## Local dashboard

The preview serves the same interface as the public dashboard. By default it uses labeled sample data. With `--aws`, it reads the project tables using the operator's AWS profile. [Preview source](../bin/preview_dashboard.py)

| Class or method | How it works |
| --- | --- |
| `Preview(BaseHTTPRequestHandler)` | Handles one browser request at a time within the threaded local HTTP server. The server supplies a snapshot reader, so the handler works with either sample or AWS data. |
| `Preview.do_GET()` | Maps the requested path to an HTML, CSS or JavaScript file. For `/api/dashboard`, calls the snapshot reader and serializes its result. Returns 404 for an unknown route and 503 if the live snapshot cannot be read. |
| `aws_snapshot_reader()` | Verifies the configured AWS identity and returns a callable. Each call looks up the stack's current tables and builds a fresh snapshot. |

## Candle ingestion

The model consumes **completed** candles. A bar still trading can change its close and would give inference a different input from training.

| Function | How it works |
| --- | --- |
| [`get_binance_data()`](../cryptobros/data_fetcher.py) | Requests a recent window from Binance.US, drops the unfinished bar and converts exchange fields to named prices, volumes and timestamps. |
| [`fetch_historical_data()`](../cryptobros/historical_backfill.py) | Computes a year-long time range, requests successive pages and advances past the final candle on each page. Returns ordered candle records. |
| `convert_to_csv()` | Converts normalized historical records into CSV text for archiving or reuse by the notebooks. |
| [`load_data_from_s3()` and `prepare_dataframe()`](../cryptobros/s3_to_dataframe.py) | The first reads the configured historical CSV into pandas. The second parses timestamps and sorts the records for time-based calculations. |

## Feature construction

The same market observation needs a feature vector for inference and a known outcome for training. [Feature functions](../cryptobros/feature_engineering.py)

| Function | How it works |
| --- | --- |
| `aggregate_candles()` | Resamples timestamped trades or bars into OHLCV bars using first open, maximum high, minimum low, last close and summed volume. |
| `create_features()` | Derives momentum, volatility, RSI, volume, price-range and time-of-day inputs. In training mode it labels each usable row by the return four bars ahead when the horizon is set to four. |
| [`training_features()`](../training/train.py) | Validates ordered 15-minute boundaries and splits candles at gaps. Restarts indicators in each segment so a feature or label never crosses missing market history. |
| `latest_feature_row()` | Builds features without future labels and returns the newest usable row. A window with too little indicator history cannot produce a forecast. |

## Training, evaluation and explainability

Earlier observations train the classifier. Later observations measure how it performs on candles it did not see during fitting. [Model functions](../cryptobros/modeling.py)

| Function | How it works |
| --- | --- |
| [`validate()`](../training/train.py) | Builds gap-aware features, requests a four-bar purge before the holdout, and returns a fitted model and evaluation metrics. |
| `train_direction_model()` | Splits the ordered features, fits a histogram gradient-boosting classifier, predicts on the held-out rows and returns accuracy, confusion matrix and class-level metrics. |
| `walk_forward_validate()` | Repeats fitting on progressively longer historical windows. Each fold tests on the following period, revealing variation across periods. |
| `explain_model()` | Shuffles each feature five times on the holdout and measures the mean change in accuracy. Returns scores, dates and sample size for the dashboard. |
| `save_model()` | Writes a joblib bundle with the fitted estimator and feature order, plus a JSON metrics file that can be reviewed separately. |
| `predict_latest()` | Passes the latest feature row to the fitted model. Returns a direction, class probabilities, anchor close and timestamp. |

## Production forecasting and scoring

An hourly forecast first becomes a stored prediction. Evaluation happens later, once the one-hour target candle has closed.

| Function | How it works |
| --- | --- |
| [Prediction `handler()`](../src/prediction/app.py) | Fetches candles, archives the raw window in S3 and invokes private inference. Writes the resulting forecast and serving-model identity to DynamoDB. |
| [Inference `handler()`](../sagemaker/lambda_handler.py) | Resolves the selected baseline or candidate, evaluates the supplied candles and returns both forecast and model identity. |
| [`pending_items()` and `fetch_candle_at()`](../src/evaluation/app.py) | Scan for completed forecasts awaiting scores and fetch each target candle's close. An unavailable or open target remains pending. |
| Evaluation `handler()` | Compares the realized direction with the stored prediction. Its conditional write records correctness once, including when two evaluations overlap. |

## Automatic retraining and release

Retraining uses a rolling window of 100 scored forecasts. Deployment also requires a passing historical holdout and successful inference checks. [Release functions](../src/retraining/app.py)

| Function | How it works |
| --- | --- |
| `rolling_window()` | Selects the latest 100 scored IDs and counts correct predictions. An incomplete window produces no eligibility decision to train. |
| `reserve()` | Atomically records the eligible window and the next allowed training time. Competing checks cannot claim the same window twice. |
| [`save_candidate()`](../training/train.py) | Checks the holdout size and accuracy before writing a candidate artifact. A score below 55% fails the gate. |
| `check_serving()` | Loads candles from the triggering forecast and replays them against inference. Checks the returned identity, class, probabilities and anchor price. |
| `release()` and `switch_model()` | The first coordinates preview, verification or recovery. The second changes the serving selection and history together so rollback can restore the previous model. |

## Public dashboard

The scheduled publisher reads private tables once per refresh. Visitors read the resulting snapshot through API Gateway.

| Function | How it works |
| --- | --- |
| [`read_snapshot()`](../src/dashboard/snapshot.py) | Traverses forecast records, counts all scored outcomes and retains the newest 100. Joins in recent training history, model selection and feature importance. |
| [Website `handler()`](../src/dashboard/app.py) | Serves the interface files or the cached JSON snapshot. It returns a valid empty snapshot while the first publication is pending. |

## Read a docstring in Python

From the repository root, open Python and enter `from training.train import training_features`, then `help(training_features)`. The function's docstring begins:

```python
def training_features(candles):
    """Build labeled rows independently inside consecutive 15-minute candle segments."""
```
