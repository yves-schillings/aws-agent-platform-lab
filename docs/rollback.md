# Roll back an application image

Rollback updates one existing ECS Express service to a previously verified ECR **digest**. It does not revert Terraform, Cognito configuration, IAM policies, KB content, S3 state or data formats. Check that the selected image can safely read the current state schema and configuration before proceeding. There is no automatic rollback based on application alarms.

## Prerequisites and evidence

Choose the known-good `repository@sha256:...` from a reviewed deployment receipt/ECR record, not a moving tag. Confirm it belongs to the same account, region and repository, still exists, and has acceptable scan results. Read the service's currently active image digest and use that as `expected_current_digest`; this prevents a rollback from overwriting a newer concurrent deployment. Retain the incident details and the receipt from the failed update.

The deploy and rollback workflows share a concurrency group, run only on the default branch and use environment `aws-lab`. Required reviewers and branch restrictions must be configured in GitHub; declaring an environment in YAML alone does not enforce those protections. AWS credentials come from the exact configured OIDC subject. No long-lived AWS keys are required.

## Workflow procedure

1. Manually start **Roll back to a known-good image** on the default branch.
2. Enter the target `sha256:<64 lowercase hex>` and the currently active digest. Review the environment approval if configured.
3. The script verifies the AWS account, exact service/repository/digest, one stable active configuration, port 8000 and `LOCAL_DEMO_MODE=false`. It refuses an unexpected current image or a service already transitioning.
4. It preserves current environment variables, secret references, command fields and logging settings, changes only the image, and waits for the chosen revision to become the sole active configuration. A timeout or SDK error produces `failed_or_unverified`, never an inferred success.
5. Check the configured health endpoint, then sign in and run the authenticated tenant/RAG/approval smoke described in [deployment.md](deployment.md). Inspect service events, CloudWatch errors and task health. Mark the incident resolved only after this behavior is verified.

The retained workflow artifact is a redacted receipt containing account/region, service ARN, image digests, revision identifiers, times and status. It excludes container environment and secret values. Keep operational evidence privately as needed; GitHub receipt retention is seven days. The ECR repository does not automatically expire old images, so the operator must manage retention without removing the required rollback digests.

## Local operator alternative

The script defaults to offline argument validation and creates no AWS client without `--execute`:

```text
python scripts/rollback_express.py --expected-account-id <actual-account> --region <verified-region> --service-arn <exact-existing-service-arn> --image-uri <repository@known-good-digest> --expected-current-image <repository@current-digest> --output artifacts/rollback-<unique-name>.json
```

Only after authorization and review, append `--execute` using the appropriate temporary operator credentials. Use a fresh output filename: the script refuses to overwrite an existing receipt. The account check is performed before any update, and the digest must exist in ECR. Do not provide passwords, tokens or secret values as arguments.

If the service is already transitioning or unhealthy, inspect ECS Express service events first. The helper is intentionally limited to a stable service and will not cancel an active AWS deployment, change IAM, rebuild a deleted image or repair schema incompatibilities. If the chosen image is incompatible with current data, plan a separately reviewed recovery or forward fix. Do not reset state, delete artifacts or repeatedly promote arbitrary versions to bypass the checks.

Offline tests cover account mismatch, mutable/foreign images, concurrent configuration, wrong runtime mode, expected-current mismatch, preserved configuration, redacted receipts, existing receipt protection and failed deployment status. No live AWS rollback has been executed or verified during development.
