# AWS Agent Platform Lab

By **Yves Schillings, Secloudis** · [secloudis.com](https://secloudis.com/)

A hands-on AWS agent platform lab using synthetic data, Amazon Bedrock and controlled multi-agent workflows.

The project is intended as an open-source foundation that organisations can inspect, run and adapt. [Open-source reuse and enterprise value](docs/slides/25-open-source-reuse-and-enterprise-value.md) explains the reusable components, required adaptations and measurable outcomes. Licence selection and public release readiness remain to be confirmed; this is not a production-readiness or return-on-investment claim.

The delivery sequence is AWS first: deploy and verify this Bedrock implementation. An Azure variant is a separate later phase.

## Architecture deck and deployment documentation

![Multi-Agentic Workflow on AWS by Yves Schillings, Secloudis](docs/assets/slides/slide-01.png)

[PowerPoint](docs/presentation/Secloudis_Multi_Agentic_Workflow_on_AWS_v2.11.pptx) · [PDF](docs/presentation/Secloudis_Multi_Agentic_Workflow_on_AWS_v2.11.pdf)

The **Multi-Agentic Workflow on AWS** deck by Yves Schillings, Secloudis describes the **target Factory**: five worker roles, four human approval gates, isolated candidate execution and controlled release of a separate target application. The implementation status below remains the authority for what currently works. The target diagram is not a claim of a completed AWS deployment.

**[Global architecture: shared Factory, three companies and external organisations](docs/slides/26-one-factory-several-companies.md)**

[Company connections through MCP](docs/slides/27-company-apis-and-human-approvals.md) · [Python workflow](docs/slides/30-langgraph-workflow-in-python.md) · [Application APIs](docs/slides/31-shared-application-and-company-apis.md) · [Actors and responsibilities](docs/slides/32-actors-and-responsibilities.md) · [Business and delivery ecosystem](docs/slides/33-business-and-delivery-ecosystem.md) · [Business functions and hosting](docs/slides/34-business-functions-and-hosting.md) · [Technical exchange contracts](docs/slides/35-synthetic-affiliation-consultation-flow.md)

**[Keep the client, workflow and model separate: complete diagram](docs/slides/37-client-workflow-model-separation.md)**

[Conversational client options](docs/slides/38-conversational-client-options.md) · [Human approval across clients](docs/slides/39-human-approval-across-clients.md) · [Model hosting and data boundaries](docs/slides/40-model-hosting-and-data-boundaries.md) · [Conversational access delivery](docs/slides/41-conversational-access-delivery.md)

The four human checkpoints are **G1 Scope**, **G2 Design**, **G3 Quality** and **G4 Release**. **G means Gate**. Release approval authorises deployment of the exact reviewed version.

The [documentation portal](docs/README.md) connects all 41 slides to their explanation, deployment steps, code, prerequisites and required evidence. Slides 17–24 add the incremental delivery approach and [epic/feature backlog](docs/backlog/epics-features.md), retaining the complete Factory target; slide 25 explains open-source reuse and enterprise value, and slides 26–35 describe the proposed shared company platform, Python workflow, common application and human/software responsibilities. Slides 36–41 form a dedicated section on conversational access: the complete client/workflow/model diagram, client options, human approval, inference/data boundaries and delivery proof. Follow the [AWS runbook](docs/deployment.md) for the current deployment candidate; missing Factory components are identified before their deployment can be claimed.

| Slide | Architecture and deployment guide |
|---|---|
| 01 | [Multi-Agentic Workflow on AWS](docs/slides/01-ai-factory-on-aws.md) |
| 02 | [Target scope and current evidence](docs/slides/02-target-scope-and-current-evidence.md) |
| 03 | [Inside the Factory: logical architecture](docs/slides/03-logical-architecture.md) |
| 04 | [AWS deployment architecture](docs/slides/04-aws-deployment-architecture.md) |
| 05 | [Delivery workflow and four human gates](docs/slides/05-workflow-and-human-gates.md) |
| 06 | [Five Software Workers and Task Contracts](docs/slides/06-workers-and-task-contracts.md) |
| 07 | [Context, retrieval and source permissions](docs/slides/07-context-and-retrieval.md) |
| 08 | [Sandbox isolation and trusted validation](docs/slides/08-sandbox-and-validation.md) |
| 09 | [Run state, evidence and version binding](docs/slides/09-state-evidence-and-versions.md) |
| 10 | [Integration and migration risk controls](docs/slides/10-integration-and-migration-risks.md) |
| 11 | [Performance and data consistency controls](docs/slides/11-performance-and-data-consistency.md) |
| 12 | [AI risks and approval integrity](docs/slides/12-ai-risks-and-approval-integrity.md) |
| 13 | [Infrastructure provisioning and bootstrap](docs/slides/13-provisioning-and-bootstrap.md) |
| 14 | [Candidate build, approval and release](docs/slides/14-candidate-release.md) |
| 15 | [Operations, recovery and cost controls](docs/slides/15-operations-recovery-and-cost.md) |
| 16 | [Documentation and required proof](docs/slides/16-documentation-and-proof.md) |
| 17 | [Incremental delivery approach](docs/slides/17-incremental-delivery-approach.md) |
| 18 | [Epic roadmap](docs/slides/18-epic-roadmap.md) |
| 19 | [Foundation features](docs/slides/19-foundation-features.md) |
| 20 | [Live demonstration features](docs/slides/20-live-demo-features.md) |
| 21 | [Factory execution features](docs/slides/21-factory-execution-features.md) |
| 22 | [Release and production features](docs/slides/22-release-production-features.md) |
| 23 | [First AWS demo acceptance](docs/slides/23-first-aws-demo-acceptance.md) |
| 24 | [Backlog refinement and evidence](docs/slides/24-backlog-refinement-evidence.md) |
| 25 | [Open-source reuse and enterprise value](docs/slides/25-open-source-reuse-and-enterprise-value.md) |
| 26 | [Shared Factory and Business Connections](docs/slides/26-one-factory-several-companies.md) |
| 27 | [Company Connections through MCP](docs/slides/27-company-apis-and-human-approvals.md) |
| 28 | [AWS First, More Clouds Later](docs/slides/28-aws-first-more-clouds-later.md) |
| 29 | [Building the Shared Company Platform](docs/slides/29-building-the-shared-company-platform.md) |
| 30 | [LangGraph Workflow in Python](docs/slides/30-langgraph-workflow-in-python.md) |
| 31 | [Shared Application and Company APIs](docs/slides/31-shared-application-and-company-apis.md) |
| 32 | [Actors and Responsibilities](docs/slides/32-actors-and-responsibilities.md) |
| 33 | [Business and Delivery Ecosystem](docs/slides/33-business-and-delivery-ecosystem.md) |
| 34 | [Business Functions and Hosting](docs/slides/34-business-functions-and-hosting.md) |
| 35 | [Synthetic Affiliation Consultation Flow](docs/slides/35-synthetic-affiliation-consultation-flow.md) |
| 36 | [Conversational Access and Data Boundaries](docs/slides/36-conversational-access-and-data-boundaries.md) |
| 37 | [Keep the Client, Workflow and Model Separate](docs/slides/37-client-workflow-model-separation.md) |
| 38 | [Conversational Client Options](docs/slides/38-conversational-client-options.md) |
| 39 | [Human Approval across Clients](docs/slides/39-human-approval-across-clients.md) |
| 40 | [Model Hosting and Data Boundaries](docs/slides/40-model-hosting-and-data-boundaries.md) |
| 41 | [Conversational Access Delivery](docs/slides/41-conversational-access-delivery.md) |

The retained business case is one common read-only application for three anonymised companies to consult synthetic affiliation records, with search, filters, effective dates and owner-authorised business APIs. RAG supplies the Factory with documentary context. The [selected code-first target](docs/slides/30-langgraph-workflow-in-python.md) uses Python LangGraph, LangChain AWS `ChatBedrockConverse` and official MCP Python SDK connections to three company MCP servers. A local deterministic LangGraph increment now implements the five-role/four-gate sequence; real model-driven Factory work, remote company connections and the [generated application](docs/slides/31-shared-application-and-company-apis.md) remain to be built. That application will use company business APIs directly at runtime.

The three participating companies are distinct from External organisation A/B/C. The latter illustrate selective routing, reference and coverage contracts; they are not additional presumed Factory tenants or an exhaustive six-company requirement. AWS hosts the proposed Factory and Shared Business Platform; external/company system hosting is unverified. The technical flow specifies owner-registered grants, separate service identities, request/response schemas and denied/unavailable outcomes.

## Source publication evidence

- [Local verification and remaining cloud boundaries](docs/source-publication-verification.md).
- Code licence: [Apache 2.0](LICENSE). Diagram licence: [CC BY 4.0](docs/DIAGRAMS-LICENSE.md), with attribution to Yves Schillings, Secloudis.

## Reproducible RAG pipeline

- **RAG (Retrieval-Augmented Generation)**
  - Follow the [source-to-answer engineering guide](docs/rag-pipeline.md) for source fixtures, metadata, chunking, embeddings, filtered retrieval, model context and citations.
  - The implemented cloud adapter targets Bedrock Knowledge Bases with S3 Vectors; local mode uses lexical search.
  - The guide separates executable offline checks from the live ingestion and inference still to verify.

## Current implementation

**Local Factory increment:** a separate LangGraph workflow runs Analyst, Architect, Code Author, Tester and Reviewer, pausing at **G1 Scope, G2 Design, G3 Quality and G4 Release**. SQLite checkpoints retain gate pauses across restarts. Tests cover rejection, stale versions, replay, cross-owner access and concurrent decisions. All role outputs and identities are simulated: the proposed code is inert, proposed business tests are not executed, and G4 does not deploy anything. Correction/resubmission and cloud durability remain future work.

The `/factory` browser prototype is a temporary inspection harness. The conversational interface is still being selected; [Claude, Codex and Copilot Studio access](docs/conversational-access.md) describes the common MCP boundary and the human-approval requirements. MCP means Model Context Protocol. No connection to those clients or remote AWS Factory is claimed. See [development stages and preflight](docs/development-start.md).

**Preserved baseline:** the following application remains available independently at `/` and through its original command-line interface.

The lab now includes a FastAPI/browser application and a command-line workflow. An analyst, designer and reviewer run in sequence, with at most two correction rounds before an explicit human decision. Approval is bound to the SHA-256 hash of the exact artifact.

The local browser mode uses deterministic mock responses, a synthetic corpus, two simulated identities and a bounded stdio Model Context Protocol (MCP) checklist tool. Run/source access checks, exact-artifact decisions, persistence, safe traces and failure paths are exercised locally. The interface visibly labels simulated inference and identities.

The AWS code path includes Cognito access-token verification, server-filtered Bedrock Knowledge Bases retrieval, Bedrock Converse and S3 artifact storage with conditional writes. Terraform, a container definition and GitHub workflow files describe the deployment path. **A successful real Cognito login, Bedrock/Knowledge Bases call or AWS deployment remains to be verified in an authorised account.** Local tests and fake SDK transports do not establish those outcomes.

A legacy Azure adapter remains for provider-contract tests; the web service and deployment target AWS. See [the architecture](docs/architecture.md), [authentication boundary](docs/authentication.md) and [implementation backlog](docs/implementation-backlog.md).

## Run locally with Python 3.12

Windows PowerShell, from this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:LOCAL_DEMO_MODE = 'true'
.\.venv\Scripts\python.exe -m aws_agent_platform_lab.web
```

Open [the local browser interface](http://127.0.0.1:8000). It binds only to loopback in local mode. [The local demonstration guide](docs/local-demo.md) explains the two synthetic workspaces, source viewer, evidence and decisions. Generated state uses the ignored `.lab-data` directory. On macOS/Linux use `python3.12`, `.venv/bin/python` and `export LOCAL_DEMO_MODE=true` for the equivalent commands.

The optional [Factory inspection prototype](http://127.0.0.1:8000/factory) uses three separate simulated company identities and the same ignored data root. Factory routes are disabled outside local mode. These fixtures do not implement real company federation or cross-company sharing.

`requirements.txt` pins the dependency versions used for verification. The core CLI mock path itself uses only the standard library; the full browser and authentication tests require the installed dependencies.

## Command-line workflow

The CLI remains useful for inspecting the original local workflow directly:

```powershell
.\.venv\Scripts\python.exe -m aws_agent_platform_lab.cli run --provider mock --scenario scenarios/demo.json --corpus corpus/knowledge.json --output demo_runs/local_001
```

Each output directory must be new or empty. The run ends at `waiting_approval`. Inspect `demo_runs/local_001/artifact.json` before recording a decision:

```powershell
$runState = Get-Content -Raw 'demo_runs/local_001/state.json' | ConvertFrom-Json
.\.venv\Scripts\python.exe -m aws_agent_platform_lab.cli approve --run-dir demo_runs/local_001 --artifact-hash $runState.artifact_hash --decision approve
```

Use `--decision reject` to reject the proposal. A rejection never publishes. A wrong hash or a modified artifact blocks the action. This local command records an operator decision; it does not authenticate a human identity.

## Use Amazon Bedrock

Follow [the AWS setup notes](aws/README.md). Install the optional SDK only in the local environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[aws]'
```

Configure an authorised AWS role or profile, region and available Converse-compatible model. For the CLI, `--provider aws` invokes Bedrock. For the web service, absent/false `LOCAL_DEMO_MODE` selects the AWS path and requires the configured identity, retrieval, model and storage services. Those operations can incur charges. Keep credentials outside the repository and keep the supplied examples synthetic.

## What the workflow proves

1. **Retrieval:** local browser retrieval applies identity scope before lexical ranking. AWS retrieval sends a server-owned tenant/access filter to Knowledge Bases and checks returned source metadata again. That SDK boundary is tested with fake responses; a live vector index remains unverified. The original CLI corpus flags are declarations, not identity controls or anonymisation.
2. **Analysis and design:** agents produce structured JSON. Required fields and cited source identifiers are validated.
3. **Review and correction:** the reviewer can request changes. Two corrections after the first draft give at most seven agent calls. Distinct roles do not guarantee independent judgement or truth.
4. **Human decision:** a favourable reviewer result pauses the run. It never authorises publication by itself.
5. **Publication:** the operator can approve the exact hash. The browser service stores the decision and publication state atomically with the artifact; the CLI copies to its fixed `published/approved_workflow.json` path. Model text is never executed as code, a shell command or a chosen output path.

Citation checks establish that identifiers refer to retrieved documents; they do not prove that every claim is supported semantically. Local files are not a tamper-proof audit store. The browser service bounds concurrent work and uses versioned state, but does not claim automatic recovery of interrupted execution or production multi-tenant operation.

## Files to inspect after a CLI run

| File | Purpose |
|---|---|
| `input_snapshot.json` | Synthetic request and retrieved documents |
| `analyst.00.json`, `designer.00.json`, `reviewer.00.json` | Validated agent outputs; corrections use later revision numbers |
| `artifact.json` | Final proposal and its evidence |
| `state.0001.json` and later snapshots | Numbered local state history |
| `state.json` | Most recent state |
| `trace.jsonl` | Roles, events, revisions, latency, hashes and available usage data |
| `human_decision.json` | Explicit local decision and the exact artifact hash |
| `published/approved_workflow.json` | Approved local result |

Unknown cloud cost is `null`, not zero. The mock provider reports simulated zero usage. Generated runs, secrets, environments and Terraform state are ignored by Git.

## Next steps

The [proposed AWS architecture](docs/architecture.md) uses ECS Express Mode on Fargate for a FastAPI/browser container, Cognito verified by the API, Bedrock Converse, Bedrock Knowledge Bases backed by S3 Vectors, a local stdio MCP tool, ordinary S3 artifacts and CloudWatch logs with OpenTelemetry instrumentation. Cloud resources remain to be deployed and validated.

The [epic and feature backlog](docs/backlog/epics-features.md) organises the proposed delivery sequence into nine epics and 35 features; detailed items are not yet expanded. The existing [LAB technical issue specifications](docs/implementation-backlog.md) retain implementation acceptance detail and recorded evidence for Terraform, GitHub Actions with OpenID Connect, runbooks and the English/Dutch demonstration. These are complementary planning levels, not duplicate published GitHub issues; existing LAB identifiers remain unchanged.

The [staged delivery plan](docs/four-day-plan.md) progresses from account readiness to the first verified AWS demonstration through Stage 1–4. It distinguishes implemented evidence from planned platform capabilities. No remote repository or cloud resources are created by this source tree.

Follow the [deployment guide](docs/deployment.md), [operating runbook](docs/operations.md)
and [rollback procedure](docs/rollback.md) for the AWS stage. Practise the
[English and Dutch demonstration script](docs/demo-script-en-nl.md) using only
claims supported by the run and environment actually shown.
