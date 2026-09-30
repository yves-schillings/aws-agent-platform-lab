# Initial GitHub issue backlog

These are issue specifications maintained in the repository. They are not published GitHub issues. The implementation has advanced beyond the original CLI baseline; the table below distinguishes current code, local proof and hosted offline checks from the remaining cloud evidence. [GitHub Actions run 36757951488](https://github.com/yves-schillings/aws-agent-platform-lab/actions/runs/36757951488) passed for commit `e24e882046112b45f8b20ebba64e6f268eab7842`, including application/deployment tests, Terraform initialization with a read-only lock file and validation, and a Linux Docker build with an offline workflow smoke test. This verifies the container in local demo mode; it provides no AWS deployment, identity, ingestion or inference proof. No item is complete merely because its files exist.

| Item | Implemented or locally verified | Remaining acceptance |
|---|---|---|
| LAB-01 | Converse adapter and failure/usage tests | Account, budget, region, model access and real inference |
| LAB-02 | Browser/API, sources, exact-hash decisions, full local journey | Deployed browser journey |
| LAB-03 | JWT verification, group policy, two simulated tenants, denial tests | Two real Cognito users, login and deployed denial tests |
| LAB-04 | Mandatory-filter Retrieve adapter, provenance checks, ingestion-file generator | Real embeddings/index ingestion and retrieval evaluation |
| LAB-05 | Real MCP stdio round trip, scope and argument denial tests; tool exercised in the offline container CI workflow | Same tool in the AWS-deployed container |
| LAB-06 | Successful Linux Docker build and offline run; 42 Python dependencies audited with no known findings; completed decisions survive an actual local HTTP process restart | AWS container replacement/S3 persistence and ECR image-scan findings |
| LAB-07 | Terraform schema/static validation and scoped roles | Reviewed plan, deployment, monitoring and teardown |
| LAB-08 | Pinned workflow actions, deployment/rollback scripts and contract tests; hosted offline tests, Terraform validation and Docker smoke passed in the linked CI run | Actual OIDC trust and AWS deployment/rollback runs |
| LAB-09 | Safe structured events, OpenTelemetry instrumentation, persisted decisions and post-restart replay/ownership checks | CloudWatch evidence, S3 persistence and operational fault rehearsal |
| LAB-10 | English/Dutch explanation guide and synthetic scenarios | Cloud evaluation and presenter rehearsal |
| LAB-11 | Explicit production follow-up boundary | Enterprise decisions and operating evidence |

P0 means necessary for the intended Monday demonstration. P1 means a follow-on platform capability to demonstrate if time and account access permit, or otherwise identify honestly as remaining work. A proof of concept does not establish full production readiness. The selected engineering recommendation is recorded in [the proposed architecture](architecture.md); it remains unverified in the target account.

## LAB-01: Establish AWS access and a real Bedrock run

**Priority:** P0. **Dependencies:** authorised account and model access.

- Configure the AWS CLI and a short-lived SSO or role session outside the repository.
- Choose and record the permitted region, model/inference profile and test budget.
- Use least-privilege invocation permissions rather than administrator credentials.
- Run the synthetic workflow against Bedrock and inspect the results, usage and errors.

**Acceptance:** one successful real model call is repeatable; a complete synthetic workflow reaches the human gate; evidence identifies provider/region/model and does not expose credentials. Access denial, unavailable model and truncated output have understandable handling. No cloud-deployment claim is made from inference alone.

## LAB-02: Add a run API and browser interface

**Priority:** P0. **Dependencies:** existing workflow; live inference can follow.

- Implement FastAPI with a small browser interface in one container. Expose create-run, get-status, get-artifact and explicit approve/reject operations.
- Show the request, retrieved documents, each agent result, correction loop and final decision.
- Keep run identifiers server-generated and output paths server-owned.
- Bind decisions to the reviewed artifact hash; handle duplicate requests without repeated publication.
- Set request size and execution limits; choose a safe single-user execution model for the first deployment.

**Acceptance:** a browser user can follow a complete synthetic run and inspect sources. No result is published before a deliberate decision. Modified artifacts, cross-run reads, duplicate decisions and failed calls produce clear outcomes. A local HTTP test covers the main journey.

## LAB-03: Enforce source access before retrieval

**Priority:** P0. **Dependencies:** identity approach and retrieval boundary.

- Define two Amazon Cognito demonstration users and documents with distinct access permissions; disable public sign-up.
- Verify Cognito token signature, issuer, expiry, token use, app client and required route scopes in FastAPI. Do not presume the Express Mode listener already performs authentication.
- Derive allowed source scope from verified identity, never a user-supplied role string.
- Apply permissions before retrieval and preserve the filter for every agent and citation.
- Keep caches and run access scoped to the same identity boundary.

**Acceptance:** the restricted user cannot retrieve, cite, read a run containing or infer a hidden document through the API. Tests cover both authorised and denied paths and attempts to override the source filter. The existing `authorized: true` corpus flag is not presented as this capability.

## LAB-04: Replace lexical ranking with vector retrieval

**Priority:** P0. **Dependencies:** LAB-01 and LAB-03; regional and model availability checks.

- Put a small synthetic corpus in a private ordinary S3 source bucket; use Amazon Bedrock Knowledge Bases to chunk/embed it into an S3 Vectors index. Verify embedding model access and dimensions.
- Preserve source identifiers, source versions and access metadata on chunks.
- Implement the Knowledge Bases `Retrieve` adapter with server-owned equality/conjunction metadata filters and a lexical fallback for local demonstrations. Never accept a client/model-generated filter that widens permissions.
- Build a small labelled question set to compare lexical and vector results.

**Acceptance:** a paraphrased query retrieves the expected source, restricted material remains excluded, citations resolve to the displayed source version, and evaluation records retrieval quality and observed latency. Document the chosen AWS service, cost drivers and index lifecycle. Do not equate vector search with reliable factual answers.

## LAB-05: Demonstrate one bounded MCP tool

**Priority:** P0. **Dependencies:** explicit tool policy and authentication boundary.

- Add one local stdio Model Context Protocol (MCP) server exposing the deterministic read-only `check_required_documents` tool over synthetic inputs. Pin the official Python SDK version.
- Give the tool a strict input/output schema, host-side identity/scope authorisation, timeout and response-size limits. The process and executable are fixed by trusted configuration; there is no public MCP endpoint.
- Allowlist the tool and its destination in application configuration.
- Keep any write operation outside the initial read-only tool scope.

**Acceptance:** an authorised call succeeds, malformed arguments and an unauthorised call fail, and the trace identifies the tool/result without secrets. Document injection cannot select an arbitrary tool, executable, host or command. Present this as one constrained integration, not general external-system access.

## LAB-06: Package and run the application in a container

**Priority:** P0. **Dependencies:** LAB-02.

- Add a pinned Python runtime, reproducible dependency lock and small application image.
- Run as a non-root user; provide health/readiness endpoints and shutdown handling.
- Pass configuration through environment/role mechanisms; exclude secrets, documents and local outputs from the image.
- Persist versioned run artifacts in an ordinary private S3 bucket before using ephemeral cloud instances. Keep this separate from the S3 vector bucket/index.

**Acceptance:** the same image completes a mock workflow locally and passes health checks. Restart/storage behaviour is understood. A vulnerability/dependency check is recorded with any unresolved findings. No credentials or personal files are present in the image layers.

## LAB-07: Provision the smallest useful AWS deployment with Terraform

**Priority:** P0. **Dependencies:** LAB-01, LAB-02 and LAB-06.

- Provision Amazon ECS Express Mode on Fargate, ECR image registry, Cognito, ordinary S3 source/artifact storage, Knowledge Bases/S3 Vectors and CloudWatch logging. Pin a Terraform AWS provider supporting `aws_ecs_express_gateway_service` and verify its schema.
- Configure the service's public/private networking explicitly and document the actual result. Do not draw private tasks as the untouched Express public-subnet default.
- Separate deployment role, task execution role, application task role and knowledge-base ingestion role. Use temporary workload credentials, not an AWS key in the image.
- Define cost-related limits, retention settings, resource tags and teardown instructions.
- Protect remote Terraform state; never commit state, plans or live variable files.
- Make the account, region and environment explicit. Review the plan before an actual deployment.

**Acceptance:** Terraform validation and a reviewed plan succeed; deployment produces an authenticated HTTPS demo in the authorised AWS account; the runtime reaches only intended services; S3 persistence, conditional writes and teardown are verified. Re-deploying the last verified image digest and configuration restores the demonstration. Express canary deployment is not described as a rolling-update circuit breaker. Cloud resources are described as deployed only after successful execution and inspection.

## LAB-08: Add GitHub Actions with AWS OIDC federation

**Priority:** P0 for offline continuous integration; P1 for cloud delivery automation. **Dependencies:** remote repository and LAB-07 for deployment.

- Run offline tests and dependency checks on pull requests.
- Build an immutable image and retain its digest and source commit identity.
- Use OpenID Connect (OIDC) federation for AWS deployment, with no long-lived AWS secret in GitHub.
- Restrict the AWS trust policy to the actual repository and deployment branch/environment. Inspect the actual OIDC subject format rather than assuming an older repository-name-based subject; pin third-party actions to full commit SHAs.
- Separate untrusted pull-request checks from deployment permissions.

**Acceptance:** a normal pull request runs checks without AWS deployment credentials; only the selected trusted workflow can obtain the scoped deployment role. The deployed image maps to a source commit and can be rolled back. Do not publish a workflow with a placeholder owner or overly broad trust condition.

## LAB-09: Produce useful traces and an operating runbook

**Priority:** P0. **Dependencies:** LAB-01, LAB-02 and cloud deployment for cloud evidence.

- Send structured run, agent, tool and model events to CloudWatch; expose latency, failure counts and available token usage. Add OpenTelemetry spans for the API, retrieval, model and MCP boundaries.
- Keep secrets and unnecessary prompt/document content out of logs.
- Label estimated cost separately from measured usage; unknown cost remains unknown.
- Define diagnosis steps for access failures, throttling, model timeouts, retrieval failures and interrupted runs. Allow one active run per user; an interrupted run fails explicitly instead of claiming automatic durable resume.
- Document start, stop, rollback, retention and cleanup procedures.

**Acceptance:** one successful and one failed run can be explained from the traces. The runbook lets another operator reproduce the demo and recover from a known failure. A restart does not silently lose or duplicate an approved decision.

## LAB-10: Evaluate the workflow and rehearse in English and Dutch

**Priority:** P0. **Dependencies:** minimum end-to-end deployment.

- Prepare synthetic English and Dutch requests and a small fixed expected-result set.
- Check source relevance, groundedness, unknown-answer behaviour and language consistency.
- Include negative demonstrations: hidden source, unsupported citation, injection attempt, denied tool, model failure and changed artifact hash.
- Rehearse a five-minute demonstration and a deeper architecture explanation.
- Prepare an offline mock fallback with clearly labelled simulated inference.

**Acceptance:** a dated evidence table records expected/observed results and remaining gaps. Both language journeys are rehearsed. The presenter can explain every component, source permission, model call, controlled action and deployment boundary. Unimplemented requirements remain visibly listed.

## LAB-11: Harden platform capabilities after the demonstration

**Priority:** P1 after the initial demonstration.

Confirm production requirements for tenant isolation, availability, scalable orchestration, concurrent decisions, durable execution, evaluation gates, model governance, network isolation, incident response, disaster recovery, data retention and infrastructure lifecycle. Langfuse/Dynatrace trace export, enterprise federation, Kubernetes integration and private-network production topology need separate configuration and tests. Convert the confirmed requirements into separate issues with measurable acceptance criteria. A successful four-day lab is evidence of a learning implementation, not a substitute for these decisions or operating experience.
