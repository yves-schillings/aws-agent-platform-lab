"""Explicit, digest-only update of one existing ECS Express service.

No AWS client is created without --execute. This script never creates resources,
changes identity configuration, subscribes to a model or invokes a model.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DeploymentError(ValueError):
    """Controlled deployment failure safe to present without provider response bodies."""
    pass


def validate_target(account: str, region: str, service_arn: str, image_uri: str) -> str:
    """Require a matching account, region, ECS service and immutable ECR image digest."""
    if not re.fullmatch(r"\d{12}", account):
        raise DeploymentError("An explicit 12-digit account ID is required.")
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d+", region):
        raise DeploymentError("An explicit commercial AWS region is required.")
    service_pattern = rf"arn:aws:ecs:{re.escape(region)}:{account}:service/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+"
    if not re.fullmatch(service_pattern, service_arn):
        raise DeploymentError("The service ARN must match the explicit account and region.")
    image_pattern = rf"{account}\.dkr\.ecr\.{re.escape(region)}\.amazonaws\.com/([a-z0-9][a-z0-9/_-]*)@sha256:[a-f0-9]{{64}}"
    match = re.fullmatch(image_pattern, image_uri)
    if not match:
        raise DeploymentError("Use an immutable ECR digest in the same account and region.")
    return match.group(1)


def stable_configuration(service: dict[str, Any]) -> dict[str, Any]:
    """Read one active cloud configuration and reject unsafe local-demo exposure."""
    if service.get("status", {}).get("statusCode") != "ACTIVE":
        raise DeploymentError("The Express service is not ACTIVE; inspect its deployment before retrying.")
    configurations = service.get("activeConfigurations", [])
    if len(configurations) != 1:
        raise DeploymentError("Exactly one active configuration is required; another deployment may be running.")
    config = configurations[0]
    container = config.get("primaryContainer", {})
    if not container.get("image") or container.get("containerPort") != 8000:
        raise DeploymentError("The current configuration is not the expected port-8000 application.")
    environment = {item["name"]: item["value"] for item in container.get("environment", [])}
    if environment.get("LOCAL_DEMO_MODE") != "false":
        raise DeploymentError("Refusing to update a public service configured for local demo mode.")
    return config


def write_receipt(path: Path, receipt: dict[str, Any], *, new: bool = False) -> None:
    """Write a bounded deployment receipt without embedding container secrets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if new else "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")


