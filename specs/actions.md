# Shared Actions

Shared composite actions live under `.github/actions/<action-name>/action.yml`.

## setup-python-deps

Sets up Python, enables `actions/setup-python` built-in pip caching, validates
requirements files, and installs them in order.

Required input:
- `requirements-files`: newline-separated requirements files.

Optional input:
- `python-version`: defaults to `3.11`.

The action must not implement custom pip cache key calculation. It delegates pip
caching to `actions/setup-python` with `cache: pip` and `cache-dependency-path`.

## notifications

Sends workflow notifications without embedding repository secrets.

Supported providers:
- `vbase-common`: uses `vbase_common.notifications.notifiers`.
- `slack-webhook`: posts a simple text payload to a caller-provided Slack
  webhook URL.

Caller-provided secrets:
- `VBASE_NOTIFICATIONS_JSON_DESCRIPTOR` for `vbase-common`.
- `VBASE_COMMON_REPO_READ_TOKEN` for installing `vbase-common`.
- `SLACK_WEBHOOK_URL` for direct Slack webhook sends.

The action must not log secret values or notification descriptors.

## publish-docs

Publishes Markdown documentation from a product repository into the central docs
repository.

Required input:
- `docs-repo-access-token`.

Optional inputs:
- `source-docs-path`
- `target-docs-path`
- `target-repository`
- `target-repository-branch`
- `preprocess-plant-uml`
- `resolve-absolute-links-repos`

The action is a Node 24 action and runs the checked-in bundled `index.js`.
Source TypeScript and package files are kept with the action for maintenance,
but `node_modules` must not be committed.
