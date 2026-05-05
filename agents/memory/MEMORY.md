# Agent Memory

## Repository Purpose

`vbase-github-actions` is the central home for shared validityBase GitHub
Actions and reusable workflows.

## Design Decisions

- Reusable workflows are preferred for full processes such as Python CI,
  linting, E2E tests, coverage, documentation publication, and deployments.
- Composite actions are used for focused reusable operations.
- Composite actions currently live under `.github/actions/<name>/action.yml`.
- Secrets are always supplied by caller repositories; this repo must not store
  secret values.
- Downstream repositories should consume reviewed release refs such as `@v1` or
  full commit SHAs, based on policy.

## Current Shared Actions

- `.github/actions/setup-python-deps/action.yml`
- `.github/actions/setup-cypress-deps/action.yml`
- `.github/actions/notifications/action.yml`
- `.github/actions/publish-docs/action.yml`

## Current Reusable Workflows

- `.github/workflows/publish-docs.yml`
