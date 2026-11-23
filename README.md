# BTCUSDT Direction Prediction

This project collects BTCUSDT market data from Binance.US, stores historical
data in Amazon S3, creates prediction features, and trains a model to predict
whether BTCUSDT will move **up**, **down**, or remain **flat**.

## What the model predicts

The model uses completed 15-minute candles and predicts the direction of the
price 60 minutes later:

| Class | Meaning |
| --- | --- |
| `UP` | Price increases by more than 0.20% |
| `DOWN` | Price decreases by more than 0.20% |
| `FLAT` | Price changes by no more than 0.20% |

The 0.20% value is a return threshold based on the current price. For example,
0.20% of a BTC price of $84,000 is about $168.

## Repository guide

| Path | Description |
| --- | --- |
| [`historical_backfill.py`](./historical_backfill.py) | Downloads one year of completed 15-minute candles and uploads a CSV to S3 |
| [`s3_to_dataframe.py`](./s3_to_dataframe.py) | Loads the historical S3 CSV into pandas and prepares timestamps |
| [`data_fetcher.py`](./data_fetcher.py) | Gets a rolling window of recent completed Binance.US candles |
| [`feature_engineering.py`](./feature_engineering.py) | Creates the same features for training and prediction |
| [`modeling.py`](./modeling.py) | Trains, validates, saves, and uses the classifier |
| [`01_feature_engineering.ipynb`](./01_feature_engineering.ipynb) | Shows S3 loading and feature creation |
| [`02_modeling.ipynb`](./02_modeling.ipynb) | Shows validation, training, and live-style prediction |
| [`bin/live_prediction.py`](./bin/live_prediction.py) | Command-line example for a live-style prediction |
| [`data/sample_btcusdt_15m.csv`](./data/sample_btcusdt_15m.csv) | Small sample file for the quick-start example |
| [`requirements.txt`](./requirements.txt) | Python packages required by the project |

## Install

### Requirements

- Python 3
- An AWS profile named `dtsc3601-crypto` with access to the project S3 bucket
- Internet access for Binance.US and AWS

### Install the required libraries

From the repository folder, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The main libraries used are:

- `pandas` for tabular market data
- `numpy` for numerical calculations
- `boto3` for Amazon S3
- `requests` for Binance.US API requests
- `scikit-learn` for the classifier and evaluation
- `joblib` for saving the trained model
- `jupyter` for running the notebooks

## Quick start: train on the small sample

The repository includes a small CSV so the project can be tested without
downloading one year of data. Run this from the repository folder:

```powershell
python -c "import pandas as pd; from feature_engineering import create_features; from modeling import train_direction_model; candles = pd.read_csv('data/sample_btcusdt_15m.csv'); features = create_features(candles, timeframe='15min', horizon_bars=4, flat_threshold=0.002); model, metrics = train_direction_model(features); print(f'Rows: {len(features)}'); print(f'Accuracy: {metrics[\"accuracy\"]:.3f}')"
```

This example:

1. Reads the checked-in sample CSV.
2. Creates the same 15-minute features used by the full project.
3. Creates a 60-minute, three-class target.
4. Trains the classifier on a chronological split.
5. Prints the test accuracy.

The sample is for confirming that the code runs. It is too small to represent
the full model's expected performance.

## Store the full historical dataset in S3

The historical backfill downloads one year of completed BTCUSDT 15-minute
candles in batches and stores them at:

```text
s3://dtsc3601-cryptobros-project-879022683465-us-east-2-an/
historical/binance/BTCUSDT/15m/btcusdt_15m_1y.csv
```

Run:

```powershell
python historical_backfill.py
```

The S3 profile and bucket are configured in
[`historical_backfill.py`](./historical_backfill.py) and
[`s3_to_dataframe.py`](./s3_to_dataframe.py). Do not commit AWS credentials,
access keys, or secret files.

## Run the notebooks

### Feature engineering

