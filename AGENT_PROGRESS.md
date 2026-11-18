# Agent Progress Journal

## Goal

Complete the serverless BTCUSDT retraining pipeline and API/frontend access with no unnecessary persistent AWS cost.

## Last updated

2026-11-17

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
- Endpoint status: deleted; recreating it will start continuous billing.
- Stack: `dtsc3601-crypto-serverless`
- Branch: `full-serverless`
- Region: `us-east-2`

An `InService` endpoint is continuously billable. It remains deleted and must not be recreated unless live prediction usage or an approved smoke test is actively required.

## Cost protection status

- [x] Verified endpoint deletion
- [x] Endpoint deleted after testing
- [ ] No training jobs left running
- [ ] No temporary endpoint configurations left
- [ ] No temporary SageMaker endpoint left running
- [ ] Lambda log retention configured

## Next milestone

Retraining pipeline.

## Immediate next step

1. Keep the SageMaker endpoint deleted during development.
2. Confirm the deployed stack parameter is empty.
3. Confirm prediction records remain useful as `pending_sagemaker`.
4. Implement retraining threshold logic locally.
5. Add unit tests.
6. Add SAM infrastructure.
7. Run validation without deploying SageMaker resources.
8. Add deployment instructions only after local tests pass.

## Important decisions

- Prediction horizon: 60 minutes.
- Prediction cadence: hourly.
- Evaluation cadence: hourly.
- Minimum rolling evaluation window: 100 predictions.
- Retraining threshold: below 55% rolling accuracy.
- Retraining cooldown: seven days.
- Live endpoint: disabled/deleted during development.
- Training: SageMaker Training Job rather than a continuously running SageMaker Pipeline.

## Work in progress

- Retraining decision logic.
- Retraining state storage.
- SageMaker training entrypoint.

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
