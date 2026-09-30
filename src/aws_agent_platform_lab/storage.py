"""Small compare-and-swap JSON store. S3 provides cross-task conditional writes."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from .models import canonical_bytes, sha256_bytes


class ConflictError(RuntimeError):
    pass


def safe_key(key: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_/-]+\.json", key) or ".." in key or key.startswith("/"):
        raise ValueError("Invalid storage key")
    return key


class LocalStore:
    """Single-process development store, deliberately not a distributed lock."""
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, key):
        path = self.root / safe_key(key)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("Storage path escapes root")
        for parent in [path, *path.parents]:
            if parent == self.root:
                break
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise ValueError("Storage links are forbidden")
        return path

    def get(self, key):
        with self._lock:
            path = self._path(key)
            if not path.exists():
                return None, None
            data = path.read_bytes()
            return json.loads(data), sha256_bytes(data)

    def put(self, key, value, expected=None):
        """None means create only. An ETag means replace exactly that version."""
        with self._lock:
            _, current = self.get(key)
            if current != expected:
                raise ConflictError("The stored version changed")
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = canonical_bytes(value)
            temporary = path.with_suffix(".next")
            temporary.write_bytes(data)
            temporary.replace(path)
            return sha256_bytes(data)


class S3Store:
    def __init__(self, bucket: str, region: str, client=None):
        if not bucket or not region:
            raise ValueError("AWS storage configuration is incomplete")
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("s3", region_name=region, config=Config(
                connect_timeout=5, read_timeout=15,
                retries={"mode": "standard", "total_max_attempts": 2},
                ignore_configured_endpoint_urls=True))
        self.bucket, self.client = bucket, client

    def get(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=safe_key(key))
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") == "NoSuchKey":
                return None, None
            raise
        with response["Body"] as body:
            data = body.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("Stored document exceeds the size limit")
        return json.loads(data), response["ETag"]

    def put(self, key, value, expected=None):
        condition = {"IfNoneMatch": "*"} if expected is None else {"IfMatch": expected}
        try:
            result = self.client.put_object(Bucket=self.bucket, Key=safe_key(key),
                Body=canonical_bytes(value), ContentType="application/json", **condition)
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") in {
                    "PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
                raise ConflictError("The stored version changed") from None
            raise
        return result["ETag"]
