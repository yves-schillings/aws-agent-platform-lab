# Multi-Agentic Workflow on AWS — Proposed Epic and Feature Backlog

By **Yves Schillings, Secloudis** · Planning snapshot: **30 September 2026** · Source revision: `86ac8aa`

This backlog proposes an incremental delivery order. It retains the complete Factory scope; the initial demonstration scope is not an already-approved scope reduction.

## Hierarchy and priorities

**Epic > Feature > Item.** An epic groups a capability outcome, a feature defines observable behaviour, and a future item defines executable work. This version contains **9 epics and 35 features**; detailed items are **not yet expanded**.

- **P0 — Initial AWS demo:** prioritise a repeatable, verified AWS demonstration: the platform, three real roles, one exact-artifact human decision and risk-based tests. External account and service dependencies determine readiness.
- **P1 — Complete Factory:** build five workers, four human gates, isolated candidate execution, independent validation and release to a separate application after the first verified AWS slice.
- **P2 — Production and Azure:** agree production requirements, ownership and evidence before industrialisation; an Azure edition is a separate later phase.

Priority expresses the proposed work sequence; dependencies below express actual feature prerequisites.

## Current evidence boundary

The current implementation has three sequential roles, bounded corrections and one human decision bound to an exact artifact hash. The local browser workflow, source controls, persistence and fixed read-only MCP tool have local evidence. A hosted CI run on revision `e24e882` validated tests, Terraform and a container in offline mode; it is not live AWS evidence and must not be silently attributed to another revision.

Cognito, Bedrock Converse, Knowledge Bases and S3 adapters and infrastructure definitions exist. **Real application login through Cognito, inference, ingestion, deployment, persistence and operational results remain unverified.** Account console access is confirmed; operator access, MFA, deployment region, models and budget controls still require evidence.

The target five-worker/four-gate Factory, generated-code sandbox, independent candidate validator and separate target application are not delivered by the current platform deployment.

The selected code-first target uses LangGraph for Python orchestration, LangChain AWS `ChatBedrockConverse` for Bedrock, and the official MCP Python SDK for explicit tool nodes connecting to three company-owned MCP servers. A separate local increment now implements deterministic LangGraph roles, four simulated gates and SQLite checkpoints. LangChain AWS and remote company connectors remain unimplemented. This local progress refines EP-05 without satisfying its complete cloud acceptance criteria. See the [development evidence](../development-start.md).

**Gate key:** G means Gate, a human approval checkpoint: **G1 Scope**, **G2 Design**, **G3 Quality**, **G4 Release**. G4 Release authorises deployment of the exact reviewed version.

Budget alerts do not themselves stop billing. The authorised budget needs technical usage limits and an owner responsible for shutdown.

## Epics and features

### EP-01 — Application to Generate and Acceptance Tests

Specify the application the Factory must generate, using the already-defined shared affiliation-data consultation case for three anonymised companies, and define its data and acceptance tests.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F01-01 — Describe the application the Factory must generate** | P0 | None | A testable specification describes one shared, read-only application for three anonymised companies to consult synthetic affiliation records, with search, filters, effective dates and owner-authorised access; it implements the selected CSV-to-consultation case without real insurance decisions. It defines each company/external box function, example, hosting assumption and selective business exchange. External A/B/C use proposed contract mocks, not assumed MCP servers. The Factory produces versioned, tested application code released only after four human gates. | Application case already retained; testable specification and external fixture contracts to complete. |
| **F01-02 — Prepare sample data and expected application behaviour** | P0 | F01-01 | Synthetic affiliation records and identities represent all three companies, with expected fields, date boundaries, provenance and refusals. Specify a Company 2-owned record granted to Company 1, Company 3 denial before a provider call, optional external A/C routing/coverage and independent B reference fixtures. Approved documents separately supply Factory context; no real external contract or legal decision is claimed. | Synthetic scenarios exist; affiliation data, expected results and external mocks remain to be prepared. |
| **F01-03 — Define tests for generation, approval and deployment** | P0 | F01-01, F01-02 | Define pass/fail checks for generation, quality, permissions, exact-version approval and release. Business contract cases cover app and owner grant checks, wrong service client/resource, permitted fields, effective dates, revocation, 403 before provider invocation and 502/504 without invented results. Execute checks as the corresponding capabilities are implemented. | Target journey defined; generation/approval/deployment contract tests to formalise; AWS execution unverified. |

