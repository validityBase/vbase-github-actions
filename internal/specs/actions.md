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

## setup-node-deps

Sets up Node.js, enables `actions/setup-node` built-in npm caching, validates
the package lockfile, and installs dependencies with `npm ci`.

Optional inputs:
- `node-version`: defaults to `20`.
- `package-lock-path`: defaults to `package-lock.json`.
- `working-directory`: defaults to `.`.
- `npm-ci-args`: optional additional arguments passed to `npm ci`.

The action validates that `working-directory` exists and that
`working-directory/package-lock.json` exists and is readable before npm cache
setup and install. `package-lock-path` is retained as a compatibility input, but
it must reference the same lockfile that `npm ci` will use. The npm cache key is
tied to `working-directory/package-lock.json`.

It must not cache `node_modules`; `npm ci` removes and recreates that directory.
The action parses `npm-ci-args` as shell-style arguments and invokes `npm ci`
with an array expansion so quoted values are preserved and glob patterns are not
expanded by the shell.

## setup-cypress-deps

Sets up Node.js, enables npm cache through `actions/setup-node`, caches the
Cypress binary through `actions/cache`, installs npm dependencies, and verifies
or installs Cypress.

Optional inputs:
- `node-version`: defaults to `24`.
- `cypress-cache-key-suffix`: defaults to `v2`.

The action assumes `package-lock.json` is in the caller repository root. It does
not cache `node_modules` because `npm ci` removes and recreates it.

The action validates that `package-lock.json` exists and is readable before any
cache keys are evaluated. Cypress must come from the caller lockfile; the action
runs `./node_modules/.bin/cypress` instead of `npx cypress`, verifies the cached
binary, installs it if needed, and verifies it again.

## notifications

Sends workflow notifications without embedding repository secrets.

The action uses `vbase_common.notifications.notifiers.send_notification()`.
Delivery to Slack, email, or both is controlled by the caller-provided
`VBASE_NOTIFICATIONS_JSON_DESCRIPTOR` value.

Caller-provided secrets:
- `VBASE_NOTIFICATIONS_JSON_DESCRIPTOR` for Slack/email configuration.
- `VBASE_COMMON_REPO_READ_TOKEN` for installing `vbase-common`.

Required inputs:
- `title`
- `message`

Optional inputs:
- `notification-level`: defaults to `NONPRD`.
- `metadata-json`: JSON object, defaults to `{}`.
- `recipients-json`: JSON array, defaults to `[]`.
- `vbase-common-ref`: defaults to `main`.

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
but `node_modules` must not be committed. Runtime dependencies should pass
`npm audit --omit=dev`; after changing TypeScript source or package
dependencies, rebuild and commit the bundled `index.js`.

## repo-backup-b2

Creates and uploads restore-friendly repository backups to Backblaze B2.

Required inputs:
- `b2-key-id`
- `b2-application-key`
- `b2-bucket-name`

Optional inputs:
- `backup-prefix`: defaults to `github-backups`.
- `bundle-name`: defaults to `repo.bundle`.

The caller repository must already be checked out before this action runs. The
action fetches all branch and tag refs, creates a full-history `git bundle`,
verifies the bundle, writes `repo.bundle.sha256`, writes `metadata.json`, and
smoke-tests restore with `git clone <bundle>` followed by `git fsck --strict`.

The action uploads the bundle, checksum, and metadata to:

```text
<backup-prefix>/<owner>/<repo>/YYYY/MM/DD/<timestamp>-<run-id>-<attempt>/
```

The implementation intentionally uses the Backblaze B2 Native API through the
Python standard library. It avoids runtime dependency installation and avoids a
third-party upload action in the production backup path. B2 credential values
must be resolved by the caller's approved secret-management process, passed as
action inputs at runtime, and never logged. The action does not back up Git LFS
objects or submodule repositories.
