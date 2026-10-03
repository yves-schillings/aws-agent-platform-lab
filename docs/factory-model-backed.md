# Model-backed Factory and Cognito access (MVP increment)

This increment turns the five-role Factory from fixed examples into model calls, and lets Cognito-authenticated users reach it on AWS. Five-company federation, the candidate sandbox, the generated application and remote MCP stay out of scope.

## Modes

| Setting | Effect |
| --- | --- |
| `FACTORY_PROVIDER` unset or `fixtures` | Unchanged behaviour: the five roles return fixed examples. |
| `FACTORY_PROVIDER=mock` | Roles call the local mock model: offline end-to-end checks. |
| `FACTORY_PROVIDER=aws` | Roles call Bedrock Converse directly through `AwsBedrockProvider`; with `BEDROCK_KNOWLEDGE_BASE_ID` set, documents come from Bedrock Knowledge Bases. |
| `FACTORY_PROVIDER=aws-langchain` | Roles call the same Bedrock model through `LangChainBedrockProvider` and `ChatBedrockConverse`; retrieval remains the same scoped Knowledge Base path. |
| `FACTORY_ENABLED=true` (AWS mode) | Exposes `/api/factory/*` to Cognito-verified users. Without it the routes return 404. |

Terraform: `enable_factory = true` sets `FACTORY_ENABLED=true`, `FACTORY_PROVIDER=aws-langchain` and `LAB_DATA_DIR=/app/artifacts/lab-data` (the container's writable directory). Set `factory_provider = "aws"` only when the direct Boto3 adapter is intentionally selected. Default is `false`.

## How one role call works

1. `start_run` resolves the caller's company scope from the verified identity and retrieves at most five permitted documents. A caller without permitted documents gets 422 before any model call.
2. Each LangGraph role node builds a JSON prompt: role task, rules, the role's `response_schema`, the request, the permitted documents and the earlier roles' proposals (the Reviewer also receives the candidate files and test cases).
3. The rules state that request, document and earlier-role text is untrusted data, that only supplied document IDs may be cited, and that nothing proposed is executed.
4. `validate_model_output` keeps an answer only if its fields match the role schema exactly, its citations name supplied documents, proposed file paths stay inside the candidate, and a reviewer approval leaves no unresolved issues.
5. A provider error or invalid answer sets the run to `failed` without reaching a gate; only the error type is stored.
6. Validated proposals stay inert data. The Factory never builds, executes or deploys proposed code.

## Identities

- Local mode accepts only the three fixture identities; a principal marked as verified is refused (403).
- AWS mode (`verified_identities=True`, set by `service_from_environment` when `LOCAL_DEMO_MODE` is not `true`) accepts Cognito-verified principals whose token groups map to a known company. Gate decisions record `identity_verified: true`.
- A Cognito-authenticated gate approver must be a separate identity from the run owner and must hold the matching `factory-g1-approver`, `factory-g2-approver`, `factory-g3-approver` or `factory-g4-approver` group. The server checks both the company scope and that exact gate group before it resumes LangGraph. Local fixtures retain a single-user approval harness for offline tests.

## Known MVP limits

- **Local persistence:** offline development uses SQLite checkpoints.
- **AWS persistence:** the configured Factory uses shared DynamoDB checkpoints and a run registry for ownership and per-run leases. Both Fargate tasks can access the same waiting run. Live recovery and concurrent-decision behavior still require retained acceptance evidence.
  The lease is renewed every 15 seconds during a 45-second ownership window.
  Each checkpoint write includes an atomic condition that the operation still
  owns an unexpired lease. A displaced task cannot write with its old token.
  `factory_persistence.py` owns this logic; the LangGraph saver is cloned per
  operation, without changing the shared saver's client. The application role
  needs `dynamodb:ConditionCheckItem` on the runs table in addition to checkpoint
  writes. This does not guarantee exactly-once inference or solve HTTP timeouts.
- **Browser access:** `/factory` supports both local mode and enabled AWS mode. AWS requests use Cognito authentication. Page availability does not establish successful sign-in or model execution.
- Choose `aws` for the direct Boto3 Converse adapter or `aws-langchain` for `ChatBedrockConverse`. Both use the configured AWS region, model, profile and bounded timeout settings.

## Tests

`tests/test_factory_model.py` covers: five model-backed roles through four gates, per-company document isolation, refusal before any model call, invalid JSON, out-of-scope citations, sanitized provider errors, unsafe file paths, reviewer approvals with open issues, environment selection, and the Cognito HTTP path (valid token, missing or forged token, cross-user isolation, run-owner denial, wrong-gate-approver denial, and routes disabled unless enabled).

Install `requirements-test.txt` for the offline suite. `test_factory_persistence.py`
uses Moto to emulate DynamoDB conditions and the pinned AWS LangGraph saver.
It checks renewal beyond the initial expiry, ownership replacement, expiry,
renewal failure, and requester/approver resumption on two service instances.
These emulator tests do not replace a live ECS task-replacement exercise.
