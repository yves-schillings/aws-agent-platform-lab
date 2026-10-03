"""Validate the Azure adapter, or opt in to a synthetic inference request.

Default validation makes no network call. --call can incur Azure charges.
Credentials are read from the environment and are never printed. This checks
model access only: it does not start the Factory or approve any human gate.
"""

from __future__ import annotations

import argparse
import json
import os

from aws_agent_platform_lab.providers import AzureOpenAIProvider, ProviderError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--call", action="store_true",
                        help="Send a synthetic request; Azure may charge for inference")
    args = parser.parse_args(argv)
    settings = dict(os.environ)
    settings.setdefault("POC_MAX_ATTEMPTS", "1")
    settings.setdefault("POC_MAX_OUTPUT_TOKENS", "128")
    try:
        provider = AzureOpenAIProvider(environ=settings)
        if not args.call:
            print(json.dumps({"configuration_valid": True, "network_call": False,
                              "adapter": "AzureOpenAIProvider",
                              "api_version": provider.api_version}))
            return 0
        prompt = json.dumps({
            "role": "analyst",
            "instructions": 'Return exactly {"status":"ok","citations":[]}.',
            "scenario": {"id": "azure-connectivity", "title": "Synthetic connectivity test",
                         "request": "Confirm receipt of this synthetic request.", "synthetic": True},
            "documents": [{"id": "CONNECTIVITY-REF", "title": "Synthetic reference",
                           "text": "This is a fixed synthetic connectivity fixture."}],
        })
        # generate() builds the HTTPS request, authenticates, validates the
        # textual completion and records input/output token usage.
        result = json.loads(provider.generate("analyst", prompt))
        if result != {"status": "ok", "citations": []}:
            raise ProviderError("Azure connectivity response did not match the synthetic contract.")
        print(json.dumps({"connection_verified": True, "network_call": True,
                          "usage": provider.last_usage}))
        return 0
    except (ValueError, ProviderError) as error:
        message = str(error) if isinstance(error, ProviderError) else "Azure response is not valid JSON."
        print(json.dumps({"connection_verified": False, "error": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
