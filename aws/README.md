# Amazon Bedrock adapter

The AWS adapter calls Bedrock Converse using the standard AWS credential chain. Unit tests replace the network client with a local fake. A real AWS call and a deployment remain unverified until they have been executed successfully in an authorised account.

## Prerequisites

- Python 3.12 local environment with the `aws` package extra installed.
- An authorised account, role or AWS single sign-on (SSO) profile and AWS CLI for login and identity checks.
- A chosen region and a Converse-compatible model or inference profile accessible from that account.
- Permission to invoke only the chosen model/profile resources. An inference profile can require additional underlying model resources and regions.
- An agreed test budget. Per-call token and retry limits do not impose a global account spending cap.

The example region and profile are placeholders, not verified account settings. No credentials are stored in this project. The `environment.example` file is not loaded automatically.

```powershell
$env:AWS_PROFILE = 'aws-agent-platform-lab'
$env:AWS_REGION = 'eu-west-1'
$env:BEDROCK_MODEL_ID = '<authorised-model-or-inference-profile>'
$env:POC_TIMEOUT_SECONDS = '45'
$env:POC_MAX_ATTEMPTS = '2'
$env:POC_MAX_OUTPUT_TOKENS = '2048'
aws sso login --profile aws-agent-platform-lab
aws sts get-caller-identity --profile aws-agent-platform-lab
```

If workload credentials come from an AWS runtime role, leave `AWS_PROFILE` unset. Never add credentials or identity command output to Git.

## Explicit live inference

Run from the repository root after setup:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location).Path 'src')
.\.venv\Scripts\python.exe -m aws_agent_platform_lab.cli run --provider aws --scenario scenarios/demo.json --corpus corpus/knowledge.json --output demo_runs/aws_001
```

This sends the supplied synthetic request, selected synthetic reference documents and agent outputs to the configured model. It can incur inference charges. Do not replace the examples with personal, client or confidential content. A `synthetic: true` label does not anonymise data.

After a successful call, review the trace and artifact. Record the selected region, model, provider outcome and observed usage in a private test log. A local AWS inference call establishes model connectivity, not a deployed online service.

## Implemented bounds

- The SDK loads only for a real inference request.
- The default connection timeout is 10 seconds; the read timeout defaults to 45 seconds and is configurable from 1 to 120 seconds.
- The default is two total network attempts, configurable from one to three.
- Output defaults to 2,048 tokens, configurable from 128 to 4,096. Truncated responses are rejected.
- Provider errors omit remote response bodies and credential values.
- Model output is still untrusted and must pass schema and citation checks.
- The local human decision remains separate from the agent review.

The repository currently contains no deployed AWS infrastructure or operational AWS monitoring. See [the backlog](../docs/implementation-backlog.md).

## Official API references

- [Boto3 Bedrock Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html)
- [Botocore configuration](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)
