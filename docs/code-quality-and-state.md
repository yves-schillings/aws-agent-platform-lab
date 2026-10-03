# Code quality and Terraform state

The offline CI workflow runs Ruff correctness checks on `src`, `tests` and
`scripts`. It also runs mypy on the authentication and JSON validation modules.
This is an incremental typing boundary, not full-project static type coverage.
The tools are pinned in `requirements-quality.txt` and installed in a separate
environment so they do not change the production container dependencies.

Run locally from the repository root:

```powershell
python -m pip install -r requirements-quality.txt
python -m ruff check src tests scripts
python -m mypy
```

## Remote state migration

Terraform state is still local. Do not copy it to the public repository or
replace it with an empty state. Before a migration, preserve the complete local
state, verify the account and managed resource inventory, and provision a
dedicated private S3 bucket with encryption, versioning and public access
blocked. Grant the deployment role access only to the state object and its
lock object. Select its region and lifecycle independently of the demo's data.

Terraform 1.12 supports S3 native state locking with `use_lockfile = true`.
DynamoDB backend locking is deprecated. The application's DynamoDB checkpoint
tables are unrelated to Terraform backend locks.

Add the backend block only as part of that prepared migration:

```hcl
terraform {
  backend "s3" {}
}
```

Provide `bucket`, `key`, `region`, `encrypt = true` and
`use_lockfile = true` in a private backend configuration file. Do not put
credentials in that file. Then run `terraform init -migrate-state` with the
verified deployment profile. Confirm that `terraform state list` has the same
inventory, a read-only plan shows no unexpected changes, and a second session
cannot acquire an already held lock. Keep the local backup until recovery has
been verified. These are migration instructions; no migration is claimed here.

References: [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3),
[Ruff rules](https://docs.astral.sh/ruff/rules/),
[mypy incremental adoption](https://mypy.readthedocs.io/en/stable/existing_code.html).
