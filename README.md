# AWS Agent Platform Lab

By **Yves Schillings, Secloudis** · [secloudis.com](https://secloudis.com/)

A hands-on AWS agent platform lab using synthetic data, Amazon Bedrock and controlled multi-agent workflows.

The delivery sequence is AWS first: deploy and verify this Bedrock implementation. An Azure variant is a separate later phase.

## Architecture deck and deployment documentation

![Multi-Agentic Workflow on AWS by Yves Schillings, Secloudis](docs/assets/slides/slide-01.png)

[PowerPoint](docs/presentation/Secloudis_Multi_Agentic_Workflow_on_AWS_v2.1.pptx) · [PDF](docs/presentation/Secloudis_Multi_Agentic_Workflow_on_AWS_v2.1.pdf)

The **Multi-Agentic Workflow on AWS** deck by Yves Schillings, Secloudis describes the **target Factory**: five worker roles, four human approval gates, isolated candidate execution and controlled release of a separate target application. The implementation status below remains the authority for what currently works. The target diagram is not a claim of a completed AWS deployment.

The four human checkpoints are **G1 Scope**, **G2 Design**, **G3 Quality** and **G4 Release**. **G means Gate**. Release approval authorises deployment of the exact reviewed version.

The [documentation portal](docs/README.md) connects each slide to its explanation, deployment steps, code, prerequisites and required evidence. Follow the [AWS runbook](docs/deployment.md) for the current deployment candidate; missing Factory components are identified before their deployment can be claimed.

| Slide | Architecture and deployment guide |
|---|---|
| 01 | [Multi-Agentic Workflow on AWS](docs/slides/01-ai-factory-on-aws.md) |
| 02 | [Target scope and current evidence](docs/slides/02-target-scope-and-current-evidence.md) |
| 03 | [Inside the Factory: logical architecture](docs/slides/03-logical-architecture.md) |
| 04 | [AWS deployment architecture](docs/slides/04-aws-deployment-architecture.md) |
| 05 | [Delivery workflow and four human gates](docs/slides/05-workflow-and-human-gates.md) |
| 06 | [Five workers and task contracts](docs/slides/06-workers-and-task-contracts.md) |
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

## Current implementation

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

The [GitHub issue backlog](docs/implementation-backlog.md) defines acceptance criteria for that implementation, Terraform, GitHub Actions with OpenID Connect, operating runbooks and an English/Dutch demonstration.

The [four-day plan](docs/four-day-plan.md) prioritises a repeatable demonstration by Monday 5 October 2026. It distinguishes implemented evidence from planned platform capabilities. No remote repository or cloud resources are created by this source tree.

Follow the [deployment guide](docs/deployment.md), [operating runbook](docs/operations.md)
and [rollback procedure](docs/rollback.md) for the AWS stage. Practise the
[English and Dutch demonstration script](docs/demo-script-en-nl.md) using only
claims supported by the run and environment actually shown.
