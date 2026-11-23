# Agent progress journal

## November 21, 2026 automatic model release

Applied the owner-approved automatic release implementation in Ohio as
`samcli-deploy1795293440/b4214984-1442-42d1-89a2-2c8ca7112064`.
The tested private inference runtime is
`sha256:b3897ee350e0c9b25ec22adabbc79183c34ac6cd1de0df652d75e267a008b39e`.
CloudFormation reached `UPDATE_COMPLETE`. Verified the live workflow's
promotion, verification and recovery states and all four enabled schedules.

All 19 focused tests passed. SAM lint and build passed. AWS Step Functions
validated the substituted workflow definition with zero diagnostics.
An offline run of the production container exercised baseline inference,
preview and selection of the real local training artifact, digest rejection
and restoration. Transaction tests covered a packaged baseline and a previously
promoted model, including repeated calls during deployment and rollback.

Replayed archived candles from forecast `20261121T200000Z` through the live
private Lambda. It returned `FLAT`, the baseline model identifier, and the
expected runtime digest. The refreshed public dashboard showed 9 correct of
21 at 3:48 p.m. Eastern, and the eligibility execution
`auto-release-deployment-eb91777` succeeded with `train=false`.
On the first eligible passing training run, inspect `Promote` and
`VerifyServing`, the run's `deployed` history status, and the model digest on
the next hourly forecast and dashboard snapshot. Matching model digests confirm
the live switch. The workflow now handles the release step in the earlier
December 1 presentation checklist. Additional usage consists of private Lambda
invocations, DynamoDB reads and transactions, S3 artifact reads, and workflow
transitions.

## November 21, 2026 production trainer release

Applied the approved `trainer-gap-handling-556a4123` change set in Ohio.
CloudFormation reached `UPDATE_COMPLETE`. The stack parameter and active
Step Functions definition both reference the training image digest
`sha256:556a4123a57ef19838d7d06bf521f7a22a79177ac3866e4e834d4930a3c8d492`.
The job uses one `ml.m5.large` with a 1,800-second training limit.
The hourly prediction, evaluation and dashboard rules and the 03:45 UTC
daily eligibility rule were enabled.

The post-deployment execution `trainer-release-check-556a4123` succeeded
with `train=false`. The public snapshot at 2:25 p.m. Eastern showed 9
correct of 20 scored forecasts and zero training runs. All 13 focused tests
passed. The next live milestone is an eligible training run. Check the
November 24 evening window as described in the presentation checks below.

## November 21, 2026 training rehearsal

Binance.US returned 35,004 of 35,040 candles requested over the last year.
The previous trainer rejected the entire dataset. The updated trainer requires
99% coverage and splits at gaps before computing features or future targets.
The training image passed a local replay using those actual candles. Its
chronological holdout accuracy was **56.64% on 6,842 examples**, with 27,364
training rows. The local release rehearsal produced a candidate archive,
passed the README packaging step, and returned a `FLAT` forecast with valid
probabilities from the candidate Lambda image. The rehearsals ran locally and
did not write to AWS history. All 13 focused tests passed.

The private training image digest is
`sha256:556a4123a57ef19838d7d06bf521f7a22a79177ac3866e4e834d4930a3c8d492`.
Change set `trainer-gap-handling-556a4123` updates the workflow's training
image. The first scheduled eligibility check succeeded November 20 at 10:45 p.m.
Eastern. The November 21, 2:25 p.m. Eastern dashboard snapshot showed 9 of
20 live forecasts correct (45%). Live candidate validation and production
promotion still depend on an eligible run and a passing holdout.

## November 20, 2026 presentation checkpoint

Both the workflow deployment and the approved daily schedule update reached
`UPDATE_COMPLETE` in Ohio. EventBridge targets the deployed Standard workflow
at 03:45 UTC each day (10:45 p.m. Eastern in November). Hourly prediction,
evaluation and dashboard publishing continue. Inference uses the private Lambda.
The bounded SageMaker training job incurs compute charges only on admission.
Other usage includes ECR and S3 storage, DynamoDB data and backups, Lambda,
API Gateway, workflow transitions and logs. There is no scheduled shutdown.

The live Step Functions execution `presentation-window-check-20261120` reached
`CheckWindow`, `Eligible`, and `Done`. Its result was `train=false` with
three scored predictions. The live dashboard and its JSON showed 2 correct of
3 scored (66.7%) both for the rolling window and across all served versions.
Verified the published totals in Edge, and verified the EventBridge rule state
and state machine target. All 12 tests passed, as did SAM lint and build.
The dashboard regression fixture counts 100 correct of 102 overall while the
latest 100 are all correct.

**December 1 presentation checks (Eastern time)**

1. Open https://bvtbp86dfl.execute-api.us-east-2.amazonaws.com/ on November 24
   after 10:25 p.m. At one new score per hour the dashboard should show its
   first complete window. The 10:45 p.m. workflow uses the most recent live
   scores. At 55 or more correct, show the successful skipped execution in
   Step Functions and check subsequent days.
