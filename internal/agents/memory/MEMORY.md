# Agent Memory

## Repository Purpose

`vbase-github-actions` is the central home for shared validityBase GitHub
Actions and reusable workflows.

## Design Decisions

- Reusable workflows are preferred for full processes such as Python CI,
  linting, E2E tests, coverage, documentation publication, repo backups, and
  deployments.
- Composite actions are used for focused reusable operations.
- Composite actions currently live under `.github/actions/<name>/action.yml`.
- `setup-python-deps` keeps `require-hashes` disabled by default for backwards
  compatibility; migrated repositories opt in with `require-hashes: true`.
- Python dependency hash migration guidance lives in
  `internal/specs/python-dependency-hashes.md`.
- Secrets are always supplied by caller repositories; this repo must not store
  secret values.
- Downstream repositories should consume reviewed release refs such as `@v1` or
  full commit SHAs, based on policy.
- Repository backup logic lives in `.github/actions/repo-backup`; the public
  reusable workflow is `.github/workflows/repo-backup.yml`. Caller repos own
  schedules and pass the project-scoped Bitwarden token; the workflow resolves
  S3-compatible object storage credentials at runtime and uploads through AWS
  CLI against the configured endpoint.
- Internal specs and memory live under `internal/`; root `CLAUDE.md` and
  `AGENTS.md` stay small and point here.

## Current Shared Actions

- `.github/actions/setup-python-deps/action.yml`
- `.github/actions/setup-node-deps/action.yml`
- `.github/actions/setup-cypress-deps/action.yml`
- `.github/actions/notifications/action.yml`
- `.github/actions/publish-docs/action.yml`
- `.github/actions/repo-backup/action.yml`

## Current Reusable Workflows

- `.github/workflows/publish-docs.yml`
- `.github/workflows/python-lint.yml`
- `.github/workflows/repo-backup.yml`
