# Repo Backup

This file is the canonical source for repository backup action and reusable
workflow behavior. Keep detailed backup context here; other docs should link to
this file instead of repeating the contract.

## Recommended Entry Point

Use `.github/workflows/repo-backup.yml` for production repository backups. The
caller repository owns scheduling, for example daily cron plus
`workflow_dispatch`, and calls this reusable workflow.

Use `.github/actions/repo-backup/action.yml` directly only when the caller
workflow needs to own checkout, credential resolution, or additional
orchestration.

## Layering

The reusable workflow and the composite action intentionally have different
responsibilities.

`.github/workflows/repo-backup.yml` is the orchestration layer:

- checks out the caller repository with full history;
- checks out `validityBase/vbase-github-actions` at the reusable workflow ref
  into `.vbase-github-actions`;
- installs `vbase-common` and the Bitwarden SDK;
- resolves object storage credentials from the configured Bitwarden project;
- invokes the shared `repo-backup` composite action with the resolved
  credentials.

`.github/actions/repo-backup/action.yml` is the implementation layer:

- expects the caller repository to already be checked out;
- fetches all branch and tag refs;
- creates a full-history git bundle;
- verifies the bundle;
- writes `repo.bundle.sha256`;
- writes `metadata.json`;
- smoke-tests restore with `git clone <bundle>` and `git fsck --strict`;
- uploads the bundle, checksum, and metadata with AWS CLI against the configured
  S3-compatible endpoint.

This keeps Bitwarden and workflow orchestration in the reusable workflow while
keeping backup generation and upload behavior in one shared action
implementation.

## Backup Object Layout

Backups are uploaded under:

```text
<backup-prefix>/<owner>/<repo>/YYYY/MM/DD/<timestamp>-<run-id>-<attempt>/
```

The object set contains the git bundle, checksum, and metadata.

## Composite Action Contract

Required inputs:

- `object-storage-access-key-id`
- `object-storage-secret-access-key`
- `object-storage-bucket-name`
- `object-storage-endpoint-url`
- `object-storage-region`

Optional inputs:

- `python-version`: defaults to `3.12`.
- `backup-prefix`: defaults to `github-backups`.
- `bundle-name`: defaults to `repo.bundle`.

The action is secret-source agnostic. Object storage credential values must be
resolved before this action runs and passed through `object-storage-*` inputs at
runtime. The action must never log secret values. Self-hosted runners must
provide AWS CLI. The action does not back up Git LFS objects or submodule
repositories.

## Reusable Workflow Contract

Required runtime secrets:

- `VBASE_COMMON_REPO_READ_TOKEN`
- `BWS_ACCESS_TOKEN`

Important inputs:

- `backup-prefix` defaults to `github-backups`.
- `bundle-name` defaults to `repo.bundle`.
- `bitwarden-project` defaults to `vbase-repo-backups`.
- `bitwarden-org-id` defaults to the vbase Bitwarden organization id.
- `vbase-common-ref` defaults to `v0.1.1`.
- `python-version` defaults to `3.12`.
- `runner` defaults to `ubuntu-latest`.

Object storage credentials are read from the configured Bitwarden project and
exposed only to later workflow steps through masked GitHub Actions environment
values. Bucket lifecycle rules, credential provisioning, and quarterly restore
tests are separate operational tasks outside this reusable workflow.
