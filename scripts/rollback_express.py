"""Rollback an existing Express service to an explicitly selected known-good image."""
from __future__ import annotations

import sys
from deploy_express import main, parser


if __name__ == "__main__":
    arguments = parser().parse_args()
    if not arguments.expected_current_image:
        parser().error("rollback requires --expected-current-image to avoid replacing a newer release")
    # Same preservation, account, immutable-image and verification rules as deployment.
    raise SystemExit(main(sys.argv[1:]))