### EP-02 — AWS Account and Deployment Readiness

Qualify external dependencies and the conditions for a controlled first AWS run.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F02-01 — Secure administrator and deployment access** | P0 | F01-01 | Root MFA is confirmed and a separate temporary operator session proves the intended account and least-privilege access without repository secrets. | Account console accessed; MFA and operator access unverified. |
| **F02-02 — Confirm available AWS services and AI models** | P0 | F02-01 | The selected region, inference and embedding models, required services, quotas and account restrictions are verified before deployment. | Architecture defined; live availability and models unverified. |
| **F02-03 — Set spending alerts and clean up resources** | P0 | F02-01 | An authorised budget, spend alerts, technical usage limits, retention policy and named shutdown owner are recorded and verified. | Controls described; account budget and alerts unverified. |
| **F02-04 — Save deployment settings and protect infrastructure state** | P0 | F02-02, F02-03 | The actual deployment configuration, protected Terraform state, separate roles, network settings and reviewed plan match the qualified account and region. | Definitions exist; actual plan and state protection unverified. |

### EP-03 — First Live AWS Vertical Slice

Reuse the current platform to connect an authenticated request to a real, reviewable result.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F03-01 — Real Bedrock Inference** | P0 | F01-02, F02-01, F02-02, F02-03 | Repeatable real Bedrock inference takes the synthetic three-role workflow to human review, with model, region, usage and failure evidence. | Adapter and local tests exist; real inference unverified. |
| **F03-02 — Authenticated AWS Platform Deployment** | P0 | F02-04, F03-01 | An identified platform image runs behind HTTPS with API-verified Cognito identities, rejected invalid tokens and inspected health checks. | Application and definitions exist; AWS runtime/login unverified. |
| **F03-03 — Permission-Aware Live Retrieval** | P0 | F02-02, F03-02 | Live Knowledge Bases retrieval preserves source versions and server-owned permissions, finds expected paraphrased queries and excludes restricted sources. | Adapter and filters tested locally; live ingestion/index unverified. |
| **F03-04 — Three-Role Workflow and Exact-Artifact Decision** | P0 | F03-03, F04-01 | The deployed browser completes three real Bedrock roles, bounded corrections and the fixed MCP tool, publishing only after a decision bound to the inspected artifact hash. | Local journey verified; deployed end-to-end journey unverified. |

### EP-04 — Evidence, Risk Tests and Initial AWS Demo

Test meaningful failures and prepare a repeatable, understandable demonstration.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F04-01 — Cloud State, Evidence and Safe Traces** | P0 | F03-02 | S3 state, artifacts and decisions remain consistent while safe CloudWatch traces explain one successful and one failed run. | Local persistence and instrumentation exist; cloud evidence unverified. |
| **F04-02 — Risk-Based Live Acceptance Tests** | P0 | F03-04, F04-01, F09-03 | Dated AWS tests record expected and observed results for access boundaries, invalid citations, injection, tool denial, model failures, changed hashes and replayed decisions. | Local negative tests exist; AWS execution pending. |
| **F04-03 — Recovery, Rollback and Cleanup Rehearsal** | P0 | F03-04, F04-01 | Container replacement preserves approved decisions, interrupted work fails explicitly, and the last verified image/configuration can be restored using the runbook. | Local restart tested; AWS replacement and rollback unverified. |
| **F04-04 — English and Dutch Demonstration Readiness** | P0 | F01-02, F04-02, F04-03 | English and Dutch demonstrations are rehearsed on frozen evidence, with an explicit simulated fallback and reviewed public documentation aligned with the private planning artifacts; public release readiness also confirms the explicitly selected open-source licence, usable code, installation/demo instructions and reproducible synthetic examples. | Guide and fallback exist; live evaluation, rehearsal, licence selection and public release readiness pending. |

### EP-05 — Five-Worker Factory and Human Gates