Open [`01_feature_engineering.ipynb`](./01_feature_engineering.ipynb) and run
all cells. It downloads the S3 CSV, loads it into pandas, saves a local copy,
and displays the raw candles and engineered features.

### Modeling

Open [`02_modeling.ipynb`](./02_modeling.ipynb), restart the kernel, and run all
cells. It:

1. Loads the historical data from S3.
2. Creates the target and feature columns.
3. Uses chronological training and testing.
4. Runs walk-forward validation.
5. Displays accuracy and the classification report.
6. Saves the trained model under `models/`.
7. Fetches recent Binance.US data and prints a live-style prediction.

## Main functions

### Data ingestion

- `historical_backfill.get_time_range()` calculates the one-year time range
  ending at the latest completed 15-minute candle.
- `historical_backfill.fetch_historical_data()` requests the data in batches,
  removes candles outside the requested period, and returns normalized records.
- `historical_backfill.convert_to_csv()` converts those records into CSV text.
- `historical_backfill.upload_to_s3()` writes the CSV to the configured S3 key.
- `data_fetcher.get_binance_data()` retrieves a recent rolling window for
  prediction and excludes an incomplete candle.
- `data_fetcher.upload_to_s3()` stores a live API response as timestamped JSON.

### Data preparation and features

- `s3_to_dataframe.load_data_from_s3()` downloads the historical CSV into a
  pandas DataFrame.
- `s3_to_dataframe.prepare_dataframe()` parses UTC timestamps, sorts the
  records, and returns a clean copy.
- `feature_engineering.aggregate_candles()` creates the model's 15-minute bars
  from candle data.
- `feature_engineering.create_features()` calculates momentum, trend, RSI,
  volatility, volume, candle-shape, and time-of-day features. It also creates
  the optional `DOWN`, `FLAT`, and `UP` target.
- `feature_engineering.latest_feature_row()` calculates features from the
  rolling live window and returns only the newest row for prediction.
- `feature_engineering.feature_names()` returns the feature names in the
  order expected by the model.

### Training and prediction

- `modeling.train_direction_model()` trains with an earlier-period training
  set and a later-period test set.
- `modeling.walk_forward_validate()` repeats training and testing across
  expanding time windows without using future rows.
- `modeling.save_model()` saves the classifier, feature-column order, and
  evaluation metrics.
- `modeling.predict_latest()` returns the predicted class, probabilities,
  timestamp, and current close price.

All functions include docstrings in their Python files with more detail about
their arguments, return values, and errors.

## Run the live prediction example

Run the model notebook first so the trained model exists under `models/`.
Then run:

```powershell
python bin/live_prediction.py
```

The script calls Binance.US, fetches recent completed candles, calculates the
latest feature row, and prints:

```text
Completed bar: ...
Current close: $...
Predicted direction in 60 minutes: UP/DOWN/FLAT
Class probabilities:
  DOWN: ...
  FLAT: ...
  UP: ...
```

The API returns a rolling window rather than one candle because moving
averages, RSI, volatility, and volume features need historical values.

## Serverless development on `full-serverless`

The dashboard displays times in fixed Eastern Standard Time (UTC−5). The next
scheduled prediction is the next whole hour. The feature importance chart ranks
the mean change in classification accuracy across five shuffles per input.
The baseline chart uses 288 labeled examples after the baseline was committed,
beginning November 17 at 9 p.m. EST and ending November 20 at 8:45 p.m. EST.
The training workflow computes each new model's scores on its own chronological
holdout. Model selection shows the evaluation period and sample size because
these can differ between runs. Correlated features can share predictive signal.

The hourly prediction Lambda fetches closed candles from Binance.US and stores the
raw input in S3. Set the SAM parameter `InferenceImage` to the immutable digest
URI of the private inference image to run the packaged baseline model in Lambda.
Prediction invokes it synchronously and saves the resulting class, probabilities,
model bar time, and closing price in DynamoDB. Evaluation uses that price and
timestamp to score the forecast one hour later. The inference function has no
HTTP URL and needs no provisioned concurrency. With an empty inference image
parameter, the existing SageMaker configuration or pending-record behavior applies.

