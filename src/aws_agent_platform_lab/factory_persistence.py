"""Renewable per-run leases and fenced DynamoDB checkpoint writes.

A heartbeat keeps a slow model call exclusive. Every checkpoint write also
checks the same live lease atomically, so a paused task cannot publish stale
state after another task has taken over. This does not make external model
calls exactly once, and an interrupted run still requires operator recovery.
"""
from contextlib import contextmanager
from copy import copy
import math
import re
import threading
import time
import uuid

from botocore.config import Config
from botocore.exceptions import ClientError

from .services import ServiceError


class RunLease:
    """One operation's token, heartbeat and checkpoint authorization."""

    def __init__(self, registry, run_id, token):
        self.registry, self.run_id, self.token = registry, run_id, token
        self.stopped = threading.Event()
        self.lost = threading.Event()

    def get(self, run_id):
        """Read immutable run scope through the same registry."""
        return self.registry.get(run_id)

    def condition(self):
        """Bind a transaction to this token and its unexpired lease."""
        if self.lost.is_set() or self.stopped.is_set():
            raise ServiceError("Factory lease was lost; reload the run before retrying", 503)
        return {"TableName": self.registry.table_name,
                "Key": {"run_id": {"S": self.run_id + "#lock"}},
                "ConditionExpression": "lease_owner = :owner AND lease_expires > :now",
                "ExpressionAttributeValues": {":owner": {"S": self.token},
                                               ":now": {"N": str(int(self.registry.wall_clock()))}}}

    def renew(self):
        """Extend only an unexpired lease still owned by this operation."""
        check = self.condition()
        now = self.registry.wall_clock()
        self.registry.client.update_item(
            TableName=check["TableName"], Key=check["Key"],
            UpdateExpression="SET lease_expires = :expires",
            ConditionExpression=check["ConditionExpression"],
            ExpressionAttributeValues={**check["ExpressionAttributeValues"],
                ":expires": {"N": str(math.ceil(now + self.registry.lease_seconds))}})

    def heartbeat(self):
        """Stop granting writes on any renewal failure; expiry permits recovery."""
        while not self.stopped.wait(self.registry.renew_seconds):
            try:
                self.renew()
            except Exception:
                self.lost.set()
                return

    def fence_saver(self, saver):
        """Clone the pinned AWS saver with a token-bound client for this invocation.

        Never install a mutable current-token field on the shared saver: an old
        operation could otherwise borrow a replacement operation's authority.
        The deployed saver has no S3 offload and only uses PutItem for writes.
        """
        cloned = copy(saver)
        client = FencedCheckpointClient(saver.client, self, saver.table_name)
        cloned.client = client
        cloned.storage = copy(saver.storage)
        cloned.storage.dynamodb_client = client
        cloned.repo = copy(saver.repo)
        cloned.repo.dynamodb_client = client
        cloned.repo.storage = cloned.storage
        return cloned


class FencedCheckpointClient:
    """Delegate reads; combine each checkpoint Put with a lease ConditionCheck."""

    def __init__(self, client, lease, table_name):
        self.client, self.lease, self.table_name = client, lease, table_name

    def __getattr__(self, name):
        # Fail closed if a future saver changes its write implementation.
        if name in {"batch_write_item", "update_item", "delete_item", "transact_write_items"}:
            raise ServiceError("Unsupported Factory checkpoint write", 503)
        return getattr(self.client, name)

    def put_item(self, **params):
        """Write only this run's checkpoint and only while its lease is valid."""
        pk = params.get("Item", {}).get("PK", {}).get("S", "")
        run_id = self.lease.run_id
        if (params.get("TableName") != self.table_name or not
                (pk == f"CHECKPOINT_{run_id}" or pk.startswith(f"CHUNK_{run_id}#")
                 or pk.startswith(f"WRITES_{run_id}#"))):
            raise ServiceError("Factory checkpoint does not match the leased run", 503)
        try:
            self.client.transact_write_items(TransactItems=[
                {"ConditionCheck": self.lease.condition()}, {"Put": params}])
        except ClientError as exc:
            reasons = exc.response.get("CancellationReasons", [])
            # Preserve the saver's existing idempotent-put semantics only when
            # the lease check passed and the checkpoint item already exists.
            if (len(reasons) == 2 and reasons[0].get("Code") == "None"
                    and reasons[1].get("Code") == "ConditionalCheckFailed"):
                raise ClientError({"Error": {"Code": "ConditionalCheckFailedException",
                                               "Message": "Checkpoint already exists"}}, "PutItem") from None
            self.lease.lost.set()
            raise ServiceError("Factory checkpoint write refused; reload the run before retrying", 503) from None
        return {}


