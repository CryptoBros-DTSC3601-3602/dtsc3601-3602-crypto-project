# CryptoBros | Bitcoin direction forecasts

Can the last few hours of Bitcoin trading help predict its direction an hour from now? CryptoBros uses completed 15-minute BTC/USDT candles from Binance.US to train a gradient-boosted classifier. It predicts **UP** for a gain above 0.20%, **DOWN** for a loss greater than 0.20%, and **FLAT** for the interval in between, including both endpoints.

## Live AWS dashboard

**[Open the CryptoBros forecast dashboard](https://bvtbp86dfl.execute-api.us-east-2.amazonaws.com/)** to see the latest forecast, when the next one is due, how often past forecasts were correct and which inputs each model relied on. You can explore it without installing Python or signing in.

## Install locally

From the repository root on Windows, use Python 3.12 and PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Run the project

To follow one forecast from training through evaluation, run the bundled example:

```powershell
.\.venv\Scripts\python bin/sample_forecast.py
```

The command fits a classifier on earlier candles, scores it on later candles and prints a direction and probabilities for the last sample candle. To explore the interface with labeled sample data, start the preview and open [the local dashboard](http://127.0.0.1:8000):

```powershell
.\.venv\Scripts\python bin/preview_dashboard.py
```

## Architecture and repository structure

| Stage | Where to look | What happens |
| --- | --- | --- |
| Learn from candles | `cryptobros/`, `notebooks/`, `data/` | Python converts candles to momentum, volatility, volume and time features. Training and testing follow time order. |
| Forecast and score | `src/prediction/`, `sagemaker/`, `src/evaluation/` | EventBridge runs hourly jobs. Lambda archives candles in S3, invokes private Lambda inference, then scores mature forecasts in DynamoDB. |
| Retrain and release | `training/`, `src/retraining/`, `infra/` | Step Functions starts a bounded SageMaker job when fewer than 55 of the latest 100 scores are correct and the seven-day cooldown permits it. A candidate needs at least 55% holdout accuracy and serving checks to go live. A failed post-switch check triggers rollback. |
| Publish and explore | `src/dashboard/`, `bin/`, `tests/` | An hourly publisher builds a public snapshot. API Gateway serves the dashboard through Lambda. The CLI and tests exercise the pipeline locally. |

## Examples and walkthroughs

[Train, evaluate, save and reload a forecast model](docs/tutorial.md). The examples explain the printed metrics, show how to interpret a confusion matrix and give diagnostic steps for missing forecasts or scores.

## Class and function reference

[Explore the code by pipeline stage](docs/reference.md), from candle ingestion and feature construction to the dashboard, model selection and rollback.

## AWS deployment guide

[Build and deploy the AWS stack](docs/operations/project-guide.md). The guide covers container images, stack parameters, schedules and checking the published snapshot.

## Point of contact

The [repository's contributor history](https://github.com/CryptoBros-DTSC3601-3602/dtsc3601-3602-crypto-project/graphs/contributors) credits the people who contributed code. For project questions, contact:

Aashutosh Panchal

*GitHub:* Aashu-P

*Email:* aashupanchal2006@gmail.com


**License:** CryptoBros uses the GNU General Public License, version 3. [Full license](LICENSE)
