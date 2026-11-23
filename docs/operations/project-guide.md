# AWS deployment guide

Run all commands from the repository root.

## Production architecture

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

This project is available under the [GNU General Public License v3.0](../../LICENSE).
