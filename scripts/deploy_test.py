"""Offline contracts for the deployment boundary; no cloud calls."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from deploy_express import DeploymentError, deploy, main, stable_configuration, validate_target


ACCOUNT = "123456789012"  # AWS documentation example only; never a deployment default.
REGION = "eu-west-1"
SERVICE = f"arn:aws:ecs:{REGION}:{ACCOUNT}:service/test/test"
REPOSITORY = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/test"
PREVIOUS = REPOSITORY + "@sha256:" + "a" * 64
TARGET = REPOSITORY + "@sha256:" + "b" * 64


def service(image=PREVIOUS, revision="previous"):
    return {"status": {"statusCode": "ACTIVE"}, "activeConfigurations": [{
        "serviceRevisionArn": revision,
        "primaryContainer": {"image": image, "containerPort": 8000,
            "environment": [{"name": "LOCAL_DEMO_MODE", "value": "false"}, {"name": "ACCESS_POLICY_JSON", "value": "private-policy"}],
            "secrets": [{"name": "OBSERVABILITY_SECRET", "valueFrom": "private-secret-reference"}],
            "awsLogsConfiguration": {"logGroup": "/lab/test"}},
    }]}


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "receipt.json"
        self.ecs, self.ecr, self.sts = Mock(), Mock(), Mock()
        self.sts.get_caller_identity.return_value = {"Account": ACCOUNT}
        self.ecr.describe_images.return_value = {"imageDetails": [{"imageDigest": "sha256:" + "b" * 64}]}
        self.ecs.describe_express_gateway_service.side_effect = [{"service": service()}, {"service": service(TARGET, "target")}]
        self.ecs.update_express_gateway_service.return_value = {"service": {"targetConfiguration": {"serviceRevisionArn": "target"}}}

    def run_deploy(self, **overrides):
        args = dict(ecs=self.ecs, ecr=self.ecr, sts=self.sts, account=ACCOUNT, region=REGION, service_arn=SERVICE, image_uri=TARGET, output=self.output)
        return deploy(**(args | overrides))

    def test_preserves_configuration_and_redacts_receipt(self):
        receipt = self.run_deploy()
        container = self.ecs.update_express_gateway_service.call_args.kwargs["primaryContainer"]
        expected = copy.deepcopy(service()["activeConfigurations"][0]["primaryContainer"])
        expected["image"] = TARGET
        self.assertEqual(container, expected)
        self.assertEqual(receipt["status"], "service_active")
        self.assertNotIn("private-policy", self.output.read_text())
        self.assertNotIn("private-secret-reference", self.output.read_text())

    def test_account_mismatch_stops_before_mutation(self):
        self.sts.get_caller_identity.return_value = {"Account": "999999999999"}
        with self.assertRaises(DeploymentError):
            self.run_deploy()
        self.ecs.update_express_gateway_service.assert_not_called()

    def test_rejects_mutable_tag_and_foreign_registry(self):
        for image in [REPOSITORY + ":latest", TARGET.replace(ACCOUNT, "999999999999")]:
            with self.assertRaises(DeploymentError):
                validate_target(ACCOUNT, REGION, SERVICE, image)

    def test_current_image_precondition(self):
        with self.assertRaises(DeploymentError):
            self.run_deploy(expected_current_image=TARGET)
        self.ecs.update_express_gateway_service.assert_not_called()

    def test_concurrent_deployment_or_local_mode_is_rejected(self):
        snapshot = service()
        snapshot["activeConfigurations"].append(copy.deepcopy(snapshot["activeConfigurations"][0]))
        with self.assertRaises(DeploymentError):
            stable_configuration(snapshot)
        snapshot = service()
        snapshot["activeConfigurations"][0]["primaryContainer"]["environment"][0]["value"] = "true"
        with self.assertRaises(DeploymentError):
            stable_configuration(snapshot)

    def test_failure_does_not_claim_success(self):
        self.ecs.describe_express_gateway_service.side_effect = [{"service": service()}, {"service": {"status": {"statusCode": "FAILED"}}}]
        with self.assertRaises(DeploymentError):
            self.run_deploy()
        self.assertIn("failed_or_unverified", self.output.read_text())

    def test_existing_receipt_is_preserved(self):
        self.output.write_text("preserve")
        with self.assertRaises(DeploymentError):
            self.run_deploy()
        self.assertEqual(self.output.read_text(), "preserve")

    def test_default_is_offline_validation(self):
        self.assertEqual(main(["--expected-account-id", ACCOUNT, "--region", REGION, "--service-arn", SERVICE, "--image-uri", TARGET, "--output", str(self.output)]), 0)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
