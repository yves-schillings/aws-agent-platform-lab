# AWS deployment runbook

This repository contains a deployable candidate for a synthetic demonstration. No AWS resources, users, model subscriptions or public endpoints were created during development. Terraform schema validation and offline tests do not establish that an AWS deployment works. Account authorization, regional availability, costs, model access and authenticated end-to-end behavior still require an operator's verification.

## Topology and boundaries

The browser signs in through a Cognito public client using authorization code with PKCE. FastAPI validates access tokens and resolves Cognito groups to server-side tenant/access scopes. ECS Express Mode maintains two identical Python application tasks on Fargate behind its managed HTTPS Application Load Balancer. Each task runs the same immutable container image in its own isolated runtime. The application calls Bedrock Converse, retrieves from one Bedrock Knowledge Base backed by S3 Vectors, invokes an in-process-owned MCP subprocess over stdio, and stores run state and artifact decisions in a private S3 bucket using conditional writes.

Terraform provisions two public subnets and an Internet Gateway, without a NAT Gateway. Express manages the load balancer, certificates, security groups and task public IP assignment. The runtime is one 0.5-vCPU/1-GiB task; a deployment may temporarily run more tasks. This is a deliberately small demonstration topology, with public network egress and no high-availability or private-network claim. Inspect the actual managed security groups after deployment and verify that application traffic reaches tasks only through the load balancer. [AWS Express resources and networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html)

The two S3 buckets block public access, enforce TLS, use KMS encryption and enable versioning. S3 Vectors also uses the lab KMS key. Runtime IAM grants exact configured inference resources, Retrieve on one KB, and GetObject/PutObject only under `runs/*` and `principals/*`. `ListBucket` is granted on the artifacts bucket so a missing state/lease key returns 404: S3 otherwise returns 403, and GetObject does not carry a ListObjects prefix condition. The app does not list objects or receive object-delete permission. [S3 GetObject permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html)

Separate roles handle application calls, container image/logging access, KB ingestion, GitHub deployment and Express infrastructure. The Express infrastructure role uses the AWS-managed `AmazonECSInfrastructureRoleforExpressGatewayServices` policy; its infrastructure permissions are broader than the application role. Optional Secrets Manager references are passed to the container execution role without storing secret values in Terraform. No external observability secrets are needed for the baseline. [ECS infrastructure role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html)

Application JSON events and safe OpenTelemetry span summaries go to CloudWatch with 14-day retention. A demonstration alarm counts workflow error events. It has no notification target or automatic rollback. Langfuse and Dynatrace exporters are not configured or proven.

## 1. Run offline checks

From the repository root, with Python 3.12 and Terraform 1.12.2:

```powershell
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
python -m unittest discover -s tests -v
python -m unittest discover -s scripts -p deploy_test.py -v
terraform -chdir=infra init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate -no-color
```

The provider is pinned to `hashicorp/aws` 6.66.0 with its dependency lock file. These checks do not authenticate to AWS. CI repeats them, builds a non-root Python 3.12 image, and runs a full offline workflow **inside** the container. Local mode intentionally binds only to loopback, so a published Docker port is insufficient and must not be used to bypass that restriction:

```powershell
docker build -t aws-agent-lab-local .
docker run -d --name aws-agent-lab-local -e LOCAL_DEMO_MODE=true aws-agent-lab-local
docker exec aws-agent-lab-local python /app/container_smoke.py
docker logs aws-agent-lab-local
docker rm -f aws-agent-lab-local
```

