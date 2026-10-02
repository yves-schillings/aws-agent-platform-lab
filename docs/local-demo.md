# Run the browser demonstration locally

The local browser mode uses deterministic mock model responses and two simulated identities. It does not contact Bedrock or establish cloud authentication. The header labels this mode explicitly.

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
$env:LOCAL_DEMO_MODE = 'true'
.\.venv\Scripts\python.exe -m aws_agent_platform_lab.web
```

Open [the local interface](http://127.0.0.1:8000). The process binds only to `127.0.0.1` in this mode and rejects remote peers and unexpected Host names. `LOCAL_DEMO_MODE` must be exactly `true` or `false` (case insensitive). A different non-empty value is a configuration error.

## Demonstration journey

1. Keep the `alpha` workspace or select `beta`. The user selector represents a simulated identity, not a login.
2. Read the synthetic request, choose English or Dutch and confirm that the input is synthetic.
3. Start the workflow. Follow the analyst, designer and reviewer.
4. Open the source evidence and inspect the complete artifact. Source contents are fetched through an authorised source-viewer endpoint.
5. Read the artifact SHA-256 hash. Tick the review checkbox and approve that exact version, or reject it.
6. Inspect the trace and outcome. Change to the other simulated identity: the server must not disclose the first user's run or its documents.

The API's source and run checks are real application checks over synthetic identity fixtures. They do not prove enterprise identity federation. The mock provider's wording does not evaluate semantic answer quality or prove bilingual model performance. A Dutch request still requires a real-model evaluation for that claim.

Generated runs are stored in the ignored `.lab-data` directory by default. `LAB_DATA_DIR` can select another local data directory. Keep source files and generated evidence separate. The web API limits a request to 4,000 characters and accepts only the documented fields; users cannot submit a model URL, tool executable or source access filter.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Authentication tests use newly generated test signing keys and no remote identity provider. HTTP tests exercise the actual local service with a deterministic tool double, including rejected access, wrong hashes, replayed decisions and incomplete cloud configuration. Separate tool integration checks must establish that the real stdio MCP transport works.

## Health and bootstrap

`GET /healthz` reports that the process is alive. It is deliberately not a claim of authenticated model connectivity or complete AWS readiness. Cloud authentication and run endpoints stay closed when required settings are missing, while health remains available for the two-stage deployment bootstrap.

To stop, interrupt the terminal process. To start AWS mode, unset `LOCAL_DEMO_MODE` or set it to `false`, then complete the settings described in [authentication](authentication.md) and the deployment documentation. Never expose the simulated mode to a network.
