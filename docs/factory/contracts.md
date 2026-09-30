# Target factory contracts

**Gate key:** G means Gate, a human approval checkpoint: G1 Scope, G2 Design, G3 Quality, G4 Release. Release authorises deployment of the exact reviewed version.

**Status: target dependency.** These are engineering contracts for the five-worker/four-gate architecture. The current application does not accept these envelopes, dispatch five workers, execute generated code or release candidate applications.

## TaskRequest and TaskResult

A controller owns routing and issues a bounded task. A worker may return a proposal or evidence; it cannot widen its source scope, select a deployment identity or mark a human gate passed.

| Envelope | Required fields and constraints |
|---|---|
| `TaskRequest` | Unique `task_id`, `run_id`, worker role, tenant/access scope derived from verified identity, exact input artifact hashes/source versions, output schema, allowed tool names, deadline, maximum calls/tokens and approved model policy. |
| `TaskResult` | Same task/run/role, terminal outcome, exact output artifact hashes, cited input/source IDs, safe error type, observed usage, tool evidence, test results where applicable, and the policy/model configuration used. |
| Controller checks | Issued task exists and is current; response role/scope matches; deadline/lease remains valid; hashes resolve; schema and references pass; budgets cannot be increased by worker text. |
| Failure behavior | Invalid, expired or conflicting output is recorded and rejected. Bounded correction can create a new task version. Budget exhaustion, failed controls or missing evidence stops or escalates to the designated owner. |

The existing [model validators](../../src/aws_agent_platform_lab/models.py), [workflow roles](../../src/aws_agent_platform_lab/workflow.py) and [service lease checks](../../src/aws_agent_platform_lab/services.py) are reusable boundary mechanisms. They are not this complete envelope implementation.

## Worker boundaries

| Worker | Consumes | Produces | Must not grant itself |
|---|---|---|---|
| Analyst | Approved intake scope and permitted source snapshots | Requirements, assumptions, acceptance criteria and source citations | Access to another tenant or G1 approval |
| Architect | G1-bound requirements and constraints | Component/interface design, trust boundaries, migration plan and risk controls | G2 approval or runtime permissions |
| Code author | G2-bound design, task contract and approved repository snapshot | Candidate diff/commit and dependency manifest | Merge, trusted test editing or production credentials |
| Tester | Candidate commit and controlled acceptance criteria | Proposed tests and observed sandbox results | Authority to redefine protected tests or suppress failed evidence |
| Reviewer | Candidate, independent test results, provenance and risk register | Findings, correction requests and readiness recommendation | G3/G4 approval or deployment authority |

The trusted validation runner executes protected tests and policy checks under separate control. A Tester worker can propose test cases, but its own generated report is not equivalent to trusted execution evidence.

## Artifact and candidate manifest

Target evidence binds the complete reviewable candidate, not only a prose answer. A manifest needs: source commit SHA, repository identity, build/image digest, dependency-lock hash, input/source IDs and versions, requirement/design hashes, model/prompt policy identifiers, trusted test/report hashes, sandbox configuration, risk exceptions, artifact hash and parent lineage. Store generated source, execution evidence and release decisions separately with explicit read/write roles.

Changing code, dependencies, source scope, design, trusted tests or a material runtime configuration creates a new candidate manifest. The controller must invalidate affected gate decisions instead of reusing an old approval against new bytes. No manifest/signature implementation is claimed in the current repository.

## Four authenticated gate decisions

| Gate | Owner role to assign | Reviewed object | Required result |
|---|---|---|---|
| G1 scope | Business/source owner | Requirements, scope and source permissions | Accept or reject exact scope; unresolved assumptions recorded |
| G2 design | Architecture/security owner | Design, interfaces, trust boundaries and risk treatment | Accept or request a revised design |
| G3 quality | Independent quality owner | Candidate manifest plus trusted test/security/performance evidence | Accept only the exact tested candidate, or return findings |
| G4 release | Named release authority | G3 candidate, deployment target/configuration and rollback plan | Authorise the exact release or refuse it |

Every decision needs verified actor identity, role authorisation, gate ID, artifact/manifest hash, decision, timestamp and reason/reference. A cryptographic evidence signature, if required, needs its own controlled signing key and verification policy; the existing hash-bound local/browser decision is not that signing service. Concurrent or stale decisions must fail a conditional state update.

## External writes and migrations

Define idempotency keys, expected source/target versions, transaction or compensation boundaries, reconciliation rules, retry limits and owner authority before integrating a writable business tool. A JSON state compare-and-swap does not make an external API or multi-record migration exactly once. The baseline's read-only checklist and synthetic artifact publication do not exercise these contracts.
