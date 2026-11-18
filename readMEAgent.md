# Background Agent Context

## Repository purpose

Build and document the remaining AWS serverless milestones for BTCUSDT direction prediction.

- Account: `879022683465`
- Region: `us-east-2`
- AWS profile: `dtsc3601-crypto`
- Shared bucket: `dtsc3601-cryptobros-project-879022683465-us-east-2-an`
- Branch: `full-serverless`
- Progress journal: `AGENT_PROGRESS.md`

Do not print, commit, or upload AWS credentials or secrets.

## Mandatory cost controls

Before making AWS changes:

1. Confirm whether `dtsc3601-btcusdt-serverless` is `InService`.
2. Never leave a SageMaker endpoint running for development or unattended agent work.
3. Do not create an endpoint unless an explicit endpoint smoke test is required.
4. Delete the endpoint immediately after any smoke test.
5. Do not leave SageMaker training jobs, endpoint configurations, or models running after testing.
6. Disable temporary development schedules where they are not required.
7. Prefer unit tests, Docker local tests, SAM validation, and change-set validation over AWS deployments.
8. Never deploy multiple SageMaker endpoints.

Endpoint status:

```powershell
aws sagemaker describe-endpoint `
  --endpoint-name dtsc3601-btcusdt-serverless `
  --profile dtsc3601-crypto `
  --region us-east-2 `
  --query '{Status:EndpointStatus,FailureReason:FailureReason}'
```

Endpoint deletion:

```powershell
aws sagemaker delete-endpoint `
  --endpoint-name dtsc3601-btcusdt-serverless `
  --profile dtsc3601-crypto `
  --region us-east-2
```

## Existing implementation

- `infra/template.yaml`
  - Prediction Lambda.
  - Evaluation Lambda.
  - DynamoDB prediction table.
  - EventBridge prediction/evaluation schedules.
- `src/prediction/app.py`
  - Fetches completed BTCUSDT 15-minute candles.
  - Stores raw candle JSON in S3.
  - Stores predictions in DynamoDB.
  - Optionally invokes SageMaker.
- `src/evaluation/app.py`
  - Evaluates predictions after 60 minutes.
  - Stores actual direction and correctness.
- `src/sagemaker/inference.py`
  - SageMaker inference implementation.
- `sagemaker/Dockerfile`
  - Custom SageMaker container.
- `feature_engineering.py`
  - Original feature engineering.
- `modeling.py`
  - Original training implementation.

## Completed

- S3 raw-candle storage.
- DynamoDB prediction storage.
- Hourly prediction schedule.
- Custom SageMaker container.
- SageMaker endpoint deployment.
- Hourly evaluation schedule.
- Prediction correctness records.

## Next milestone: retraining pipeline

Implement a minimum-cost retraining pipeline.

Recommended services:

1. DynamoDB for predictions and retraining state.
2. EventBridge for retraining decisions.
3. Lambda for threshold evaluation.
4. Step Functions for orchestration.
5. SageMaker Training Job for model training.
6. S3 for training data and model artifacts.
7. Systems Manager Parameter Store for the active model version.

## Retraining recommendation

Use these starting thresholds:

- Minimum: 100 evaluated predictions.
- Retrain if rolling accuracy falls below 55%.
- Seven-day retraining cooldown.
- Chronological validation.
- Existing 60-minute horizon and 15-minute candles.
- Existing 0.20% UP/DOWN threshold.

## Required pipeline

1. Evaluation Lambda records correctness.
2. Retraining decision Lambda calculates rolling accuracy.
3. Retraining state prevents duplicate executions.
4. Step Functions starts the retraining workflow.
5. Fresh candles are downloaded and stored in S3.
6. Training features are generated.
7. SageMaker runs a training job.
8. The new model passes a chronological quality gate.
9. The model artifact is stored with a version.
10. A SageMaker endpoint is created only for an approved deployment.
11. Model version and metrics are stored in DynamoDB.
12. The previous model remains available until promotion succeeds.

## Development AWS policy

- Prefer unit tests, Docker local tests, and SAM validation.
- Do not deploy AWS infrastructure until code and SAM validation pass.
- Do not start SageMaker training until the quality gate and cost guardrails pass.
- Do not update or delete the live endpoint without explicit approval.
- Do not modify the production endpoint until the new model passes validation.
- Stop and remove billable development resources before ending a session.

## Validation requirements

Before AWS deployment:

- Run focused unit tests.
- Run SAM validation.
- Inspect CloudFormation changes.
- Test retraining decisions locally.
- Test training locally using a small fixture.
- Confirm seven-day cooldown behavior.
- Confirm concurrency protection.
- Confirm all SageMaker resources can be deleted.

## Progress documentation

At the start of every agent session:

1. Read `AGENT_PROGRESS.md`.
2. Confirm the current SageMaker endpoint status.
3. Read the `Immediate next step` section.

At the end of every meaningful milestone:

1. Update `AGENT_PROGRESS.md`.
2. Record completed work.
3. Record failed attempts.
4. Record AWS resources created or deleted.
5. Record the exact next steps.
6. Record unresolved questions and cost concerns.
