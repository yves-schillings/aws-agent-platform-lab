# Independent review brief: local Factory increment

Use this brief for an independent Claude review when the user explicitly requests the review to run. Preparing the brief does not send code, invoke a paid model or authorise external sharing. Share only approved repository material; exclude credentials, Terraform state/plans, private source documents, real institution names and private presentation files.

## Reviewer role

Review the exact submitted revision and diff. Look for incorrect behavior, broken boundaries, misleading evidence and missing tests. Do not treat an architecture diagram, passing mock tests or an approval label as proof of cloud execution. Return reproducible findings with file/line, trigger, consequence, severity and the smallest meaningful test. Clearly distinguish confirmed defects, open questions and optional improvements.

The reviewer is independent of the five application software workers. Those workers prepare proposals and evidence; they cannot give themselves data access or approve their own gates. Claude's review is advisory. The designated human owner makes each G1 Scope, G2 Design, G3 Quality and G4 Release decision, and a human retains the final deployment decision.

**Interface choice remains pending.** `/factory` is a prototype/test harness, not the committed final user interface. A Claude or Copilot conversational client may later connect to the common backend through an authenticated MCP/API adapter. Distinguish that client from Claude used as a Bedrock inference model, and from Claude Code performing this independent source review. No client connection or model invocation is performed by preparing this brief.

## Scope and files

| Area | Files to inspect | Boundary to examine |
|---|---|---|
| New Factory orchestration | `src/aws_agent_platform_lab/factory.py` and Factory tests in `tests/` | Five deterministic workers, explicit LangGraph routes, four named gates, revision/hash binding, terminal rejection and restart behavior; later correction routing must not be claimed as implemented |
| Web integration | `src/aws_agent_platform_lab/web.py`, `auth.py`, Factory browser files under `src/aws_agent_platform_lab/static/`, `tests/test_web.py` and new Factory web tests | Prototype `/factory` and `/api/factory/runs`, owner derivation, input allowlists, local-only access and preservation of baseline endpoints; final client selection is pending |
| Local persistence | Factory SQLite implementation and restart tests | Atomic state/decision changes, concurrency, stale decisions, replay handling and explicit local-only limitations |
| Existing baseline | `services.py`, `workflow.py`, `storage.py`, `providers.py`, `retrieval.py`, `mcp_tool.py` | Existing three-role/one-decision functionality remains usable; no silent claim that it is the full target Factory |
| Prerequisites | `scripts/preflight.py`, `tests/test_preflight.py` | Offline default, opt-in STS only, timeout/missing-tool classification, output redaction and no automatic mutation |
| Deployment context | `infra/`, `Dockerfile`, `requirements.txt`, `.github/workflows/`, `scripts/deploy_express.py`, `scripts/rollback_express.py` | Current platform deployment is distinct from generated-application release; no new deployment authority is accidentally introduced |
| Claims and instructions | `AGENTS.md`, `docs/development-start.md`, `docs/deployment.md` | Claims match exact observed evidence, with source names/secrets excluded from public material |

Confirm the actual new filenames from the submitted diff rather than assuming every planned file has already been implemented. The pre-increment audit at commit `86ac8aa` recorded 78 application tests and 8 deployment-script tests. The submitted increment must include its own exact revision, dependency changes and test results.

## Questions the review must answer

1. Does the graph actually execute the five intended role stages and pause at **G1 Scope**, **G2 Design**, **G3 Quality** and **G4 Release**, in order? Can an omitted, rejected or stale gate be bypassed by another API call or crafted state?
2. Is run ownership established by verified server-side identity, with local fixtures clearly simulated? Can a caller choose another owner through request fields, path IDs, connection identifiers or stored state?
3. Does each decision apply only to the displayed artifact/revision and the appropriate gate? What happens when two decisions race, an old hash is reused, a request repeats, or the process stops between checkpoint and approval?
4. If a LangGraph node can rerun after a pause or recovery, are its writes idempotent? Are SQLite access, transactions and connection lifetimes appropriate for the actual concurrency model? Does reopening the process recover the intended state without silently repeating work?
5. Are generated proposals inert? Is there any execution path into `exec`, `eval`, a shell, Docker, package installation, filesystem paths chosen by model content, arbitrary tool URLs or deployment APIs? A textual code proposal must not become executable through a preview or review action.
6. Is deterministic Tester/Reviewer output accurately labelled? Their opinions do not establish independently executed trusted tests, sandbox isolation or a working generated application.
7. Do the Factory endpoints stay unavailable in cloud mode until their real authentication/persistence design is implemented? Do local bindings, Host checks, source scopes, browser rendering, request-size limits and input validation preserve the existing protections?
8. Does the preflight avoid AWS calls by default, skip remote Docker engines, keep credentials/raw diagnostics out of reports, and refuse to report readiness after timeouts, missing tools or malformed successful responses?
9. Are dependencies pinned and tested on the supported runtime? Does the existing offline suite still pass? Are new tests behavior-focused and capable of failing for a real skipped gate, wrong owner, replay or restart defect?
10. Can a reader distinguish implemented local behavior, infrastructure definitions, proposed AWS components and verified live results? Is local G4 approval clearly separate from an actual protected cloud release?
11. If a conversational client is proposed, can it start/read a run without receiving a tool or credential that approves G1–G4? Do not equate a chat confirmation or a model-authored approval payload with an authenticated human decision. Review the proposed separate human-approval surface, gate-role policy, exact-version/destination binding and one-time receipt verification. The current local fixture header and shared owner decision endpoint must not be exposed through that adapter.

## Reproduction and response

Use the project's virtual environment and synthetic data. Do not log in, call models, install dependencies, start a container, push code or deploy merely to review this brief. When authorised tooling is already available, the intended local checks are:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p deploy_test.py -v
.\.venv\Scripts\python.exe scripts/preflight.py --json
```

Report which checks actually ran and their revision. A blocked Docker check or skipped AWS identity check is useful evidence, not a reason to invent a passing result. For each material finding, provide the smallest reproduction and an acceptance test. If no defects are found, state the remaining unverified boundaries explicitly. The author resolves findings, reruns the affected checks and presents the concrete result for human review.