Extend the verified baseline into five workers, four human gates and durable execution.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F05-01 — Five-Worker Roles and Task Contracts** | P1 | F03-04, F01-03 | Five workers have versioned responsibilities, schemas, permissions and execution limits that reject and trace invalid or out-of-scope tasks. | Five deterministic local roles implemented. Real model work, tool authority and execution limits remain pending. |
| **F05-02 — Four Human Approval Gates** | P1 | F05-01 | An enforced state machine applies G1 Scope, G2 Design, G3 Quality and G4 Release with authorised human decisions and tested rejection and version-change paths. | Four hash-bound local gates tested with simulated owners; authenticated human roles and correction/resubmission remain pending. |
| **F05-03 — Durable Orchestration and Controlled Recovery** | P1 | F05-01, F05-02, F04-01 | Persisted tasks and transitions recover or fail at defined checkpoints without repeating a confirmed decision or action. | SQLite gate restart and concurrent-decision checks pass locally. Mid-execution recovery and cloud checkpoint qualification remain pending. |
| **F05-04 — Versioned Context and Tool Authority** | P1 | F05-01, F03-03 | Every task and tool preserves source versions and authority, with tested permission-change invalidation. Register/version company MCP construction contracts separately from runtime business API contracts and selective external mocks; define identity, owner grants, schemas, bounded calls and errors for each. | Filtered context and one read-only tool exist; multi-source lifecycle and expanded Factory/runtime contracts remain to define. |

### EP-06 — Candidate Isolation and Independent Validation

Execute and inspect candidate code without granting platform or target-application authority.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F06-01 — Candidate Repository and Build Provenance** | P1 | F05-01, F05-02 | A separate controlled candidate repository links approved design, immutable commit and build digest while protecting validation and release rules from workers. | Platform repository exists; candidate repository/build provenance absent. |
| **F06-02 — Disposable Generated-Code Sandbox** | P1 | F06-01, F05-04 | A disposable candidate task has no application role or production credentials and passes probes for network, resource, output and authority isolation. | Absent; the current MCP process is not a hostile-code sandbox. |
| **F06-03 — Trusted Candidate Validation** | P1 | F06-01, F06-02, F05-02 | A separate trusted validator runs protected functional, contract, security, migration, consistency and performance checks against the exact candidate and supplies evidence to G3 Quality. Include positive owner-authorised sharing, app-side 403 with zero provider calls, downstream wrong client/grant/resource rejection, permitted fields/dates and 502/504 contract failures. | Platform tests exist; independent validator and protected tests for generated candidates are absent. |

### EP-07 — Exact-Version Release to a Separate Application

Separate the Factory from its product and deploy only the exact approved candidate.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F07-01 — Separate Target Application and Data Plane** | P1 | F06-01, F05-02 | The target application has its own service, identity, configuration, data and tested interfaces, separated from the Factory and sandbox. | Absent from current infrastructure. |
| **F07-02 — G4 Release Binding and Federated Delivery** | P1 | F06-03, F07-01, F05-02 | G4 Release and restricted OIDC delivery permit only the reviewed commit, image, configuration and evidence, rejecting changes, stale evidence and unauthorised workflows. | Platform scripts exist; actual federation and candidate G4 delivery unverified. |
| **F07-03 — Application Release Verification and Recovery** | P1 | F07-02 | Post-deployment checks prove the target version and a failure rehearsal demonstrates controlled rollback or repair with migration and data recovery evidence. | Platform rollback described; target application recovery absent. |

### EP-08 — Production Operations and Later Azure Edition

Establish production commitments and address Azure only after the AWS path is verified.

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F08-01 — Governance, Ownership and Production Acceptance** | P2 | F07-03 | Production owners, service commitments, model governance, evidence retention, incident response and acceptance criteria are explicitly agreed. | Production boundary documented; requirements and ownership pending. |
| **F08-02 — Enterprise Identity, Tenant and Network Isolation** | P2 | F08-01, F05-04, F09-06 | Federation, revocation, tenant boundaries and the chosen private network topology pass cross-access and permission-change tests. | Synthetic identity boundaries exist; enterprise isolation unverified. |
| **F08-03 — Reliability, Scale and Recovery Objectives** | P2 | F08-01, F05-03, F07-03 | Agreed availability, latency, throughput, cost and recovery objectives are measured under load and faults, with tested alerts, backup and restoration ownership. | Lab limits exist; production objectives and exercises pending. |
| **F08-04 — Azure Portability After AWS Verification** | P2 | F07-03, F08-01 | After AWS verification, a separate Azure phase maps shared contracts and service differences and defines its own budget and equivalent acceptance tests. | Legacy contract-test adapter exists; deployed Azure edition out of scope. |

### EP-09 — Shared Factory for Multiple Companies

