"""Identity-scoped retrieval, independently checked before model use and display."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import sha256_bytes
from .workflow import retrieve


class RetrievalError(RuntimeError):
    """Safe failure for invalid permissions, provenance or empty retrieval results."""
    pass


def access_scope(principal):
    """Read and validate the source scope already resolved from the caller identity."""
    values = (principal.tenant, principal.access_level)
    if any(not isinstance(v, str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", v) for v in values):
        raise RetrievalError("Identity has no valid document scope")
    return values


def permitted(principal, document):
    """Check document metadata against the exact tenant, level and synthetic-data policy."""
    tenant, level = access_scope(principal)
    return (document.get("tenant") == tenant and document.get("access_level") == level
            and document.get("synthetic") is True)


def mandatory_filter(principal):
    """Build a server-owned Knowledge Bases filter that callers cannot widen."""
    tenant, level = access_scope(principal)
    return {"andAll": [
        {"equals": {"key": "tenant", "value": tenant}},
        {"equals": {"key": "access_level", "value": level}},
        {"equals": {"key": "synthetic", "value": True}},
    ]}


class LocalRetriever:
    """Filter the synthetic corpus by identity before deterministic lexical ranking."""
    mode = "lexical, synthetic corpus, simulated identity"
    def __init__(self, corpus=None):
        """Load the configured local synthetic corpus; no remote search is performed."""
        if corpus is None:
            corpus = os.environ.get("LAB_CORPUS_PATH") or Path(__file__).resolve().parents[2] / "corpus" / "web_knowledge.json"
        self.documents = json.loads(Path(corpus).read_text(encoding="utf-8"))["documents"]

    def search(self, principal, query):
        """Return at most five allowed documents; denied sources never enter ranking."""
        allowed = [d for d in self.documents if permitted(principal, d)]
        if not allowed:
            raise RetrievalError("No authorized reference documents were found")
        return retrieve(query, allowed, 5)


class BedrockRetriever:
    """Retrieve authorized chunks from Bedrock Knowledge Bases, not OpenSearch."""
    mode = "Bedrock Knowledge Bases, S3 Vectors, server-enforced metadata filter"
    def __init__(self, knowledge_base_id, region, client=None):
        """Bind the configured knowledge base and region to a bounded AWS client."""
        if not knowledge_base_id or not region:
            raise ValueError("Knowledge base configuration is incomplete")
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("bedrock-agent-runtime", region_name=region, config=Config(
                connect_timeout=5, read_timeout=30,
                retries={"mode": "standard", "total_max_attempts": 2},
                ignore_configured_endpoint_urls=True))
        self.client, self.knowledge_base_id = client, knowledge_base_id

    def search(self, principal, query):
        """Apply the mandatory filter and verify every returned chunk before model use.

        Source identifiers, versions and content hashes preserve provenance.
        An index result that violates permissions fails closed.
        """
        response = self.client.retrieve(knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={"text": query}, retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": 5,
                                              "filter": mandatory_filter(principal)}})
        documents = []
        seen = set()
        versions = {}
        for result in response.get("retrievalResults", []):
            metadata = result.get("metadata", {})
            # Defense in depth: even a buggy/stale index response may not widen access.
            if not permitted(principal, metadata):
                raise RetrievalError("Retrieved source failed its authorization check")
            content = result.get("content", {}).get("text", "")
            doc_id, version = metadata.get("document_id"), metadata.get("version")
            if (not isinstance(doc_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", doc_id)
                    or not isinstance(version, str) or not version.strip() or len(version) > 128
                    or not isinstance(content, str) or not 0 < len(content) <= 20_000):
                raise RetrievalError("Retrieved source is missing valid provenance")
            # A stale ingestion can leave different versions in one result. Fail
            # closed rather than combine conflicting source evidence or drop a
            # newer version during duplicate removal. This does not prove that
            # a single consistent version is current in the authoritative source.
            if doc_id in versions and versions[doc_id] != version:
                raise RetrievalError("Retrieved passages contain inconsistent source versions")
            versions[doc_id] = version
            # A document can have multiple chunks. Each citation identifies exact bytes.
            chunk_id = doc_id + "-" + sha256_bytes(content.encode())[:12]
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            documents.append({"id": chunk_id, "document_id": doc_id,
                "title": str(metadata.get("title", doc_id))[:200], "version": version,
                "text": content, "tenant": metadata["tenant"],
                "access_level": metadata["access_level"], "synthetic": True})
        if not documents:
            raise RetrievalError("No authorized reference documents were found")
        return documents
