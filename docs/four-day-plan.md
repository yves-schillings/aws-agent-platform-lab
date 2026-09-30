# Four-day delivery plan

**Target:** a repeatable AWS demonstration for Monday 5 October 2026, with a presenter who can explain the implementation. This plan assumes full-time work from Thursday 1 to Sunday 4 October. Account/model availability and GitHub access are external dependencies to resolve first.

| Day | Main work | Evidence to finish the day |
|---|---|---|
| Thursday 1 October | Explain the current workflow; establish GitHub and AWS identity; run the offline tests and a real Bedrock request; confirm the synthetic scenario; build a FastAPI/UI container with a health endpoint | Green offline tests, a recorded real Bedrock result, one concrete scenario and a runnable container |
| Friday 2 October | Deploy protected HTTPS UI/API on ECS Express Mode/Fargate; verify Cognito identities in the API; ingest S3 synthetic documents into Bedrock Knowledge Bases/S3 Vectors; enforce source/run permissions | Online request-to-result journey, visible sources, two identities and denied-access tests |
| Saturday 3 October | Add one stdio MCP tool, bounded agent loop, S3 evidence, CloudWatch logs and OpenTelemetry instrumentation; complete Terraform and GitHub Actions/OIDC; rehearse rollback | Controlled agent journey, traceable decisions, model failure path and reproducible deployment |
| Sunday 4 October | Freeze versions; run evaluation and failure cases; fix defects; verify the demo URL and repository; rehearse English and Dutch explanations and the offline fallback | Evidence table, concise runbook, preserved live cloud trace, repeatable demo and explicit remaining-work list |

## Daily working rhythm

1. Explain the requirement and the component in plain language.
2. Implement a small observable step.
3. Verify success and one meaningful failure path.
4. Ask the presenter to explain the result in their own words.
5. Record what is implemented, what has actually run and what remains planned.

## Dependencies to resolve first

- GitHub owner, repository visibility and authentication. No remote repository is presumed to exist.
- An authorised AWS account/role, selected region, accessible Bedrock model and test spending limit.
- A working container engine or an agreed remote build method.
- Confirm availability of the proposed ECS Express Mode/Fargate, Cognito, Bedrock and S3 Vectors combination in the selected region and account.

## Scope protection

The minimum live demonstration is an authenticated browser journey using Bedrock, synthetic sources, enforced source access, a visible review/correction loop, an exact-version human decision and inspectable traces. Vector retrieval, MCP and automatic cloud delivery each need their own evidence. If one cannot be completed safely in the available time, retain it as a clearly marked backlog item rather than claiming it works.

If AWS access is delayed, continue the API, interface, offline tests, permission controls and infrastructure definition locally. Keep the mock provider clearly labelled. An online AWS demonstration still requires a real deployment; a local mock fallback does not replace that evidence.

No production data, client correspondence, CV, presentation deck or cloud credential belongs in this repository.
