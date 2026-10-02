# Staged delivery plan

**Target:** the first repeatable, verified AWS deployment of the workflow. Progress through Stage 1–4 when each stage's evidence is available. Account/model availability and GitHub access are external dependencies to resolve first; these stages do not imply a calendar commitment.

| Stage | Main work | Evidence required to complete the stage |
|---|---|---|
| Stage 1 — Baseline and readiness | Explain the current workflow; establish GitHub and AWS identity; run the offline tests and a real Bedrock request; confirm the synthetic scenario; build a FastAPI/UI container with a health endpoint | Green offline tests, a recorded real Bedrock result, one concrete scenario and a runnable container |
| Stage 2 — Authenticated live slice | Deploy protected HTTPS UI/API on ECS Express Mode/Fargate; verify Cognito identities in the API; ingest S3 synthetic documents into Bedrock Knowledge Bases/S3 Vectors; enforce source/run permissions | Online request-to-result journey, visible sources, two identities and denied-access tests |
| Stage 3 — Evidence and recovery | Add one stdio MCP tool, bounded agent loop, S3 evidence, CloudWatch logs and OpenTelemetry instrumentation; complete Terraform and GitHub Actions/OIDC; rehearse rollback | Controlled agent journey, traceable decisions, model failure path and reproducible deployment |
| Stage 4 — Evaluation and release readiness | Freeze versions; run evaluation and failure cases, including English and Dutch synthetic requests; fix defects; verify the service URL, repository and offline fallback | Evidence table, concise runbook, preserved live cloud trace, repeatable verification and explicit remaining-work list |

## Working rhythm for each increment

1. Explain the requirement and the component in plain language.
2. Implement a small observable step.
3. Verify success and one meaningful failure path.
4. Record what is implemented, what has actually run and what remains planned.

## Dependencies to resolve first

- GitHub owner, repository visibility and authentication. No remote repository is presumed to exist.
- An authorised AWS account/role, selected region, accessible Bedrock model and test spending limit.
- A working container engine or an agreed remote build method.
- Confirm availability of the proposed ECS Express Mode/Fargate, Cognito, Bedrock and S3 Vectors combination in the selected region and account.

## Scope protection

The minimum live deployment is an authenticated browser journey using Bedrock, synthetic sources, enforced source access, a visible review/correction loop, an exact-version human decision and inspectable traces. Vector retrieval, MCP and automatic cloud delivery each need their own evidence. If one is not yet verified, retain it as a clearly marked backlog item rather than claiming it works.

If AWS access is delayed, continue the API, interface, offline tests, permission controls and infrastructure definition locally. Keep the mock provider clearly labelled. A live AWS result still requires a real deployment; a local mock fallback does not replace that evidence.

No production data, client correspondence, CV, presentation deck or cloud credential belongs in this repository.