2. After an eligible execution finishes, inspect its SageMaker job and its
   run-specific S3 inputs and metrics, then check the history after the next
   hourly snapshot. For a validated candidate, use the manual release steps in
   the README, review and approve the digest change, and verify the serving
   digest on the next forecast. Keep the previous digest available.
3. On December 1, show the forecast, rolling and all-time scores with their
   denominators, and actual workflow history. The labeled local preview can
   illustrate candidate history if no production candidate qualifies.

## November 20, 2026 retraining deployment review

Published the locally tested linux/amd64 image to the private immutable-tag
ECR repository `dtsc3601-btcusdt-training` in Ohio. Its digest is
`sha256:3309086691b6ab89477b573a4a313a8ed19157d3dafcabf9cacafa677e77c382`.
The image adds about 167 MB of listed compressed storage. SAM lint and all
12 focused tests passed. Step Functions validated the substituted Standard
workflow definition with zero diagnostics. The regional ml.m5.large training
quota was 15 and there were zero training jobs in progress.

Staged change set `training-workflow-20261120214545` for execution approval.
It adds the state machine, decision Lambda, history table, roles and disabled
daily rule, and connects the dashboard publisher to history. No live training
execution has been validated.

### When and how to verify

With three forecasts scored at 9:15 p.m. Eastern on November 20, the first
full window is expected around **November 24 at 10:15 p.m. Eastern** assuming
uninterrupted hourly scoring. Check the public dashboard after its 10:25 p.m.
refresh. Eligibility requires at most 54 correct of the latest 100 and a
clear seven-day cooldown. At 55 or more correct, continue collecting outcomes.

After deployment, locate `RetrainingWorkflow` under the CloudFormation
stack's Resources tab in us-east-2. After explicit training approval, start
one Standard execution with input `{}`. An eligible run should reserve one
history record and start one bounded SageMaker job. Inspect the execution,
the job status, and the run-specific S3 candles and metrics. A passing
candidate also has an artifact URI and validated history. A below-threshold
candidate should leave a failed history record. Check the next hourly dashboard
snapshot for the run. Release a validated candidate manually using the README.
Obtain separate approval before enabling recurring paid runs.

## November 20, 2026 public dashboard

The approved dashboard change set reached `UPDATE_COMPLETE`. The public
read-only site is https://bvtbp86dfl.execute-api.us-east-2.amazonaws.com/.
Verified the HTML, CSS, JavaScript and JSON API returned HTTP 200, and Edge
rendered the live forecast and accuracy. After the initial snapshot, the
hourly publisher refreshed the public API at 9:25 p.m. Eastern with two
correct forecasts out of three scored.

API Gateway, the website and publisher Lambdas, the on-demand snapshot table,
and the hourly rule are deployed. Usage can incur API, Lambda, DynamoDB,
log and transfer charges. Training is disabled.

## November 20, 2026 live backend

Executed the approved backend change set. The stack reached `UPDATE_COMPLETE`
and both hourly prediction and evaluation rules are enabled. Private Lambda
inference is active on the staged digest. Public hosting and retraining are
disabled. Recurring usage includes Lambda, S3, DynamoDB and logs.

The first live invocation stored 120 candles in S3 and wrote completed forecast
`20261120T234734Z` to DynamoDB. The local dashboard and Edge displayed
`FLAT` with the matching model digest. Open `http://127.0.0.1:8000` on the
project PC. To restart the live view, run `python bin/preview_dashboard.py --aws`.

Scheduled forecasts arrived at 7 and 8 p.m. Eastern. At 8:15 p.m. the
evaluation Lambda scored the first manual forecast correct and the 7 p.m.
scheduled forecast incorrect. The dashboard returned outcomes `[1, 0]`,
matching the DynamoDB records (one correct of two).

## November 20, 2026 backend staging

The tested private inference image was pushed to the existing ECR repository
with digest `sha256:92ec74ad673120b4a6922a4235e6970f05a897f4e6f9f57a0d3727c4dc0470fd`.
SAM uploaded artifacts under the shared bucket's deployment prefix. These
artifacts and the ECR image can incur storage charges. The backend-only
change set `samcli-deploy1795218144` was staged for review with
`DashboardEnabled=false` and empty training and SageMaker endpoint parameters.
When staging with this SAM CLI, pass `--image-repositories "InferenceFunction=$repo"`
where `$repo` is the full existing ECR repository URI.

The local dashboard now supports `python bin/preview_dashboard.py --aws`.
Verified the live DynamoDB read, local HTTP routes, and rendered empty state
in Edge. All 12 focused tests, SAM lint, and SAM build passed.

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
   in the [deployment guide](project-guide.md). Keep the optional `crypto-training` image for
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
