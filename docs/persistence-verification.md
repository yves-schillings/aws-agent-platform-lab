# Restart and storage verification

Verification performed on 30 September 2026 with Python 3.12 and the pinned local dependencies.

## Executed evidence

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_persistence_restart.py -v
```

Result: **1 process-restart integration test passed in 13.079 seconds**. The test launches its own HTTP process on an operating-system-selected loopback port, uses an isolated temporary data directory, and terminates only that process. It does not interact with another running demonstration. Inference uses deterministic mock responses; the stdio MCP tool is real and local. No AWS credentials or remote cloud services are used.

The test completed two workflows, approved one and rejected the other, stopped the server process and started a fresh process against the same stored files. It verified:

- Both final statuses, publication flags, complete artifacts and decision records survived process memory loss unchanged.
- The artifact SHA-256 still matched the artifact bytes and the exact hash recorded in the decision.
- Source identifiers, versions, text, permission metadata and tool evidence survived unchanged; the authorised source viewer returned the same source objects.
- The other tenant received `404` for both run and source reads after restart.
- A fresh service rejected another subject in the same tenant, independently of the cross-tenant check.
- Repeating either approval or rejection against either completed run returned `409`.
- The persisted state bytes remained unchanged after those rejected replay attempts, with exactly one human-decision trace entry per run.

The original service tests already covered re-opening approved state through another service object. The new integration test adds actual process loss, rejected-state durability, source provenance and post-restart ownership/replay checks.

## Interrupted-run boundary

Completed-decision persistence does not establish recovery of a workflow that was still executing when its worker died. The current code uses a fixed **1,800-second lease** from the start of the run.

- If a process disappears before its cleanup runs, the remaining lease continues to block a new run for that user until its original expiry. It is not a new 30-minute timer started by the restart.
- Before expiry, the persisted `queued` or `running` status can remain visible even though the old worker has disappeared.
- After expiry, reads present the unfinished run as `interrupted`; no automatic resume is attempted. That read projection does not rewrite the original stored active status.
- A late worker cannot turn an expired run into an approvable artifact or release a newer worker's lease. Separate time-controlled regression tests in `test_services.py` cover those cases.
- `close()` waits for worker threads. Abrupt container termination can therefore leave a lease until expiry if a network call outlasts the container's shutdown window.

These timings were established from the lease implementation and the time-controlled regression tests; this verification did **not** wait 30 wall-clock minutes or demonstrate durable restart of interrupted execution. Avoid deployment changes during active demonstration runs.

## Scope of the result

This verifies the local filesystem-backed store across separate Python processes using the **same data directory**. It does not establish persistence after deleting that directory, moving to another machine, or replacing an ephemeral container filesystem. The AWS path uses a separate S3 store with conditional writes. Actual S3 connectivity, cloud-task replacement and cloud permissions still require verification in the authorised AWS environment.

The local store remains single-process storage. The test stops the first HTTP process before starting the second; it does not claim that two simultaneous local processes provide a distributed lock.
