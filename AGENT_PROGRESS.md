# Agent Progress Journal

## Goal

Complete the serverless BTCUSDT retraining pipeline and API/frontend access with no unnecessary persistent AWS cost.

## Last updated

2026-11-19

## Completed

- Added hourly prediction Lambda.
- Added S3 raw-candle storage.
- Added DynamoDB prediction storage.
- Added SageMaker custom inference container.
- Corrected Linux `serve` line endings.
- Deployed SageMaker endpoint.
- Added hourly evaluation Lambda.
- Added actual direction and correctness fields.
- Added cost guardrails and a resume journal.
- Deleted SageMaker endpoint `dtsc3601-btcusdt-serverless` to stop continuous compute billing.
- Cleared `SagemakerEndpointName` in the deployed prediction stack.

## Current AWS state

- SageMaker endpoint: `dtsc3601-btcusdt-serverless`
- Endpoint status at last owner check: absent. Current status needs authenticated verification.
- Stack: `dtsc3601-crypto-serverless`
- Branch: `full-serverless`
- Region: `us-east-2`

An `InService` endpoint is continuously billable. Keep it absent during this milestone.

## Cost protection status

- [x] Verified endpoint deletion
- [x] Endpoint deleted after testing
- [ ] No training jobs left running
- [ ] No temporary endpoint configurations left
- [ ] No temporary SageMaker endpoint left running
- [ ] Lambda log retention configured

## Local retraining milestone

The optional SAM workflow scans all prediction pages for the newest 100 evaluated
predictions. A DynamoDB transaction reserves the window, records the execution,
and starts a seven-day cooldown at admission, including failed attempts.
A deterministic job name prevents a second paid job for the same execution.
The training image downloads fresh completed Binance.US candles, writes the
snapshot and metrics under a run-specific S3 prefix, and builds a candidate.
The last 20% is held out chronologically with a four-bar purge before the split.
Candidate accuracy must be at least 55%. A validated history record includes
the metrics and artifact URI. Active-model selection is untouched.

The state machine is omitted until TrainingImage contains an ECR digest.
Its daily schedule is disabled even when an image is supplied. Each admitted
job requests one ml.m5.large with a 30-minute runtime limit. There is no new
public API or inference endpoint.

## Immediate next step

1. Repeat the local checks below after changes.
2. Before AWS validation, bind a project identity, recheck endpoint and training
   job inventory, and review existing schedules and their charges. The owner's
   last CLI check found the endpoint absent and the stack endpoint parameter empty.
   The cloud session could not independently refresh this check (profile missing).
3. When authorized, build the image from the repository root using
   docker build -f training/Dockerfile, push it to private ECR, review a SAM
   change set with its digest, and validate one bounded workflow execution.
   Verify Binance reachability, IAM, failed-job history and candidate artifacts.
4. Decide how operators will approve a model version for serving. Item 12 of the
   project brief requires keeping the previous model available until promotion
   succeeds. Automatic promotion and rollback are pending a scope decision.
   For private inference, publish the locally tested inference image and supply its
   digest as InferenceImage. Verify completed predictions and later evaluations in
   DynamoDB. Frontend/API access remains a future milestone.
5. Review retention policies before enabling schedules. Existing hourly prediction
   and evaluation rules are enabled in the template. No AWS resources were
   created, started, modified or deleted in this local milestone.

## Private inference checkpoint

The existing prediction Lambda can call a private, on-demand inference Lambda
packaged with the checked-in model. No public route or SageMaker endpoint is
required. Nine local tests passed, SAM lint passed, and the Lambda runtime
emulator predicted FLAT on the last 120 sample candles. The prediction record
uses the scored bar timestamp and close. No AWS resources were provisioned.
If deployed, inference adds Lambda requests, duration, logs, and ECR storage.

## Validation on full-serverless

- Seven tests passed. Moto exercised DynamoDB reservations, cutoff boundaries,
  stale windows, failed and replayed executions, and S3-backed candidate history.
  The first dependency fetch returned HTTP 503. After installation the history
  test caught a reserved DynamoDB attribute name; the updated expression passed.
- Installed development dependencies from tests/requirements.txt can be tested with
  `env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE AWS_DEFAULT_REGION=us-east-2 AWS_EC2_METADATA_DISABLED=true OMP_NUM_THREADS=2 .venv/bin/python -m pytest -q tests`.
- `sam validate --lint -t infra/template.yaml --region us-east-2` passed.
  The external ASL also parsed locally. AWS service integration remains untested.
- Built the Python 3.10 training image locally using the cloud CA bundle for pip.
  Ran its validator with Docker networking disabled on the checked-in sample:
  136 training rows, four purged rows, 35 holdout rows, 42.86% accuracy.
  This falls below the candidate gate. No sample model was promoted.
- No AWS-side cleanup was necessary for this work. No live resource inventory
  was available. Local Docker smoke tests used automatic container removal.

## Cost inventory

- S3 candle, model and report storage, requests and applicable data transfer.
- DynamoDB prediction and retraining table storage, reads and writes, and
  point-in-time recovery on the prediction table.
- Private ECR image storage and applicable scanning/transfer fees.
- CloudWatch log ingestion and retention for Lambda and training jobs.
- Recurring scheduled executions drive Lambda duration/requests, Step Functions
  Standard transitions and dependent service requests. The new schedule is disabled.
- Each admitted SageMaker training job incurs instance and attached volume
  charges for its runtime. Its completed job record persists as metadata.
- The template provisions no inference endpoint. Existing AWS resources and
  current account charges cannot be inventoried from this session.

## Important decisions

- Prediction horizon: 60 minutes.
- Prediction cadence: hourly.
- Evaluation cadence: hourly.
- Minimum rolling evaluation window: 100 predictions.
- Retraining threshold: below 55% rolling accuracy.
- Retraining cooldown: seven days.
- Live endpoint: disabled/deleted during development.
- Training: SageMaker Training Job rather than a continuously running SageMaker Pipeline.

## Known risks

- SageMaker endpoints incur continuous compute cost while `InService`.
- The endpoint/container must be deleted outside explicit smoke tests.
- Lambda/Binance calls may encounter rate or availability failures.
- Retraining must never overwrite the active model before validation succeeds.
- Evaluation records must remain idempotent.

## AWS cleanup checklist

Before ending any session:

- Delete test endpoints.
- Delete test endpoint configurations.
- Delete temporary SageMaker models.
- Verify no training jobs remain `InProgress`.
- Disable temporary schedules.
- Remove test data from S3 only when explicitly approved.
- Record the cleanup result in this file.

## Next session instructions

Start by reading this file and `readMEAgent.md`, verify endpoint status, and continue only the highest-priority unfinished task marked here.
