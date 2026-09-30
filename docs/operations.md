# Operating the demonstration

The local browser uses simulated identities and deterministic model responses.
The AWS mode requires Cognito, Bedrock, the knowledge base and S3 configuration.
The source tree and successful local tests are not evidence of a running AWS service.

## Before a demonstration

Check `/healthz`, then `/auth/config` and an authenticated `/api/me` call. A healthy
process alone does not prove that authentication or inference is configured.
Use a fresh synthetic request and verify that it reaches `waiting_approval`.
Open a source and confirm its tenant and version. Keep the tested image digest
and configuration recorded privately for rollback.

Do not deploy while demonstration runs are active. There are two worker slots per
process, one active run per principal and ten starts per principal per clock hour.
Seven model calls is the maximum for one successful correction loop; each SDK
call may retry according to its explicitly configured maximum attempts. These
limits reduce usage but do not impose a hard AWS billing cap.

## Diagnosing a failed run

Use the run identifier to correlate application events and OpenTelemetry spans.
The application omits prompt/document bodies from logs. The authorized result
store contains the evidence snapshot and final artifact.

| Observation | Check | Recovery |
|---|---|---|
| Login/configuration returns 503 | Exact Cognito issuer, pool, client, domain and HTTPS callback | Complete bootstrap configuration, then start sign-in again |
| Authentication returns 401 | Token signature, expiration, token use and client binding | Sign in again; never bypass verification |
| Access returns 403 or another user's run returns 404 | Cognito groups and server access policy | Correct the authorized group mapping; do not widen retrieval from the browser |
| Retrieval fails | KB identifier, ingestion status, tenant metadata and application role | Correct the metadata or role and repeat with a new run |
| Model call fails | Allowed model/profile, region, role, quota and timeout | Use the safe error type to inspect service configuration, then retry a new run |
| Reviewer rejects the proposal | Source support and correction feedback | Refine the synthetic request or supporting corpus; do not force approval |
| Approval returns 409 | Exact artifact hash, current state, concurrent decision | Reload the result; an already decided artifact cannot be approved again |
| Run becomes interrupted | Worker termination or expired 30-minute reservation | Inspect stored evidence and start a new run after its reservation expires |

An abrupt worker termination can retain its user's reservation for up to 30
minutes. The service does not automatically resume the old workflow. A late model
response cannot become an approvable artifact after lease loss. An older instance
cannot release a newer instance's reservation. Completed decisions remain in the
same state object, protected by conditional writes.

In local mode the storage lock is single-process only. In AWS, S3 conditional
writes provide the cross-instance compare-and-swap boundary. Neither design is a
general distributed workflow engine, and neither promises exactly-once writes to
an external business system.

## Cost and cleanup

Track model input/output tokens, Fargate task time, load balancer hours, public
IPv4 addresses, storage/vector operations, encryption keys and logging. Unknown
cost fields stay unknown. No model price is inferred from a name.

After the demonstration, review the actual AWS resources and charges. Follow the
deployment guide's teardown instructions. Artifact/corpus versioning and deletion
protection intentionally require a deliberate cleanup step. An expiry tag is a
review reminder, not an automatic deletion job.
