# CryptoBros serverless handoff

Work on `full-serverless` in
[`CryptoBros-DTSC3601-3602/dtsc3601-3602-crypto-project`](https://github.com/CryptoBros-DTSC3601-3602/dtsc3601-3602-crypto-project).
Verify the remote before pulling or pushing. The Windows checkout uses
`chohan787/dtsc3601-crypto-project` as `origin`. Use the verified organization URL
explicitly for the handoff. See [AGENT_PROGRESS.md](AGENT_PROGRESS.md) for the live
inventory, validation results, and deployment commands.

## Architecture

- At minute 00 UTC, the prediction Lambda fetches completed 15-minute BTCUSDT
  candles from Binance.US and writes the raw input to S3. It invokes the
  private, on-demand inference Lambda configured by `InferenceImage` and writes
  the forecast, probabilities, anchor price and timestamp, and serving image
  digest to DynamoDB. The horizon is 60 minutes. Returns above +0.20% are
  `UP`, below -0.20% are `DOWN`, and the rest are `FLAT`.
- At minute 15 UTC, evaluation scores forecasts after the target candle closes.
  A conditional write makes evaluation safe to retry.
- With `DashboardEnabled=true`, API Gateway serves the read-only site and
  `/api/dashboard` from one origin. At minute 25 UTC, a publisher writes a
  sanitized DynamoDB snapshot with the latest completed forecast, up to 100
  scored outcomes, total scored and correct across all model versions, and up
  to 10 training runs when training is configured.
  The public Lambda reads the snapshot. The site exposes no inference or
  training triggers. Preview labeled sample data with
  `python bin/preview_dashboard.py` at `http://localhost:8000`.
- `TrainingImage` enables the optional Step Functions workflow and history
  table. Its daily rule is disabled by default. Retraining requires 100 scored
  forecasts and accuracy below 55%. A DynamoDB transaction reserves the window
  and enforces a seven-day cooldown even after failure. An admitted run uses one
  SageMaker `ml.m5.large`, 5 GB, and a 30-minute training runtime cap. The job
  fetches a year of completed candles and requires at least 99% interval coverage.
  It resets indicators at each gap and excludes labels that would cross a gap.
  It holds out the last 20% of usable examples
  chronologically with a four-bar purge, and requires at least 55% holdout
  accuracy to emit a candidate. History, training inputs, metrics, and passing
  model artifacts are keyed by run.
- Serving releases are manual. Select a trusted `validated` run, use
  `bin/prepare_candidate_image.py`, and build and smoke-test a candidate
  `linux/amd64` Lambda image. Deploy its immutable ECR digest as
  `InferenceImage` after change-set approval. Keep the prior digest available
  to restore. Automated promotion and rollback require a separate scope decision.

## AWS access and approvals

Use the local CLI profile `dtsc3601-crypto` in `us-east-2`. Run STS first and
proceed only for account `879022683465` and the ARN ending in
`user/AashutoshPanchal`. Keep AWS credentials out of output, documentation,
and Git. The stack is `dtsc3601-crypto-serverless` and the shared bucket is
`dtsc3601-cryptobros-project-879022683465-us-east-2-an`.

Start with read-only checks of the stack parameters, endpoint, jobs, and live
schedules. Keep `SagemakerEndpointName` empty and use private Lambda inference.
Endpoint creation, modification, and deletion are outside the scope. Review
changes before creating resources. Obtain approval before executing a change set
or changing live schedules, and separate approval before starting paid training.
The owner approved recurring eligible jobs on November 20, 2026. The live stack
sets `RetrainingScheduleState=ENABLED` and checks daily at 03:45 UTC. Preserve
this parameter on subsequent releases. The seven-day cooldown starts when a job
is admitted. See the latest progress journal entry for the December 1 verification
plan and current status.
