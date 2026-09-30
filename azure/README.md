# Legacy comparison adapter

The Azure OpenAI adapter is retained to preserve the existing provider-contract tests and illustrate the boundary between orchestration and model access. The active roadmap targets AWS and Amazon Bedrock.

This adapter has offline tests with fake HTTP responses. No successful live Azure request or deployment is claimed. No Azure SDK is required because the adapter uses Python's standard HTTPS library.

The placeholder-only `environment.example` lists the configuration contract. It is not loaded automatically. A live run requires an authorised endpoint and deployment, plus exactly one of `AZURE_OPENAI_API_KEY` or `AZURE_OPENAI_AD_TOKEN` supplied outside the repository. Selecting `--provider azure` can incur charges. The lab does not automatically refresh an externally supplied token.

The normal mock and AWS instructions are in [the root README](../README.md). No Azure infrastructure is part of the four-day AWS delivery plan.
