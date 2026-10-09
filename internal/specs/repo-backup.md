# Repo Backup

This file is the canonical source for repository backup action and reusable
workflow behavior. Keep detailed backup context here; other docs should link to
this file instead of repeating the contract.

## Recommended Entry Point

Use `.github/workflows/repo-backup.yml` for production repository backups. The
caller repository owns scheduling, for example daily cron plus
`workflow_dispatch`, and calls this reusable workflow.

Use `.github/actions/repo-backup/action.yml` directly only when the caller
workflow needs to own checkout or additional orchestration.

## Shared Actions Repository Backup

This repository backs itself up through `.github/workflows/daily-repo-backup.yml`.
That workflow is only the scheduled/manual caller; the reusable workflow
contract remains in `.github/workflows/repo-backup.yml`.

The caller uses the reviewed `@v2` release line. It keeps the daily cron while
using the monthly-full/daily-differential restore contract described below.
Before enabling this format, verify the bucket lifecycle and Object Lock
requirements in [Restore](#restore).

## Layering

The reusable workflow and the composite action intentionally have different
responsibilities.

`.github/workflows/repo-backup.yml` is the orchestration layer:

- checks out the caller repository with full history;
- checks out `validityBase/vbase-github-actions` at the reusable workflow ref
  into `.vbase-github-actions`;
- invokes the shared `repo-backup` composite action in Bitwarden mode.

`.github/actions/repo-backup/action.yml` is the implementation layer:

- accepts either a Bitwarden project or direct object storage credentials;
- uses the canonical `vbase-common` `bw_sm.env` CLI in Bitwarden mode, keeping
  resolved secrets scoped to the backup process;
- expects the caller repository to already be checked out;
- fetches all branch and tag refs;
- finds and validates this month's completed full backup, if one exists;
- creates a full-history bundle on the first successful run of a month, or if
  the existing monthly backup is unusable;
- otherwise creates a daily bundle containing Git objects absent from the
  monthly full backup; unchanged repositories produce metadata only;
- verifies the complete restored ref snapshot with `git fsck --strict`;
- uploads the bundle and checksum when present, then uploads `metadata.json`
  last as the completion marker, using AWS CLI and the S3-compatible endpoint.

Each run still fetches full repository history on a fresh GitHub-hosted runner.
This change reduces objects stored in the backup bucket, not GitHub-to-runner
transfer. Daily bundles are differential from the monthly full backup, so
changes already made earlier in the month may also appear in later bundles.

This keeps credential loading, backup generation, and upload behavior in one
shared action implementation while the reusable workflow owns only checkout
and caller-facing orchestration.

## Backup Object Layout

Monthly full backups are uploaded under:

```text
<backup-prefix>/<owner>/<repo>/YYYY/MM/full/<timestamp>-<run-id>-<attempt>/
```

Daily incremental backups use the existing dated layout:

```text
<backup-prefix>/<owner>/<repo>/YYYY/MM/DD/<timestamp>-<run-id>-<attempt>/
```

A full backup has `repo.bundle`, `repo.bundle.sha256`, and `metadata.json`.
An incremental has the same three files when new Git objects exist, or only
`metadata.json` when the monthly full already contains every current object.
The metadata records `backup_type`, `base_prefix`, SHA-256, current refs, and
the run identifier. Only a run with `metadata.json` is considered complete.
Existing daily full bundles remain valid standalone restore points.

## Restore

Download the selected monthly full `repo.bundle` and `metadata.json`, plus the
selected daily bundle and metadata when restoring an incremental. The daily
metadata names its exact monthly `base_prefix`. Check the checksums and restore
the refs with the shared helper:

```bash
cd /path/to/vbase-github-actions/.github/actions/repo-backup
python3 -m scripts.restore_backup \
  --full-bundle /path/to/monthly/repo.bundle \
  --full-metadata /path/to/monthly/metadata.json \
  --daily-bundle /path/to/daily/repo.bundle \
  --daily-metadata /path/to/daily/metadata.json \
  --output /path/to/restored.git
```

Omit both `--daily-*` arguments for a monthly full restore. If the daily
metadata has `bundle_file: null`, omit only `--daily-bundle`. The output is a
bare mirror; clone it to obtain a working tree. The helper verifies the bundle
hashes, required Git objects, exact refs, and repository integrity. Quarterly
restore tests should download artifacts from object storage and use this path,
not merely re-check the local bundle produced by a workflow run.

The monthly full object must remain available for every dependent daily backup.
If a lifecycle policy deletes daily objects after N days, retain monthly full
objects for at least N + 31 days. Object Lock can prevent earlier deletion;
bucket lifecycle and retention must be checked before enabling the new format.

## Composite Action Contract

Choose exactly one credential mode:

- Bitwarden mode requires `bitwarden-access-token`, `bitwarden-project`, and
  `vbase-common-repo-read-token`.
- Direct mode requires all five `object-storage-*` inputs.

Direct credential inputs:

- `object-storage-access-key-id`
- `object-storage-secret-access-key`
- `object-storage-bucket-name`
- `object-storage-endpoint-url`
- `object-storage-region`

Optional inputs:

- `python-version`: defaults to `3.12`.
- `backup-prefix`: defaults to `github-backups`.
- `bundle-name`: defaults to `repo.bundle`.
- `vbase-common-ref`: defaults to `v0.1.3` in Bitwarden mode.
- `bitwarden-org-id`: defaults to the vBase Bitwarden organization id.

The action must never log secret values. Bitwarden project values are available
only to the child backup process and are not exported through `GITHUB_ENV` or
step outputs. Storage credentials need permission to list, read, and write
objects under the backup prefix because each daily run reads its monthly base.
Self-hosted runners must provide AWS CLI. The action does not back up Git LFS
objects or submodule repositories.

## Reusable Workflow Contract

Required runtime secrets:

- `VBASE_COMMON_REPO_READ_TOKEN`
- `BWS_ACCESS_TOKEN`

Important inputs:

- `backup-prefix` defaults to `github-backups`.
- `bundle-name` defaults to `repo.bundle`.
- `bitwarden-project` defaults to `vbase-repo-backups`.
- `bitwarden-org-id` defaults to the vbase Bitwarden organization id.
- `vbase-common-ref` defaults to `v0.1.3`.
- `python-version` defaults to `3.12`.
- `runner` defaults to `ubuntu-latest`.

Object storage credentials are read from the configured Bitwarden project only
inside the shared action's backup process. Bucket lifecycle rules, credential
provisioning, and quarterly restore tests are separate operational tasks
outside this reusable workflow.
