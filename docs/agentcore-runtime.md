# Amazon Bedrock AgentCore Runtime integration

- **Purpose**
  - Run the existing Python Factory in Amazon Bedrock AgentCore Runtime. Amazon Bedrock still supplies model inference; AgentCore hosts the agent application around those model calls.
  - Preserve the five AI agents (Analyst, Architect, Code Author, Tester and Reviewer), LangGraph orchestration and four human approval gates.
  - Keep the current browser entry point and FastAPI backend. The inbound MCP (Model Context Protocol) server remains separate; its AgentCore routing is not implemented by this change.
  - A minimum cloud deployment is verified below. Its engineering caller uses a separate Cognito test client; the deployed ECS browser has not been switched to the source connector.

## Implemented call path

- **Browser and trusted backend**
  - The browser signs in with Amazon Cognito and sends an access token to the existing FastAPI Factory endpoints.
  - `web.py` verifies that token before selecting `AgentCoreFactoryClient` when `FACTORY_BACKEND=agentcore`.
  - `agentcore_client.py` calls `InvokeAgentRuntime` using the backend's AWS IAM (Identity and Access Management) role and Boto3 (the official Python library for calling Amazon Web Services).
- **Runtime identity and permissions**
  - The IAM signature authenticates the backend workload. The original Cognito token in the invocation payload identifies the human separately.
  - `agentcore.py` independently verifies the Cognito signature, issuer, expiry, client identifier, token type and required scopes.
  - Server-owned policy maps verified groups to company access and gate permissions. The request cannot supply a trusted principal, company or role.
  - The token is used inside this trusted application path only. It is not passed to model prompts or business APIs (Application Programming Interfaces).
  - Do not enable request-body or invocation-payload logging: the IAM-mode payload contains an access token.
- **Workflow and state**
  - The Runtime container executes the five existing Python workers. LangChain or Boto3 calls Amazon Bedrock for inference.
  - Production startup requires the existing Amazon DynamoDB checkpoint and run-registry tables. Separate Runtime sessions must share durable state and approval leases.
  - Each gate still requires a distinct authorised approver and the exact artifact hash. AgentCore does not replace these application checks.

## Container contract

- **Files**
  - `Dockerfile.agentcore` packages the application for the Runtime service.
  - `src/aws_agent_platform_lab/agentcore.py` exposes `POST /invocations` and `GET /ping` on port 8080.
  - Requests select `start`, `read` or `decide`. Responses contain either `result` or a bounded business `error` envelope.
  - Health returns `HealthyBusy` during active workflow work and `Healthy` otherwise.
- **Build command**
  - Build an ARM64 image using `docker buildx build --platform linux/arm64 -f Dockerfile.agentcore -t agentcore-factory:review --load .`.
  - This command needs a running Docker daemon and ARM64 build support. The image must be built and checked before publication to Amazon ECR (Elastic Container Registry).
  - The existing ECS (Elastic Container Service) deployment workflow does not deploy this new image to AgentCore.

## Minimum cloud configuration

- **Existing web backend environment**
  - Substitute the runtime ARN (Amazon Resource Name) placeholders in the example policy before applying it, and change `DEFAULT` if using another endpoint qualifier.
  - Set `FACTORY_ENABLED=true`, `FACTORY_BACKEND=agentcore`, `AWS_REGION`, `AGENTCORE_RUNTIME_ARN` and `AGENTCORE_RUNTIME_QUALIFIER=DEFAULT`.
  - Retain the existing Cognito sign-in configuration and `ACCESS_POLICY_JSON`. Do not replace Cognito merely because the worker hosting changes.
  - Grant the backend role `bedrock-agentcore:InvokeAgentRuntime` on the exact runtime and its selected runtime endpoint. See `infra/agentcore-caller-policy.example.json`.
  - Restrict the Runtime resource policy and backend role assumption to approved callers. A local HTTP server alone does not enforce AWS SigV4 signatures.
- **Runtime environment and execution role**
  - Set `AGENTCORE_INBOUND_AUTH=iam`, `AGENTCORE_LOCAL_TEST=false`, `LOCAL_DEMO_MODE=false` and `FACTORY_PROVIDER=aws-langchain`.
  - Configure `AWS_REGION`, `FACTORY_CHECKPOINTS_TABLE`, `FACTORY_RUNS_TABLE`, `BEDROCK_KNOWLEDGE_BASE_ID` and the existing Bedrock model/provider settings from the AWS runbook.
  - Configure the same trusted Cognito issuer, user pool, application client, scope policy and `ACCESS_POLICY_JSON` as the backend. The reused Cognito settings also require its domain and redirect URI (Uniform Resource Identifier).
  - Grant the separate Runtime execution role only the required model, retrieval and DynamoDB operations. Backend invocation permission does not grant the Runtime these permissions.
  - Configure network access to the Cognito public signing keys, Bedrock and DynamoDB, and apply the existing secrets-management controls.
  - Keep both Runtime invocation and the synchronous backend call within tested service timeouts. The connector currently waits up to 300 seconds.

