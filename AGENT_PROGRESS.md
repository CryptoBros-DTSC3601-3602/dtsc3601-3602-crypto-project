# Agent progress journal

## November 19, 2026 Windows checkpoint

Reviewed the implementation at `a862718` on `full-serverless`. The verified
organization repository's branch pointed to the same commit at the start of
this session. This checkpoint updates the two agent documents.

- Windows Python 3.12 ran `python -m pytest -q tests` with the declared test
  dependencies in the ignored `.venv/crypto-test-deps` directory.
  All 12 focused tests passed.
- SAM CLI 1.172.1 passed `python -m samcli validate --lint --template-file infra/template.yaml --profile dtsc3601-crypto --region us-east-2`
  and `python -m samcli build --template-file infra/template.yaml`. Windows
  Application Control blocked `sam.exe`. The installed SAM Python module worked.
  `python -m json.tool infra/retraining.asl.json` also passed.
- The Windows dashboard HTTP check returned 200 for HTML, CSS, JS, and the
  JSON API, and verified the sample flag and 100 fixture outcomes.
- Windows Docker Desktop started its Linux engine after an initial missing
  named pipe. Both `linux/amd64` images built locally. The inference runtime
  emulator returned `FLAT` for the last 120 sample candles. The training image
  ran offline and scored 42.86% on 35 holdout rows. The 55% quality gate
  rejected the candidate and produced no model artifact. Both smoke-test
  containers were removed. The images remain available as `crypto-inference`
  and `crypto-training`.
- The cloud checkpoint also passed Chromium desktop, mobile, and API-error
  checks and exercised serving with a retrained fixture image.

## Read-only AWS inventory

- STS verified account `879022683465` and
  `arn:aws:iam::879022683465:user/AashutoshPanchal` in `us-east-2`.
- `dtsc3601-crypto-serverless` was `UPDATE_COMPLETE`. Its parameters are
  `ProjectName=dtsc3601-crypto`, the shared `DataBucketName` below, and an empty
  `SagemakerEndpointName`. It deploys prediction and evaluation Lambdas, their
  EventBridge rules, and the predictions table. Private inference, retraining,
  and the dashboard are pending deployment.
- SageMaker returned `ValidationException` with `Could not find endpoint
  "dtsc3601-btcusdt-serverless"`. The project endpoint list was empty and the
  regional training lists returned zero `InProgress` or `Stopping` jobs.
- The live `dtsc3601-crypto-hourly-prediction` and
  `dtsc3601-crypto-hourly-evaluation` rules were both `DISABLED`. The deployed
  CloudFormation template declares both `ENABLED`. Verify their live states
  after the approved deployment and explicitly enable them with approval if
  they are still disabled. No dashboard or retraining rule is deployed and no
  project EventBridge Scheduler schedules were found.
- The predictions table was active and on demand with 35-day point-in-time
  recovery. AWS reported 2,120 bytes and eight records. A scan found zero
  completed or scored forecasts.
- The existing private ECR repository `dtsc3601-btcusdt-inference` has eight
  digests, mutable tags, and no lifecycle policy. The private inference Lambda
  is absent, so there is no active serving digest. Build from
  `sagemaker/Dockerfile.lambda` for the first Lambda release.
- The shared bucket `dtsc3601-cryptobros-project-879022683465-us-east-2-an`
  is in Ohio and has no lifecycle configuration. The project log group
  `/aws/lambda/dtsc3601-crypto-prediction` has 3,506 bytes and no retention limit.

## Cost and scope