Share one AWS-hosted workflow while isolating each company's resources and enabling only explicitly governed joint projects. All six features are planned; see the [multi-company API architecture](../factory/multi-company-api-architecture.md).

| Feature | Priority | Dependencies | Measurable outcome | Current status |
|---|---|---|---|---|
| **F09-01 — Register companies and validate caller membership** | P0 | F03-02 | Verified human or service identities resolve server-side to an active company/project membership; forged company selectors, inactive memberships and unmapped identities are denied. | Planned; the prototype has two simulated scopes and no company membership registry. |
| **F09-02 — Keep company data, runs and results separate** | P0 | F09-01, F03-03, F04-01 | Company knowledge bases, source buckets and access roles are separate; scoped state, evidence, secrets, build contexts and artifact delivery deny cross-company reads, writes and connection substitution. | Planned; current synthetic tenant filters do not establish the proposed strong company boundary. |
| **F09-03 — Test shared use and blocked cross-company access** | P0 | F09-02, F03-04 | At least two companies use the same workflow with their own authorized data and results; tests reject other-company run/source/artifact access, forged membership and role/target substitution, with revision-specific evidence. | Planned; existing `alpha`/`beta` local tests are supporting evidence, not completion of multi-company acceptance. |
| **F09-04 — Expose stable company APIs for long-running jobs** | P1 | F09-02, F05-03 | Versioned OpenAPI request/response/error schemas and contract tests define company APIs; POST /v1/projects/{project_id}/runs durably accepts a job with 202, Location and scoped idempotency, while authorized status/cancellation survive retries and failures without duplicate untracked work. A generated client SDK can follow the same contract. | Planned; POST /api/runs already returns 202, but durable project APIs, idempotency and cancellation are not implemented. |
| **F09-05 — Grant and revoke access to joint projects** | P1 | F09-04, F05-04 | A resource owner grants a named recipient a specific resource, purpose, allowed operations and expiry; positive joint use succeeds, unrelated resources remain denied, and expiry/revocation blocks subsequent steps, reads, approvals and deliveries. | Planned; there is no collaboration workspace or resource-sharing grant in the current single-scope model. |
| **F09-06 — Bind each approval and release to its company** | P1 | F09-05, F05-02, F07-02 | G1 Scope, G2 Design, G3 Quality and G4 Release enforce eligible human approvers and exact version/hash/ETag; every release binds immutable company, project, target and configuration, rejecting stale or wrong-company decisions. | Planned; the current exact-artifact decision is not a company-specific four-gate release policy. |

## Incremental approach

1. Make the already-defined target application testable: one common application for three anonymised companies to consult synthetic affiliation records, with search, filters, effective dates and generation/approval/deployment tests. Keep existing prototype evidence separate from this target specification.
2. Qualify account access, models, region and spending controls, then prove the first real Bedrock call.
3. Deploy one authenticated vertical slice with enforced source access, three real roles, exact-artifact approval and inspectable cloud evidence.
4. Test success and meaningful failure paths, rehearse recovery, freeze versions and practise the demonstration in English and Dutch.
5. Expand into the complete Factory through explicit contracts, four human gates, isolated candidate execution, protected validation and exact-version release.
6. Address production commitments and the later Azure edition using their own acceptance evidence.

If a live AWS dependency remains blocked, keep the incomplete capability visible and show the local fallback as simulated; a mock run never substitutes for AWS proof.

## Future item policy

Do not populate detailed items in this version. After reviewing epics and features, decompose the next P0 increment first, using stable identifiers such as `I01-01-001` under one parent feature.

Each future item should state the observable change, owner, prerequisites, estimate, completion criteria, one success test, a meaningful failure test, expected evidence and tested revision/environment, cost/security effects, stop conditions and recovery path. Separate implementation, configuration, live verification, documentation and learning where acceptance or ownership differs. Files alone do not complete a feature.

Public README, engineering pages, slide exports and the Secloudis WordPress article with its GitHub link should reflect the demonstrated revision and be published after content review. Private planning records, credentials, source documents and client information must remain outside public material.

**Abbreviations:** AWS = Amazon Web Services; API = Application Programming Interface; CI = Continuous Integration; G = Gate; HTTPS = Hypertext Transfer Protocol Secure; MCP = Model Context Protocol; MFA = Multi-Factor Authentication; OIDC = OpenID Connect; S3 = Simple Storage Service; SDK = Software Development Kit.
