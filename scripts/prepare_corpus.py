"""Prepare the checked-in synthetic corpus for Bedrock S3 ingestion. No AWS calls."""
import argparse
import json
from pathlib import Path


def prepare(output: Path):
    """Create synthetic text and metadata sidecars in a fresh local output directory.

    Preserve source scope and version for later Knowledge Bases ingestion.
    No upload, model embedding or AWS request occurs here.
    """
    source = Path(__file__).resolve().parents[1] / "corpus" / "web_knowledge.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("Only the explicitly synthetic corpus may be prepared")
    output.mkdir(parents=True, exist_ok=True)
    for doc in data["documents"]:
        content = output / (doc["id"] + ".txt")
        metadata = output / (doc["id"] + ".txt.metadata.json")
        attributes = {key: doc[key] for key in
                      ("tenant", "access_level", "synthetic", "document_id", "version", "title")}
        encoded = json.dumps({"metadataAttributes": attributes}, indent=2) + "\n"
        if len(encoded.encode()) > 1024:
            raise ValueError("Metadata exceeds the S3 Vectors KB limit")
        for path in (content, metadata):
            if path.exists():
                raise FileExistsError("Use a fresh output directory to preserve earlier corpus versions")
        content.write_text(doc["text"] + "\n", encoding="utf-8")
        metadata.write_text(encoded, encoding="utf-8")
    return len(data["documents"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(f"Prepared {prepare(parser.parse_args().output)} synthetic documents with metadata.")
