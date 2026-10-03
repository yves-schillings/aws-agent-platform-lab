# Connect the AWS Python application to Microsoft Foundry

- **Implemented adapter:** [`AzureOpenAIProvider`](../src/aws_agent_platform_lab/providers.py) implements `generate(role, prompt)` in `providers.py` using Python's `urllib.request`. No Azure SDK or LangChain Azure adapter is required for this implementation.
- **Destination:** a model deployment supporting Azure OpenAI Chat Completions. This adapter does not implement the Foundry project/Agent API, Anthropic Messages API or every model in the Foundry catalogue.
- **Verification:** provider tests replace HTTP with local fakes. A successful live AWS-to-Azure inference and a full Factory run have not been recorded.

## 1. Configure the Azure destination

- Select an authorised subscription and create or reuse a Foundry or Azure OpenAI resource.
- Deploy a compatible chat model with the required quota. Record deployment alias, model/version, region and deployment type.
- Choose regional processing or an appropriate EU DataZone deployment when the policy requires European processing. A Global deployment on a European resource does not guarantee that.
- Obtain the resource endpoint, such as `https://<resource>.openai.azure.com`. A project URL ending in `/api/projects/<project>` is not the inference endpoint accepted by this adapter.
- Select exactly one authentication mode: a resource API key, or an Entra access token for an identity authorised to perform inference. Use the token audience documented for the selected endpoint. The current adapter accepts an externally supplied token and does not refresh it.

## 2. Configure the Python caller

The placeholder-only [`environment.example`](environment.example) is not loaded automatically. Supply these values in the process environment:

```text
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=<deployment-alias>
AZURE_OPENAI_API_VERSION=v1
# Exactly one credential, supplied by the secret store:
# AZURE_OPENAI_API_KEY
# AZURE_OPENAI_AD_TOKEN
```

- For an AWS ECS task, store the credential in AWS Secrets Manager and reference it through the task definition's `secrets` configuration. Give the task execution role the required secret-read and, where applicable, KMS-decrypt permissions. An AWS IAM role itself is not an Azure credential.
- Permit DNS resolution and outbound HTTPS on port 443 to the approved Azure resource. A private endpoint also requires private routing and DNS between the clouds.
- Keep destination selection under operator control. Keep credentials outside source, committed Terraform values, article examples and logs.

## 3. Read and test the connection code

```python
import json
from aws_agent_platform_lab.providers import AzureOpenAIProvider

provider = AzureOpenAIProvider()  # Reads the environment above.
prompt = json.dumps({
    "role": "analyst",
    "instructions": 'Return exactly {"status":"ok","citations":[]}.',
    "scenario": {"synthetic": True, "request": "Synthetic connectivity test"},
    "documents": [{"id": "CONNECTIVITY-REF", "text": "Synthetic connectivity fixture."}],
})
answer = provider.generate("analyst", prompt)
usage = provider.last_usage
```

- `generate()` sends `POST /openai/v1/chat/completions`, with the deployment alias in the JSON `model` field.
- API-key authentication uses `api-key`; token authentication uses `Authorization: Bearer ...`. Credentials are not placed in URLs.
- The adapter validates the endpoint, bounds timeouts/retries/output, rejects redirects and incomplete answers, and exposes sanitised errors.
- A dated API version selects the legacy `/openai/deployments/<alias>/chat/completions?api-version=...` route.

Install the project in your own virtual environment (`python -m pip install -e .`), then run:

```text
python scripts/check_azure_connection.py
python scripts/check_azure_connection.py --call
```

- The first command validates configuration without calling a model.
- The second sends a fixed synthetic request, checks its JSON result and reports tokens. It can incur charges and does not enforce a dollar cap.
- Neither command starts the Factory, reads company documents or approves G1–G4.

## 4. Preserve AWS Factory controls before deployment

- The current `FACTORY_PROVIDER=azure` Factory selection uses the local adapter harness. It does not retain shared DynamoDB configuration or wire the Bedrock retriever.
- Before enabling Azure on the public AWS Factory, decouple inference selection from runtime selection. Retain verified Cognito identities, filtered retrieval, DynamoDB checkpoints/run ownership and separate human gates.
- Do not switch the deployed service to `FACTORY_PROVIDER=azure` as a shortcut. Record a live inference test and a complete authenticated Factory run separately.
- Long-running token authentication requires renewal; a static Entra token is only a short-lived test credential.

## Official references

- [Foundry endpoints and deployment aliases](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/endpoints)
- [Azure OpenAI API reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)
- [Data processing and privacy for models sold by Azure](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy)
