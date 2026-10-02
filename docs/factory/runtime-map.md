# Runtime and deployment mapping

**Gate key:** G means Gate, a human approval checkpoint: G1 Scope, G2 Design, G3 Quality, G4 Release. Release authorises deployment of the exact reviewed version.

This table separates the current demonstration infrastructure from the complete factory target. Component ownership describes roles to assign; it does not imply that any organisation has accepted production operation.

**Separate local increment:** [factory.py](../../src/aws_agent_platform_lab/factory.py) adds deterministic LangGraph routing through five roles and four gates, with SQLite checkpoints. The `/factory` inspection prototype and `/api/factory/runs` are local-only. They do not change the AWS baseline mapped below: real Factory inference, remote tools, authenticated approver roles, generated-code execution and cloud durability remain unfinished. See [development stages](../development-start.md) and [conversational access](../conversational-access.md).

| Logical component | Current source or definition | Current deployment behavior | Factory dependency / owner |
|---|---|---|---|
| Intake and human interaction | [web.py](../../src/aws_agent_platform_lab/web.py), [static UI](../../src/aws_agent_platform_lab/static/) | One FastAPI/UI container, one exact-artifact decision | Four-gate application and role policy; factory engineering + designated gate owners |
| Identity and source policy | [auth.py](../../src/aws_agent_platform_lab/auth.py), Cognito in [main.tf](../../infra/main.tf) | Signed access-token checks and server group→scope map; real AWS login unverified | Federation, permission-change lifecycle and production identity ownership |
| Orchestrator | [services.py](../../src/aws_agent_platform_lab/services.py), [workflow.py](../../src/aws_agent_platform_lab/workflow.py) | Three sequential roles, bounded corrections, worker slots and leases | Five-worker routing, durable task envelopes, gate state machine, recovery; factory engineering |
| Inference | [providers.py](../../src/aws_agent_platform_lab/providers.py) | Bedrock Converse adapter with call bounds; mock verified locally | Account/model qualification, role-specific prompts/evaluations; model governance owner |
| Context service | [retrieval.py](../../src/aws_agent_platform_lab/retrieval.py), Knowledge Base/S3 Vectors Terraform | Mandatory source filter and response recheck; live index unverified | Broader source adapters, permissions/version-change propagation; source owners + platform engineering |
| State and evidence | [storage.py](../../src/aws_agent_platform_lab/storage.py), private versioned S3 definition | Local persistence verified; S3 conditional adapter defined | Multi-step candidate/gate transactions, checkpoint recovery, evidence retention/signatures; platform/operator |
| Tool host | [mcp_tool.py](../../src/aws_agent_platform_lab/mcp_tool.py), [mcp_server.py](../../src/aws_agent_platform_lab/mcp_server.py) | One fixed read-only stdio checklist; real local protocol verified | Additional tools only with contract/authority/tests; integration owner |
| Generated-code sandbox | **Missing** | None. Current MCP process is not a hostile-code isolation boundary | Separate disposable Fargate task, no application task role or production credentials, bounded outputs and network; security + factory engineering |
| Trusted validator | **Missing for generated candidates** | Existing CI checks this platform repository | Protected tests and isolated validator for a candidate commit/image; quality owner |
| Repository and build | [CI](../../.github/workflows/ci.yml), [Dockerfile](../../Dockerfile) | Builds and checks the platform image; container evidence recorded | Controlled candidate repository, build attestation and review binding; engineering/release owner |
| Release pipeline | [deploy workflow](../../.github/workflows/deploy.yml), [deployment script](../../scripts/deploy_express.py) | Updates the platform service image by digest after manual dispatch | Separate candidate target, G4 enforcement and deployment role; release authority |
| Candidate application | **Missing** | No generated business application resource exists | Separate service and data plane with agreed interfaces/migrations; application owner |
| Observability | [telemetry.py](../../src/aws_agent_platform_lab/telemetry.py), CloudWatch definition | Safe local events/spans; cloud alarms/logs need live verification | Alert routing, service objectives, support and recovery commitments; named operator |

## Deployment boundaries

The current [Terraform](../../infra/) creates the platform's supporting services and optionally its ECS Express/Fargate service. It does not create a generated-code sandbox, trusted candidate-validation service, five worker deployments, candidate repository or target application. Applying it cannot complete slides 05, 06, 08 or 14's target capabilities.

The controller and workers may share code packages in an initial implementation, but execution authority must remain separated. Inference models receive requests; they do not receive deployment credentials. The untrusted sandbox must not share the controller task's runtime role, writable evidence store or trusted validator configuration.

The target sandbox has no application task role. Its execution role only permits image pulling and log delivery. Private subnets, approved VPC endpoints, scoped endpoint policies and DNS controls bound required network access; no Docker host socket is exposed. The output collector and trusted validator remain separate target components; see [D08](../slides/08-sandbox-and-validation.md).

Current account, region, model access, cost allowance and operational ownership remain inputs to establish. Use the actual [deployment guide](../deployment.md), not invented Terraform variables or a guessed cloud diagram.

## Selected code-first target

The three-role Python controller and local stdio MCP checklist remain the implemented baseline. LangGraph is now a pinned dependency for the separate deterministic Factory increment. LangChain AWS `ChatBedrockConverse` and three company-owned remote MCP endpoints over Streamable HTTP/HTTPS remain target work. `DynamoDBSaver` is a candidate cloud checkpointer to qualify, not deployment evidence; current Factory checkpoints use local SQLite. The [migration plan](multi-company-api-architecture.md#selected-python-workflow-and-company-mcp-connections) preserves the existing evidence and specifies crash/restart, authorisation and exact-version gate checks. The generated output is one [common affiliation-consultation application](../slides/31-shared-application-and-company-apis.md), which will use company business APIs directly at runtime.