Build from the repository root on Linux using Docker:

```sh
docker build --platform linux/amd64 -f sagemaker/Dockerfile.lambda -t crypto-inference sagemaker
docker build --platform linux/amd64 -f training/Dockerfile -t crypto-training .
```

To exercise the inference image offline, start it with
`docker run --rm -p 127.0.0.1:9000:8080 crypto-inference` and POST a JSON object
containing a `candles` array of numeric OHLCV records to
`/2015-03-31/functions/function/invocations`. Use the columns from
`data/sample_btcusdt_15m.csv`, including UTC timestamps and taker buy volume.
The response contains the predicted class, probabilities, close and model bar time.

For eventual AWS validation, store each linux/amd64 image in private ECR in
`us-east-2` and supply the two digest URIs as `InferenceImage` and `TrainingImage`
in the SAM change set. Review existing hourly schedules and permissions before
applying it. The `RetrainingScheduleState` parameter defaults to `DISABLED`.
The presentation stack uses `ENABLED` and checks daily at 03:45 UTC
(10:45 p.m. Eastern on the preceding calendar day in November and December).
When enabled,
the workflow checks the last 100 evaluated predictions, reserves an eligible
window in DynamoDB when fewer than 55 were correct and seven days have elapsed
since any previous reservation, and submits one time-limited training job. A passing job
produces a versioned S3 candidate.

Binance.US can omit 15-minute intervals. The trainer requests the past year,
requires at least 99% of the expected candles, and calculates indicators and
60-minute targets separately within each consecutive segment. The S3 metrics
record observed and missing candle counts alongside chronological holdout accuracy.

### Automatic candidate release

With private Lambda inference configured, Step Functions takes a validated
candidate through release automatically. It replays the candles from the last
forecast in the eligibility window through the private inference Lambda. The
Lambda checks the training archive's metrics and returns the SHA-256 digest
of the candidate model along with its prediction. Only trusted project
training artifacts belong under the training output prefix.

After a successful preview, a DynamoDB transaction records the previous model,
selects the candidate and sets the run to `verifying`. The workflow then invokes
the ordinary inference path with the same candles and checks the returned model
identity, class, price and probabilities. Success marks the run `deployed`.
A failed preview records `release_failed`. A failed production check restores
the previous selection and records `rolled_back`. The dashboard publishes the
training history on its next hourly refresh.

Each forecast stores the runtime image as `inference_image`, plus the actual
`model_digest` and `model_run` returned by inference. The packaged baseline
uses the runtime image digest. Older forecasts retain their recorded image
identity. Keep the per-run S3 artifacts for deployed models and rollback.
`bin/prepare_candidate_image.py` is also available for offline rehearsals.

### Preview and deploy the public dashboard

Run `python bin/preview_dashboard.py` from the repository root and open
`http://localhost:8000` on the same machine. This preview uses labeled sample
data and requires only Python 3.

For a local dashboard connected to AWS, run `python bin/preview_dashboard.py --aws`
with boto3 installed and the project CLI profile available. Open
`http://127.0.0.1:8000`. The local server checks the AWS identity and reads the
project tables to assemble the same sanitized snapshot as the hourly publisher.
Credentials stay on the server. Empty forecast and accuracy fields reflect the
current table contents. This mode works with `DashboardEnabled=false`.

For live data, use AWS CLI credentials for the existing project account,
Docker for image builds, and AWS SAM CLI. Push the inference image and, for live
training history, the training image to private ECR in `us-east-2` using the
Dockerfiles above. Use ECR image digests in the form
`ACCOUNT.dkr.ecr.us-east-2.amazonaws.com/REPOSITORY@sha256:DIGEST`.
The forecast needs an inference image to generate new completed predictions.
You can enable the dashboard before training is configured.