Existing cost drivers include S3 storage and requests, ECR image storage,
DynamoDB storage and point-in-time recovery, and CloudWatch log storage. AWS
lists [$0.10 per GB-month for private ECR storage](https://aws.amazon.com/ecr/pricing/).
The inventory did not establish account charges. This checkpoint made zero
AWS resource changes.

With the pipeline and dashboard enabled, a 30-day month has 720 predictions,
up to 720 private inference invocations, 720 evaluations, and 720 snapshots
before retries and manual invocations. Publisher and evaluation scans incur
DynamoDB reads that grow with the table. Public traffic adds API Gateway,
Lambda, snapshot reads, and logs. The training workflow adds Step Functions
transitions on execution and, for admitted jobs, training compute, volume,
logs, and artifact costs. Review storage and log retention before enabling
recurring activity. Keep the endpoint absent and the retraining rule disabled.

## Immediate next step

1. Use the locally smoke-tested `crypto-inference` image for staging. If it
   needs rebuilding, use these Windows commands and the sample candle request
   in the [README](README.md). Keep the optional `crypto-training` image for
   separate training review.

   ```powershell
   docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -f sagemaker/Dockerfile.lambda -t crypto-inference sagemaker
   docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -f training/Dockerfile -t crypto-training .
   ```

2. After staging approval, use the existing ECR repository and shared bucket.
   Push the tested image under a unique release tag and resolve it to a digest.
   If a serving image has since been deployed, reuse its verified digest.
   Omit the new `TrainingImage` parameter for this first dashboard and inference
   update. On later updates preserve a deployed training digest or set a
   reviewed digest from a separate private training repository.

   ```powershell
   $ApiArgs = @('--profile','dtsc3601-crypto','--region','us-east-2')
   $Identity = aws sts get-caller-identity @ApiArgs --output json | ConvertFrom-Json
   if ($Identity.Account -ne '879022683465' -or $Identity.Arn -notlike '*/AashutoshPanchal') { throw 'Wrong AWS identity' }
   $StackName = 'dtsc3601-crypto-serverless'
   $Bucket = 'dtsc3601-cryptobros-project-879022683465-us-east-2-an'
   $Registry = '879022683465.dkr.ecr.us-east-2.amazonaws.com'
   $Repository = 'dtsc3601-btcusdt-inference'
   $Tag = "lambda-$(git rev-parse --short HEAD)-$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss'))"
   $ImageTag = "${Registry}/${Repository}:${Tag}"
   aws ecr get-login-password @ApiArgs | docker login --username AWS --password-stdin $Registry
   if ($LASTEXITCODE -ne 0) { throw 'Unable to log in to ECR' }
   docker tag crypto-inference $ImageTag
   if ($LASTEXITCODE -ne 0) { throw 'Unable to tag the inference image' }
   docker push $ImageTag
   if ($LASTEXITCODE -ne 0) { throw 'Unable to push the inference image' }
   $Digest = aws ecr describe-images --repository-name $Repository --image-ids "imageTag=$Tag" @ApiArgs --query 'imageDetails[0].imageDigest' --output text
   if ($LASTEXITCODE -ne 0 -or $Digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Unable to resolve inference digest' }
   $InferenceImage = "${Registry}/${Repository}@${Digest}"

   python -m samcli build --template-file infra/template.yaml
   if ($LASTEXITCODE -ne 0) { throw 'SAM build failed' }
   python -m samcli deploy --template-file .aws-sam/build/template.yaml --stack-name $StackName --s3-bucket $Bucket --s3-prefix 'deployment/dtsc3601-crypto-serverless' @ApiArgs --capabilities CAPABILITY_IAM --no-execute-changeset --parameter-overrides DashboardEnabled=true "InferenceImage=$InferenceImage"
   ```

3. Inspect the returned change set with `aws cloudformation describe-change-set`
   using its ARN and the project profile and region. Review table changes, IAM,
   public routes, and rule states. Verify the project and bucket parameters
   and empty endpoint setting are preserved. Apply the reviewed ARN with
   `aws cloudformation execute-change-set` after explicit approval. Verify
   `UPDATE_COMPLETE`, check live rule states, and get approval for any direct
   rule enablement still needed.
4. Use `DashboardUrl` and `DashboardSnapshotFunctionName` from the stack outputs.
   Verify public HTML and JSON return 200. Follow a scheduled prediction through
   DynamoDB and S3. Confirm its serving digest, subsequent score, and the
   next published snapshot.
5. Separately stage a training digest while keeping the retraining rule disabled.
   Verify eligibility and obtain paid-training approval before triggering one
   bounded execution. Confirm the history, S3 metrics, quality gate, and
   artifacts. For a passing candidate, use the manual release procedure in the
   README and verify the new serving digest after approval. Record billable
   resources and their final status.