def deploy(*, ecs: Any, ecr: Any, sts: Any, account: str, region: str,
           service_arn: str, image_uri: str, output: Path,
           expected_current_image: str | None = None, timeout: int = 1800,
           poll_seconds: float = 15, clock=time.monotonic, sleep=time.sleep) -> dict[str, Any]:
    """Promote one existing Express service to an explicit image digest and observe it.

    Account, registry and current-version checks precede the update. Preserve
    configuration and secret references. Service health is not end-to-end
    authentication, retrieval or model-inference proof.
    """
    repository = validate_target(account, region, service_arn, image_uri)
    if output.exists():
        raise DeploymentError("The receipt already exists; choose a new output path.")
    if sts.get_caller_identity()["Account"] != account:
        raise DeploymentError("The active AWS identity belongs to a different account.")
    digest = image_uri.rsplit("@", 1)[1]
    images = ecr.describe_images(repositoryName=repository, imageIds=[{"imageDigest": digest}]).get("imageDetails", [])
    if len(images) != 1 or images[0].get("imageDigest") != digest:
        raise DeploymentError("The requested image digest is not present in the selected ECR repository.")
    service = ecs.describe_express_gateway_service(serviceArn=service_arn)["service"]
    config = stable_configuration(service)
    current = config["primaryContainer"]["image"]
    if expected_current_image is not None and current != expected_current_image:
        raise DeploymentError("The current image changed; refusing to overwrite a newer deployment.")
    if current.split("@", 1)[0] != image_uri.split("@", 1)[0]:
        raise DeploymentError("The new image must belong to the current repository.")
    receipt = {
        "schema_version": 1, "account_id": account, "region": region,
        "service_arn": service_arn, "previous_image": current, "target_image": image_uri,
        "previous_revision": config.get("serviceRevisionArn"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "unchanged" if current == image_uri else "prepared",
    }
    write_receipt(output, receipt, new=True)
    if current == image_uri:
        return receipt
    # Keep all current environment, secret references, logging and command fields.
    # Never dump this container configuration into a public build artifact.
    container = copy.deepcopy(config["primaryContainer"])
    container["image"] = image_uri
    try:
        response = ecs.update_express_gateway_service(serviceArn=service_arn, primaryContainer=container)
        receipt["target_revision"] = response["service"].get("targetConfiguration", {}).get("serviceRevisionArn")
        receipt["status"] = "deploying"
        write_receipt(output, receipt)
        deadline = clock() + timeout
        while clock() < deadline:
            service = ecs.describe_express_gateway_service(serviceArn=service_arn)["service"]
            code = service.get("status", {}).get("statusCode", "")
            if "FAIL" in code or code in {"INACTIVE", "DRAINING"}:
                raise DeploymentError("ECS reported an unsuccessful deployment; inspect service events.")
            configs = service.get("activeConfigurations", [])
            if code == "ACTIVE" and len(configs) == 1:
                active = configs[0]
                same_image = active.get("primaryContainer", {}).get("image") == image_uri
                same_revision = receipt.get("target_revision") is None or active.get("serviceRevisionArn") == receipt["target_revision"]
                if same_image and same_revision:
                    receipt.update(status="service_active", finished_at=datetime.now(timezone.utc).isoformat())
                    write_receipt(output, receipt)
                    return receipt
            sleep(poll_seconds)
        raise DeploymentError("Timed out waiting for the selected Express revision. No success was inferred.")
    except Exception as error:
        receipt.update(status="failed_or_unverified", error_type=type(error).__name__)
        write_receipt(output, receipt)
        raise


def parser() -> argparse.ArgumentParser:
    """Require an exact deployment target and an explicit execution switch."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--expected-account-id", required=True)
    result.add_argument("--region", required=True)
    result.add_argument("--service-arn", required=True)
    result.add_argument("--image-uri", required=True)
    result.add_argument("--expected-current-image")
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--wait-seconds", type=int, default=1800)
    result.add_argument("--execute", action="store_true", help="Authorise the existing service update; absent means offline input validation only.")
    return result


def main(argv: list[str] | None = None) -> int:
    """Validate offline by default; create AWS clients only after --execute."""
    args = parser().parse_args(argv)
    try:
        validate_target(args.expected_account_id, args.region, args.service_arn, args.image_uri)
        if not 30 <= args.wait_seconds <= 3600:
            raise DeploymentError("Wait must be between 30 and 3600 seconds.")
        if not args.execute:
            print("Inputs valid. No AWS requests made. Add --execute only for an authorised update.")
            return 0
        import boto3
        from botocore.config import Config
        config = Config(connect_timeout=10, read_timeout=45, retries={"total_max_attempts": 3, "mode": "standard"}, ignore_configured_endpoint_urls=True)
        session = boto3.Session(region_name=args.region)
        receipt = deploy(
            ecs=session.client("ecs", config=config), ecr=session.client("ecr", config=config),
            sts=session.client("sts", config=config), account=args.expected_account_id,
            region=args.region, service_arn=args.service_arn, image_uri=args.image_uri,
            expected_current_image=args.expected_current_image, output=args.output, timeout=args.wait_seconds,
        )
        print(json.dumps(receipt, indent=2))
        print("Service configuration checked. An authenticated end-to-end smoke test remains required.")
        return 0
    except DeploymentError as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception as error:
        # Provider exception bodies may contain environment details. Keep output bounded.
        print(f"Deployment failed ({type(error).__name__}). Inspect AWS service events with an authorised operator.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