For example, publish the baseline inference image with PowerShell from the
repository root. Reuse the private repository if it already exists. Create it
with `aws ecr create-repository --repository-name crypto-inference --profile dtsc3601-crypto --region us-east-2`
if ECR reports that it is missing.

```powershell
$Registry = '879022683465.dkr.ecr.us-east-2.amazonaws.com'
$Tag = git rev-parse --short HEAD
aws ecr get-login-password --profile dtsc3601-crypto --region us-east-2 | docker login --username AWS --password-stdin $Registry
docker build --platform linux/amd64 -f sagemaker/Dockerfile.lambda -t "${Registry}/crypto-inference:${Tag}" sagemaker
docker push "${Registry}/crypto-inference:${Tag}"
$Digest = aws ecr describe-images --repository-name crypto-inference --image-ids "imageTag=$Tag" --profile dtsc3601-crypto --region us-east-2 --query 'imageDetails[0].imageDigest' --output text
$InferenceImage = "${Registry}/crypto-inference@${Digest}"
```

If a model is already serving, use its current digest when adding the dashboard
to the stack. To publish a training image, use the same ECR steps with a
separate repository and build with `-f training/Dockerfile` and context `.`.

The following example uses PowerShell from the repository root. Set the image
variables to your private ECR digest URIs. Leave the training image empty for
a first deployment, or keep the currently deployed training digest if one is
already in use. Use the existing `DataBucketName` and `ProjectName` values if
the stack uses custom values.

```powershell
$InferenceImage = '<inference image URI with digest>'
$TrainingImage = '' # Use the existing training digest if configured
sam build --template-file infra/template.yaml
sam deploy --guided --stack-name dtsc3601-crypto-serverless --profile dtsc3601-crypto --region us-east-2 --capabilities CAPABILITY_IAM --confirm-changeset --parameter-overrides DashboardEnabled=true "InferenceImage=$InferenceImage" "TrainingImage=$TrainingImage" "SagemakerEndpointName="
```

Review the change set before accepting it. The stack output `DashboardUrl` is
the public website address. API Gateway serves the HTML, styles, and data from
the same origin, so the browser needs no separate API URL or credentials.

The dashboard publishes its first snapshot at 25 minutes past the hour. To
publish it immediately, invoke the snapshot function named in the stack output.

The recent accuracy card uses the latest 100 scored forecasts, or all available
while the first window fills. All-time live accuracy counts every scored
production forecast across served model versions. Both exclude forecasts that
are waiting for their outcome. Training history reports a separate accuracy
calculated on held-out historical candles.

```powershell
$Stack = aws cloudformation describe-stacks --stack-name dtsc3601-crypto-serverless --profile dtsc3601-crypto --region us-east-2 --output json | ConvertFrom-Json
$Snapshot = ($Stack.Stacks[0].Outputs | Where-Object OutputKey -eq 'DashboardSnapshotFunctionName').OutputValue
aws lambda invoke --function-name $Snapshot --profile dtsc3601-crypto --region us-east-2 dashboard-snapshot-result.json
($Stack.Stacks[0].Outputs | Where-Object OutputKey -eq 'DashboardUrl').OutputValue
```

An empty forecast or accuracy window stays empty until the prediction and
evaluation Lambdas record the results. The new public Lambda reads one
sanitized snapshot per request. The scheduled publisher reads prediction and
training history once an hour. API Gateway throttles public requests. Deployment
can incur API Gateway, Lambda, DynamoDB, and log charges. To take the dashboard
offline, redeploy with `DashboardEnabled=false`.

## Questions

Contact **Aashutosh Panchal**:

- GitHub: [Aashu-P](https://github.com/Aashu-P)
- Email: [aashupanchal2006@gmail.com](mailto:aashupanchal2006@gmail.com)

## License

This project is available under the [GNU General Public License v3.0](./LICENSE).