## Authentication variants

- **Cognito plus backend IAM**
  - This is the implemented remote connector path. It does not require a Microsoft Entra ID tenant.
- **Direct Cognito JWT (JSON Web Token)**
  - The Runtime application also accepts `AGENTCORE_INBOUND_AUTH=cognito-jwt` and validates a Bearer token from `Authorization`.
  - AgentCore must be configured with its Cognito JWT authorizer and an allowlist that forwards `Authorization`. Header size limits apply.
  - An IAM authorizer and JWT authorizer are different Runtime configurations. The supplied Boto3 connector supports IAM, not direct JWT invocation.
  - A direct JWT caller and real authorizer deployment remain separate integration work.
- **Microsoft Entra ID**
  - Entra diagrams describe an architectural option. This code does not validate Entra tokens or demonstrate tenant federation.
  - No Microsoft tenant is needed for the offline tests or the Cognito plus IAM path. End-to-end Entra validation still requires a tenant and registered applications.
- **Engineering IAM access**
  - IAM alone identifies a workload, not a human gate approver. This Factory intentionally requires a verified human Cognito token even behind the IAM perimeter.

## Verified minimum deployment on 5 October 2026

- **Runtime and source**
  - Runtime `secloudis_factory_minimum-RPuPF760W2` is READY in `eu-west-1`, with version 3 served by DEFAULT.
  - The exact ARM64 application source is revision `42fc116abbeedc9fa65983b4cfeaba4bd69e7c91`.
  - Its deployed image manifest is `sha256:256f7c30df34bb18ba5be72f0e53bae2899737500496e29df01134d76287f82d`.
  - The eight-resource Terraform stack reuses the existing Cognito pool, Bedrock inference and retrieval, and DynamoDB state. The container runs as user `10001:10001` with a 60-second idle timeout and 900-second maximum instance lifetime.
  - [Dated machine-readable evidence](agentcore-deployment-evidence.json) records the verified source, image, run, model usage, request identifiers and explicit limits.
- **Real synthetic workflow**
  - Run `0fcf900126e04e5db7367cdf1c60966e` reached `release_ready` with five model-backed artifacts and four gate decisions.
  - Analyst, Architect, Code Author, Tester and Reviewer called Amazon Nova Lite through LangChain on Bedrock.
  - The requester and approver had distinct real Cognito subjects. Decisions were scripted API (Application Programming Interface) acceptance checks, not human review of the generated content.
  - Shared DynamoDB state was read and advanced across four Runtime sessions.
  - Cross-company access, owner self-approval and stale artifact hashes were denied.
  - The five model calls reported 11,795 input tokens and 1,078 output tokens. The billed cloud cost has not been verified.
  - Proposed code and tests remain inert text; no generated application was built, executed or deployed.
- **Identity boundary**
  - An unapproved IAM user was denied even with an identity policy permitting this Runtime invocation.
  - An approved IAM caller reached the handler, which denied missing and invalid human access tokens.
  - Runtime and DEFAULT endpoint policies are both configured. Administrative root calls reached the handler; root isolation is not demonstrated.
  - All three synthetic Cognito users and the disposable IAM operator, key and inline policy were removed after acceptance.
- **Checks and observed defect**
  - All 171 application tests and eight deployment-script tests passed locally. Ruff passed across source, tests and scripts; Mypy passed for its two configured files; the separate Terraform stack validated.
  - The first cloud run exposed DynamoDB transaction conflicts between checkpoint writes. The deployed fix serializes one operation's writes and retries only atomic transaction conflicts, at most five times, while rechecking the lease.
  - A failed lease condition or exhausted retry budget still refuses the write. Two additional offline tests cover recovery and bounded failure.
  - The inspected sample of 176 CloudWatch events contained no JWT (JSON Web Token) pattern. That sampled result is not a claim about every possible log configuration.
- **Remaining integrations**
  - The existing ECS (Elastic Container Service) browser is not routed to AgentCore. Connecting it requires alignment of its Cognito client and scope, backend invocation permissions, and the `FACTORY_BACKEND=agentcore` deployment setting.
  - AgentCore routing for the inbound MCP server remains unimplemented.
  - A direct Cognito JWT cloud authorizer and Microsoft Entra token integration remain unverified. No Microsoft tenant was created.
  - Expired and wrong-client tokens have offline validation coverage; those two negative cases were not exercised against the live Runtime.
  - Cross-session shared-state access was verified; forced Runtime restart recovery remains a separate operational test.
- **Retry limitation**
  - Automatic SDK retries are disabled because a start or decision may succeed before a transport timeout.
  - Reload a known run before retrying a decision. A timed-out start can leave a run whose identifier was not returned; idempotent start recovery is not yet implemented.
- **Article review**
  - The deployment evidence supports a revised article status section. Its Word review document remains subject to user approval before WordPress publication.

## Official service references

- [AgentCore HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html).
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html).
- [Runtime OAuth authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html).
- [AgentCore IAM actions and resource types](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock-agentcore.html).
- [AgentCore resource-based policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-based-policies.html).
