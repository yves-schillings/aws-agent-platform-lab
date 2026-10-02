"""Command-line entry point. Run never implicitly grants human approval."""
from __future__ import annotations

import argparse
import json
import sys

from .models import ValidationError
from .providers import ProviderError
from .workflow import run_workflow, decide_run


def build_parser() -> argparse.ArgumentParser:
    """Define separate run and exact-artifact approve/reject commands."""
    parser = argparse.ArgumentParser(description="Synthetic multi-agent design prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run agents and stop before human approval")
    run.add_argument("--provider", choices=("mock", "aws", "azure"), default="mock")
    run.add_argument("--scenario", required=True, help="Synthetic scenario JSON")
    run.add_argument("--corpus", help="Authorized synthetic corpus JSON; default: corpus.json beside scenario")
    run.add_argument("--output", required=True, help="New or empty directory for this run")
    run.add_argument("--max-corrections", type=int, choices=(0, 1, 2), default=2)
    run.add_argument("--top-k", type=int, choices=range(1, 11), default=3)
    approve = commands.add_parser("approve", help="Approve or reject the exact artifact hash")
    approve.add_argument("--run-dir", required=True)
    approve.add_argument("--artifact-hash", required=True)
    approve.add_argument("--decision", choices=("approve", "reject"), required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse a local operator command, execute it, and return a process exit status.

    Selecting a cloud provider is explicit; an approval copies only the
    reviewed artifact to the fixed local publication path.
    """
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            state = run_workflow(args.scenario, args.output, provider_name=args.provider,
                corpus_path=args.corpus, max_corrections=args.max_corrections, top_k=args.top_k)
        else:
            state = decide_run(args.run_dir, args.artifact_hash, args.decision)
    except (ValidationError, OSError, ProviderError) as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        # Do not expose possible credentials/provider request content from exceptions.
        print(json.dumps({"status": "error", "error_type": type(exc).__name__,
                          "message": "Provider or execution failed; consult local trace/configuration."}), file=sys.stderr)
        return 2
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 3 if state["status"] in {"review_failed", "failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
