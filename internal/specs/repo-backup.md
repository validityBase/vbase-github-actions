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

The caller uses the reviewed `@v1` release line for the same reason consumer
repositories do: centrally reviewed fixes should roll forward without
per-repository pin updates.

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
- creates a full-history git bundle;
- verifies the bundle;
- writes `repo.bundle.sha256`;
- writes `metadata.json`;
- smoke-tests restore with `git clone <bundle>` and `git fsck --strict`;
- uploads the bundle, checksum, and metadata with AWS CLI against the configured
  S3-compatible endpoint.

This keeps credential loading, backup generation, and upload behavior in one
shared action implementation while the reusable workflow owns only checkout
and caller-facing orchestration.

## Backup Object Layout

Backups are uploaded under:

```text
<backup-prefix>/<owner>/<repo>/YYYY/MM/DD/<timestamp>-<run-id>-<attempt>/
```

The object set contains the git bundle, checksum, and metadata.

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
- `vbase-common-ref`: defaults to `v0.1.2` in Bitwarden mode.
- `bitwarden-org-id`: defaults to the vBase Bitwarden organization id.

The action must never log secret values. Bitwarden project values are available
only to the child backup process and are not exported through `GITHUB_ENV` or
step outputs. Self-hosted runners must provide AWS CLI. The action does not back
up Git LFS objects or submodule repositories.

## Reusable Workflow Contract

Required runtime secrets:

- `VBASE_COMMON_REPO_READ_TOKEN`
- `BWS_ACCESS_TOKEN`

Important inputs:

- `backup-prefix` defaults to `github-backups`.
- `bundle-name` defaults to `repo.bundle`.
- `bitwarden-project` defaults to `vbase-repo-backups`.
- `bitwarden-org-id` defaults to the vbase Bitwarden organization id.
- `vbase-common-ref` defaults to `v0.1.2`.
- `python-version` defaults to `3.12`.
- `runner` defaults to `ubuntu-latest`.

Object storage credentials are read from the configured Bitwarden project only
inside the shared action's backup process. Bucket lifecycle rules, credential
provisioning, and quarterly restore tests are separate operational tasks
outside this reusable workflow.