class DynamoRunRegistry:
    """Shared immutable run scope with renewable, bounded per-run leases."""

    def __init__(self, table_name, *, region_name=None, client=None, lease_seconds=45,
                 renew_seconds=None, acquire_timeout=5, wall_clock=time.time,
                 monotonic=time.monotonic, sleep=time.sleep):
        if not isinstance(table_name, str) or not table_name:
            raise ValueError("A DynamoDB Factory runs table is required")
        if lease_seconds <= 0:
            raise ValueError("A positive Factory lease duration is required")
        renew_seconds = lease_seconds / 3 if renew_seconds is None else renew_seconds
        if not 0 < renew_seconds < lease_seconds or acquire_timeout < 0:
            raise ValueError("Factory renewal must precede expiry")
        if client is None:
            import boto3
            client = boto3.client("dynamodb", region_name=region_name,
                config=Config(connect_timeout=3, read_timeout=5,
                              retries={"total_max_attempts": 2, "mode": "standard"}))
        self.client, self.table_name = client, table_name
        self.lease_seconds, self.renew_seconds = lease_seconds, renew_seconds
        self.acquire_timeout = acquire_timeout
        self.wall_clock, self.monotonic, self.sleep = wall_clock, monotonic, sleep

    def create(self, run_id, identity):
        """Record the immutable server-derived owner and source scope once."""
        item = {"run_id": {"S": run_id}, **{key: {"S": identity[key]} for key in
                ("owner", "tenant", "access_level", "company_id", "project_id")}}
        try:
            self.client.put_item(TableName=self.table_name, Item=item,
                                 ConditionExpression="attribute_not_exists(run_id)")
        except Exception:
            raise ServiceError("Factory run state is temporarily unavailable", 409) from None

    def get(self, run_id):
        """Read run ownership consistently, without exposing provider errors."""
        try:
            response = self.client.get_item(TableName=self.table_name,
                Key={"run_id": {"S": run_id}}, ConsistentRead=True)
        except Exception:
            raise ServiceError("Factory run state is temporarily unavailable", 503) from None
        item = response.get("Item")
        return {key: value.get("S") for key, value in item.items()} if item else None

    @contextmanager
    def locked(self, run_id):
        """Acquire one run, renew during work, and release only our own token."""
        if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ServiceError("Factory run not found", 404)
        token = uuid.uuid4().hex
        deadline = self.monotonic() + self.acquire_timeout
        while True:
            now = self.wall_clock()
            try:
                self.client.update_item(TableName=self.table_name,
                    Key={"run_id": {"S": run_id + "#lock"}},
                    UpdateExpression="SET lease_owner = :owner, lease_expires = :expires",
                    ConditionExpression="attribute_not_exists(lease_expires) OR lease_expires <= :now",
                    ExpressionAttributeValues={":owner": {"S": token},
                        ":expires": {"N": str(math.ceil(now + self.lease_seconds))},
                        ":now": {"N": str(int(now))}})
                break
            except Exception as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code")
                if code != "ConditionalCheckFailedException":
                    raise ServiceError("Factory run state is temporarily unavailable", 503) from None
                if self.monotonic() >= deadline:
                    raise ServiceError("Factory run is busy; retry the request", 409) from None
                self.sleep(0.05)
        lease = RunLease(self, run_id, token)
        heartbeat = threading.Thread(target=lease.heartbeat, daemon=True,
                                     name="factory-lease-renewal")
        heartbeat.start()
        try:
            yield lease
            lease.condition()
        finally:
            lease.stopped.set()
            heartbeat.join(timeout=20)
            try:
                self.client.delete_item(TableName=self.table_name,
                    Key={"run_id": {"S": run_id + "#lock"}},
                    ConditionExpression="lease_owner = :owner",
                    ExpressionAttributeValues={":owner": {"S": token}})
            except Exception:
                # A crashed task's lease expires; never remove a successor's lock.
                pass
