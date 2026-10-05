# Amazon Bedrock AgentCore Runtime integration

- **Purpose**
  - Run the existing Python Factory in Amazon Bedrock AgentCore Runtime. Amazon Bedrock still supplies model inference; AgentCore hosts the agent application around those model calls.
  - Preserve the five AI agents (Analyst, Architect, Code Author, Tester and Reviewer), LangGraph orchestration and four human approval gates.
  - Keep the current browser entry point and FastAPI backend. The inbound MCP (Model Context Protocol) server remains separate; its AgentCore routing is not implemented by this change.

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

## Verification and remaining acceptance work

- **Offline verification**
  - On 5 October 2026, all 168 application tests and eight deployment-script tests passed locally. Ruff passed across application, tests and scripts; the existing incremental Mypy check passed for its two configured identity/model files.
  - The six new AgentCore tests are included in that application total. Docker Desktop's Linux daemon was unavailable during this check, so no AgentCore ARM64 image build or cloud execution is claimed.
  - `tests/test_agentcore.py` exercises the Runtime with locally signed test tokens and mock inference, including the full four-gate journey, cross-company denial, owner/approver separation and stale artifact decisions.
  - The browser-to-backend-to-connector-to-Runtime test uses an injected transport. It performs no AWS request and establishes no live Cognito or AgentCore deployment.
  - A restart test reopens local SQLite state. Real DynamoDB cross-session persistence still requires cloud acceptance testing.
- **Cloud acceptance**
  - Build and inspect the ARM64 image; publish its exact digest; configure a restricted Runtime and caller role.
  - Verify unauthorised IAM callers are denied before the container, and missing, expired or wrong-client human tokens are denied inside it.
  - Complete a synthetic run with a requester and distinct approver across G1–G4 and across separate Runtime sessions.
  - Record Bedrock inference, DynamoDB recovery, logs with no tokens, response latency and cloud cost before updating the central article status.
- **Retry limitation**
  - Automatic SDK retries are disabled because a start or decision may succeed before a transport timeout.
  - Reload a known run before retrying a decision. A timed-out start can leave a run whose identifier was not returned; idempotent start recovery is not yet implemented.
- **Delivery boundary**
  - This source change does not create AWS resources, replace the existing ECS service, deploy an AgentCore Runtime, update the article or publish an Entra integration claim.

## Official service references

- [AgentCore HTTP protocol contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html).
- [Runtime header allowlist](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html).
- [Runtime OAuth authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html).
- [AgentCore IAM actions and resource types](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock-agentcore.html).
- [AgentCore resource-based policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-based-policies.html).
