"""Small, explicit validation boundary for local data and model responses."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_JSON_BYTES = 1_000_000
MAX_MODEL_BYTES = 64_000
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class ValidationError(ValueError):
    """Input or output does not meet the prototype's explicit contract."""


def canonical_bytes(value: Any) -> bytes:
    """Encode deterministic JSON bytes used for persistence and exact-artifact hashes."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    """Return the SHA-256 fingerprint of the exact supplied bytes."""
    return hashlib.sha256(value).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys so validation and review see the same values."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    """Reject non-finite JSON numbers instead of accepting ambiguous numeric data."""
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError("JSON numbers must be finite")
    return result


def parse_json(text: str, *, max_bytes: int = MAX_JSON_BYTES) -> dict[str, Any]:
    """Parse a bounded JSON object with duplicate-key and numeric validation."""
    if not isinstance(text, str):
        raise ValidationError("JSON payload missing or too large")
    try:
        if len(text.encode("utf-8")) > max_bytes:
            raise ValidationError("JSON payload missing or too large")
        value = json.loads(text, object_pairs_hook=_unique_pairs,
                           parse_float=_finite_float,
                           parse_constant=lambda value: (_ for _ in ()).throw(
                               ValidationError(f"Invalid JSON constant: {value}")))
        # Reject escaped lone surrogates, including those in otherwise ignored fields.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ValidationError("Expected a strict JSON object, without markdown fences") from exc
    if not isinstance(value, dict):
        raise ValidationError("Expected a JSON object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    """Read a local JSON file through the same strict input boundary."""
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValidationError(f"Input file too large: {path.name}")
    try:
        return parse_json(path.read_text(encoding="utf-8-sig"))
    except UnicodeError as exc:
        raise ValidationError("Input file must be UTF-8 JSON") from exc


def text_field(value: Any, name: str, *, limit: int = 12_000) -> str:
    """Validate one required, bounded text field without changing its meaning."""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"{name} must be nonempty text of at most {limit} characters")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ValidationError(f"{name} contains control characters")
    return value


def text_list(value: Any, name: str, *, minimum: int = 1,
              maximum: int = 30) -> list[str]:
    """Validate a bounded list of nonempty textual values."""
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValidationError(f"{name} must contain {minimum} to {maximum} strings")
    for item in value:
        text_field(item, name, limit=4_000)
    return value


def validate_scenario(value: dict[str, Any]) -> dict[str, Any]:
    """Require an explicitly synthetic scenario with the expected request fields."""
    if value.get("synthetic") is not True:
        raise ValidationError("Only explicitly synthetic scenarios are accepted")
    if not isinstance(value.get("id"), str) or not IDENTIFIER.fullmatch(value["id"]):
        raise ValidationError("scenario.id must be a short alphanumeric identifier")
    text_field(value.get("title"), "scenario.title", limit=200)
    text_field(value.get("request"), "scenario.request", limit=12_000)
    # A declaration is a contract, not a personal-data detection system.
    return {key: value[key] for key in ("id", "title", "request", "synthetic")}


def validate_corpus(value: dict[str, Any]) -> list[dict[str, str]]:
    """Validate declared synthetic documents; this is not user authorization."""
    if value.get("authorized") is not True or value.get("synthetic") is not True:
        raise ValidationError("Corpus must declare authorized=true and synthetic=true")
    documents = value.get("documents")
    if not isinstance(documents, list) or not 1 <= len(documents) <= 100:
        raise ValidationError("Corpus must contain 1 to 100 documents")
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValidationError("Each corpus document must be an object")
        key = document.get("id")
        if not isinstance(key, str) or not IDENTIFIER.fullmatch(key) or key in seen:
            raise ValidationError("Corpus document IDs must be valid and unique")
        seen.add(key)
        text_field(document.get("title"), "document.title", limit=200)
        text_field(document.get("text"), "document.text", limit=20_000)
        result.append({field: document[field] for field in ("id", "title", "text")})
    return result


def citations(value: Any, allowed_ids: set[str], name: str = "citations") -> list[str]:
    """Reject references outside the retrieved document IDs; this is not fact checking."""
    result = text_list(value, name, maximum=100)
    if len(result) != len(set(result)) or any(item not in allowed_ids for item in result):
        raise ValidationError(f"{name} must contain unique retrieved document IDs")
    return result


def validate_response(role: str, value: dict[str, Any],
                      allowed_ids: set[str]) -> dict[str, Any]:
    """Enforce the role-specific output schema and permitted citation identifiers."""
    citations(value.get("citations"), allowed_ids)
    if role == "analyst":
        text_field(value.get("summary"), "analyst.summary")
        text_list(value.get("requirements"), "analyst.requirements")
    elif role == "designer":
        text_field(value.get("title"), "designer.title", limit=200)
        text_list(value.get("controls"), "designer.controls")
        steps = value.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
            raise ValidationError("designer.steps must contain 1 to 20 steps")
        for step in steps:
            if not isinstance(step, dict):
                raise ValidationError("Each step must be an object")
            text_field(step.get("actor"), "step.actor", limit=200)
            text_field(step.get("action"), "step.action", limit=4_000)
            citations(step.get("source_ids"), allowed_ids, "step.source_ids")
    elif role == "reviewer":
        if type(value.get("approved")) is not bool:
            raise ValidationError("reviewer.approved must be a boolean")
        issues = text_list(value.get("issues"), "reviewer.issues", minimum=0)
        if value["approved"] and issues:
            raise ValidationError("An approved review cannot contain unresolved issues")
        if not value["approved"] and not issues:
            raise ValidationError("A rejected review must explain at least one issue")
    else:
        raise ValidationError(f"Unknown agent role: {role}")
    return value