On the development workstation the Docker daemon was unavailable. [GitHub Actions run 36757951488](https://github.com/yves-schillings/aws-agent-platform-lab/actions/runs/36757951488) subsequently passed a real Linux Docker build and the offline container smoke test for commit `e24e882046112b45f8b20ebba64e6f268eab7842`, including packaged UI assets, offline auth configuration, retrieval, MCP/agents and the human approval gate. This is container evidence in simulated local mode; an AWS-deployed image still needs the checks below.

On 30 September 2026, isolated `pip-audit==2.10.1` audited the 42 pinned Python dependencies on Windows against the PyPI advisory service: no known vulnerabilities and no skipped packages. CI now runs the same strict dependency check on Linux and retains dated JSON reports for seven days. Vulnerabilities and scanner failures fail the job. This check sends public dependency names/versions to PyPI; it does not scan source code, operating-system packages or the container's image layers. Inspect ECR image findings before cloud image promotion.

The [restart verification](persistence-verification.md) records an actual local HTTP process restart. Approved and rejected decisions, source provenance and hashes survive with the same storage directory; cross-owner access and replay attempts remain denied. That evidence does not establish S3 persistence or recovery of an interrupted in-flight task.

## 2. Establish explicit deployment inputs

Complete the remaining [Stage 0: AWS account setup](aws-account-setup.md)
prerequisites first. Account console access was confirmed by a user-provided
capture on 30 September 2026. Operator access, MFA, the deployment region, budget
controls, models and application services remain unverified. Console access alone
does not provision this lab or prove application authentication through Cognito.

### Connect the operator workstation

AWS CLI 2.37.6 was installed and its version checked on the Windows development workstation using the signed Amazon per-user MSI. No AWS login or resource operation was performed. Open a new terminal for the updated PATH; the per-user executable is `%LOCALAPPDATA%\Programs\Amazon\AWSCLIV2\aws.exe`. Other workstations can follow the [official AWS CLI installation instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

After the account and region are agreed, use the account's existing authorized sign-in method. For IAM Identity Center, obtain the real start URL, SSO region, account and role from the administrator, then use:

```powershell
aws configure sso --profile aws-agent-lab
aws sso login --profile aws-agent-lab
aws sts get-caller-identity --profile aws-agent-lab
```

The SSO region is the directory's location and may differ from the workload region. [AWS SSO profile documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)

For an authorized console identity outside Identity Center, `aws login --profile aws-agent-lab` is an alternative browser sign-in flow. It requires the appropriate local-development sign-in permission. Tools that do not support login sessions directly can use the documented separate `credential_process` profile; verify SDK and Terraform identity resolution before planning. Do not print exported credentials to capture logs. [AWS console sign-in for local development](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)

Compare the returned account and role with the approved deployment identity before any resource action. Keep credentials in the normal AWS profile/cache outside the repository. The operator role used for Terraform is distinct from the application and GitHub roles. These sign-in commands remain operator actions to perform with the user; account access has not been established.

### Record the deployment inputs

Copy `infra/terraform.tfvars.example` to an ignored `infra/terraform.tfvars` and replace every `REQUIRED` value. Do not use invented accounts, regions, repository identifiers or model ARNs. Confirm:

- Authorized 12-digit AWS account; selected commercial AWS region and two actual availability zones. Provider `allowed_account_ids` rejects other accounts.
- ECS Express, Cognito, S3 Vectors, Bedrock Knowledge Bases and the selected embedding/generation models are available together in that region. Verify quotas and account restrictions. Terraform validation cannot verify availability.
- Exact Converse model or inference profile and every ARN required for invocation. Cross-region profiles may require destination model permissions and compatible service control policies. The default Titan Text Embeddings V2 dimensions are 1,024; changing the embedding model requires reviewing its dimensions and storage compatibility. [Bedrock Converse](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference-call.html), [KB permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-permissions.html)
- The account's one-time model access/Marketplace prerequisites are satisfied by an authorized administrator. Runtime and GitHub roles cannot subscribe to models. Model/provider prerequisites vary; no access is assumed. [Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- An actual owner/repository and exact GitHub OIDC subject for environment `aws-lab`. Use the subject format for this repository: new repositories and some renamed/transferred repositories use immutable owner/repository IDs. Do not guess a legacy name-only subject. No wildcard subjects are accepted. Reuse an existing GitHub OIDC provider in the account or explicitly create it, never both. [GitHub AWS OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [subject reference](https://docs.github.com/en/actions/reference/security/oidc)
- Explicit Cognito group mappings, for example `team_alpha` to tenant `alpha`, access level `internal`. Scope values must match `[a-z0-9_-]{1,64}` and the synthetic corpus metadata. Unknown or conflicting groups fail closed. No application users or passwords are provisioned by Terraform.
- Reviewed cost allowance, review/teardown date and `allow_paid_resources=true` only after authorization. The numeric allowance and expiry are acknowledgements/tags, **not** an enforced spending cap or automatic teardown.

Estimate the selected region in [AWS Pricing Calculator](https://calculator.aws/): Fargate task-hours and deployment overlap, ALB hours/LCUs, public IPv4 addresses, ECR storage/scanning, CloudWatch ingestion/retention, KMS keys/requests, S3 storage/versions/requests, S3 Vectors storage/query/ingestion, Bedrock embedding and inference tokens, Cognito active users, data transfer and any future Secrets Manager secrets. A low request count does not remove always-on compute/load-balancer costs. Add account budgets/alerts separately and agree who receives them.

Terraform state initially uses the local backend and must stay outside version control and public build artifacts. Keep it on protected local storage with a recovery copy. Before shared operation, configure an authorized encrypted remote backend with locking and least-privilege access; no state bucket is guessed or created by these files. Do not upload state or saved plans to ordinary CI artifacts. Prefer temporary operator credentials/SSO; the infrastructure administrator is separate from the limited GitHub deployment role.

## 3. Bootstrap infrastructure, then the first image

The following commands are operator actions that create billable resources. They were not executed during development.

1. Leave `enable_service=false`, `app_image_digest=""` and `public_base_url=""`. With reviewed inputs and authorized operator credentials, run `terraform -chdir=infra plan -out=bootstrap.tfplan`, review the full plan, then `terraform -chdir=infra apply bootstrap.tfplan`. This creates supporting resources, including the empty KB, ECR repository and Cognito client, but no running application service.
2. Create GitHub environment `aws-lab`, restrict deployment branches to the default branch and configure required reviewers where available. Set environment variables `AWS_REGION`, `AWS_ACCOUNT_ID`, `AWS_ROLE_ARN` from `github_deploy_role_arn`, and `ECR_REPOSITORY` to the repository **name** (the Terraform `name_prefix`, not its URL). The OIDC subject must match this environment. Credentials are short-lived; no AWS access key is stored in GitHub.
3. After offline CI succeeds for the selected commit, manually run **Publish image or update existing AWS service** on the default branch with `publish_only=true`. It tests before AWS authentication, publishes an immutable commit-SHA tag to the one ECR repository, and reports the `repository@sha256:...` URI. Review the ECR scan findings. Retrying reuses an existing immutable commit tag.
4. Set `app_image_digest` to that exact URI and `enable_service=true`; leave `public_base_url` empty. Review a new Terraform plan and apply it as the infrastructure operator. Express generates the HTTPS endpoint. `/healthz` can return 200 while login/API authorization remains unavailable.
5. Read `terraform -chdir=infra output -json service_ingress_paths`; select the actual HTTPS origin and set `public_base_url` without a trailing slash. Review and apply the configuration change. This replaces the bootstrap localhost callback with the exact HTTPS `/auth/callback` and sets `COGNITO_REDIRECT_URI`. The bootstrap never grants anonymous access. Cognito explicitly uses classic hosted sign-in (domain version 1); managed-login version 2 branding is not part of this configuration.
6. Set GitHub `ECS_SERVICE_ARN` from the Terraform `service_arn` output and `APP_BASE_URL` to the verified HTTPS origin. Runtime mode must remain `LOCAL_DEMO_MODE=false`.

Terraform deliberately ignores later changes to the container image field: image promotion and rollback belong to the scripts/workflows. Terraform still owns environment variables, IAM, identity, network and other service settings. Changing `app_image_digest` after creation does not itself promote an image. Record each deployed digest and redacted deployment receipt.

## 4. Ingest only the synthetic corpus and enroll test users

Create a fresh local export directory using `python scripts/prepare_corpus.py --output artifacts/corpus-export-<unique-name>`. This produces six synthetic text documents and matching Bedrock metadata sidecars. Review the files, then the authorized ingestion operator may run:

```text
aws s3 sync artifacts/corpus-export-<unique-name> s3://<corpus_bucket-output>/documents/ --region <verified-region>
aws bedrock-agent start-ingestion-job --knowledge-base-id <knowledge_base_id-output> --data-source-id <data_source_id-output> --region <verified-region>
```

Wait for the returned ingestion job to complete and inspect failures/statistics before claiming retrieval works. The ingestion operator needs appropriate corpus/KMS and Bedrock permissions; the GitHub deployment role deliberately has none. Preserve metadata sidecars and use only the reviewed `documents/` prefix. Do not add `--delete` to the upload as a routine deployment step. [KB S3 data source](https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html)

An identity administrator creates test users, completes their password/MFA enrollment and assigns the corresponding alpha/beta Cognito groups. Avoid embedding passwords or real email addresses in shell history, Terraform or the repository. Use two separate browser profiles to test real Cognito identities. The local identity selector is never cloud authentication.

## 5. Prove the deployed behavior

Check public `/healthz` and `/auth/config`, then use the browser to sign in. Confirm unauthenticated, wrong-client and expired tokens cannot read/create runs. With separate alpha/beta users, complete one synthetic request per user and verify server-selected KB filters, citations, real Converse usage, real MCP tool evidence, trace records and an artifact hash. A user must not read another tenant's run, source or artifact by changing an ID. Approval must match the reviewed artifact hash, and a stale/repeated decision must fail.

Inspect CloudWatch logs, private S3 state/versions and the actual task IAM/security groups. Confirm no sensitive prompts, document bodies or access tokens enter operational logs. A green load-balancer check or `service_active` receipt proves only service health/configuration; it does not prove Cognito, model access, ingestion or tenant isolation. Record the date, deployed digest, identities/scopes tested and observed results without publishing secrets or business data.

For subsequent versions, run the deployment workflow with `publish_only=false` only after offline CI and review. It preserves the current environment, secret references and logging configuration, changes only the exact image digest, and waits for the target revision. A failed/unverified receipt requires investigation. Use [rollback.md](rollback.md) for a deliberate rollback.

## Production work not completed

Before real data or wider access: review threat model and tenant isolation, organization federation and MFA policy, private egress/network controls, WAF/rate limits, durable job execution/cancellation and idempotency, distributed quotas, multi-task recovery, availability objectives, backup/restore, retention/deletion, key policy restrictions, incident response, alert routing, load/penetration testing, dependency/image scanning enforcement, Terraform remote state, policy checks and deployment approval controls. Langfuse/Dynatrace integrations require separate implementation and data-export approval. This lab does not claim production readiness.

Stopping the task alone does not remove ALB, storage, versions, vectors, keys or logs. Review a teardown plan after the agreed demonstration period. Cognito deletion protection and non-empty bucket/ECR safeguards deliberately require explicit operator handling; preserve any needed evidence first. No automatic cleanup or destructive convenience script is included.

Provider resources/schema were checked against [AWS provider 6.66.0](https://github.com/hashicorp/terraform-provider-aws/tree/v6.66.0/website/docs/r) on 2026-09-30. Availability and runtime behavior must still be verified in the selected account.