"""Offline DynamoDB semantics and pinned LangGraph saver integration.

Moto emulates AWS API conditions; these tests are not live recovery evidence.
"""
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import boto3
from moto import mock_aws
from langgraph_checkpoint_aws import DynamoDBSaver

from aws_agent_platform_lab.auth import Principal
from aws_agent_platform_lab.factory import FactoryService
from aws_agent_platform_lab.factory_persistence import DynamoRunRegistry
from aws_agent_platform_lab.services import ServiceError


class SerializedEmulatorClient:
    """Serialize emulator internals, which are not safe under LangGraph threads."""

    def __init__(self, client):
        self.client = client
        self.mutex = threading.RLock()

    def __getattr__(self, name):
        method = getattr(self.client, name)
        if not callable(method):
            return method
        def invoke(*args, **kwargs):
            with self.mutex:
                return method(*args, **kwargs)
        return invoke


@mock_aws
class FactoryLeaseTests(unittest.TestCase):
    def setUp(self):
        self.session = boto3.Session(aws_access_key_id="testing", aws_secret_access_key="testing",
                                    region_name="eu-west-1")
        self.client = SerializedEmulatorClient(self.session.client("dynamodb"))
        for name, keys in [("runs", ["run_id"]), ("checkpoints", ["PK", "SK"])]:
            self.client.create_table(TableName=name, BillingMode="PAY_PER_REQUEST",
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in keys],
                KeySchema=[{"AttributeName": k, "KeyType": "HASH" if i == 0 else "RANGE"}
                           for i, k in enumerate(keys)])
        self.registry = DynamoRunRegistry("runs", client=self.client, acquire_timeout=0)
        self.saver = DynamoDBSaver("checkpoints", session=self.session,
                                  enable_checkpoint_compression=True)
        self.saver.client = self.client
        self.saver.storage.dynamodb_client = self.client
        self.saver.repo.dynamodb_client = self.client
        self.run_id = "a" * 32

    def test_heartbeat_excludes_another_task_beyond_original_expiry(self):
        registry = DynamoRunRegistry("runs", client=self.client, lease_seconds=1,
                                     renew_seconds=0.1, acquire_timeout=0)
        with registry.locked(self.run_id):
            time.sleep(2)
            with self.assertRaises(ServiceError) as caught:
                with self.registry.locked(self.run_id):
                    self.fail("A second task acquired a live lease")
            self.assertEqual(caught.exception.status_code, 409)
        with self.registry.locked(self.run_id):
            pass

    def test_replaced_owner_cannot_write_or_delete_successors_lock(self):
        with self.assertRaises(ServiceError):
            with self.registry.locked(self.run_id) as lease:
                fenced = lease.fence_saver(self.saver)
                self.assertIs(fenced.repo.storage, fenced.storage)
                self.assertIsNot(fenced.repo.storage, self.saver.storage)
                self.client.update_item(TableName="runs", Key={"run_id": {"S": self.run_id + "#lock"}},
                    UpdateExpression="SET lease_owner = :owner",
                    ExpressionAttributeValues={":owner": {"S": "successor"}})
                fenced.client.put_item(TableName="checkpoints",
                    Item={"PK": {"S": "CHECKPOINT_" + self.run_id}, "SK": {"S": "stale"}})
        lock = self.client.get_item(TableName="runs", Key={"run_id": {"S": self.run_id + "#lock"}})
        self.assertEqual(lock["Item"]["lease_owner"]["S"], "successor")
        self.assertEqual(self.client.scan(TableName="checkpoints")["Count"], 0)

    def test_expired_lease_cannot_be_renewed_or_publish(self):
        with self.assertRaises(ServiceError):
            with self.registry.locked(self.run_id) as lease:
                self.client.update_item(TableName="runs", Key={"run_id": {"S": self.run_id + "#lock"}},
                    UpdateExpression="SET lease_expires = :expiry",
                    ExpressionAttributeValues={":expiry": {"N": "0"}})
                with self.assertRaises(Exception):
                    lease.renew()
                lease.fence_saver(self.saver).client.put_item(TableName="checkpoints",
                    Item={"PK": {"S": "CHECKPOINT_" + self.run_id}, "SK": {"S": "expired"}})
        self.assertEqual(self.client.scan(TableName="checkpoints")["Count"], 0)

    def test_renewal_failure_stops_checkpoint_writes(self):
        registry = DynamoRunRegistry("runs", client=self.client, lease_seconds=2,
                                     renew_seconds=0.02, acquire_timeout=0)
        with self.assertRaises(ServiceError):
            with registry.locked(self.run_id) as lease:
                with patch.object(lease, "renew", side_effect=RuntimeError("synthetic failure")):
                    self.assertTrue(lease.lost.wait(1))
                lease.fence_saver(self.saver).client.put_item(TableName="checkpoints",
                    Item={"PK": {"S": "CHECKPOINT_" + self.run_id}, "SK": {"S": "lost"}})
        self.assertEqual(self.client.scan(TableName="checkpoints")["Count"], 0)

    def test_full_graph_uses_fenced_saver_and_resumes_on_another_service(self):
        with tempfile.TemporaryDirectory() as root:
            first = FactoryService(Path(root), checkpointer=self.saver, registry=self.registry,
                                   verified_identities=True)
            second = FactoryService(Path(root), checkpointer=self.saver, registry=self.registry,
                                    verified_identities=True)
            requester = Principal("requester", ("tenant-alpha",), "alpha", "internal", False)
            approver = Principal("approver", tuple("factory-" + g.lower() + "-approver"
                                 for g in ("G1", "G2", "G3", "G4")), "alpha", "internal", False)
            try:
                state = first.start_run(requester, "Prepare a synthetic read-only affiliation application.")
                for gate in ("G1", "G2", "G3", "G4"):
                    viewed = second.get_run(approver, state["run_id"])
                    self.assertEqual(viewed["pending_gate"], state["pending_gate"])
                    state = second.decide_run(approver, state["run_id"], gate,
                        viewed["pending_gate"]["artifact_hash"], "approve", "Inspected synthetic fixture.")
                self.assertEqual(first.get_run(requester, state["run_id"])["status"], "release_ready")
                self.assertEqual(len(state["decisions"]), 4)
            finally:
                first.close()
                second.close()
