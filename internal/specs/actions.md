# Shared Actions

Shared composite actions live under `.github/actions/<action-name>/action.yml`.

## setup-python-deps

Sets up Python, enables `actions/setup-python` built-in pip caching, validates
requirements files, and installs them in order.

Required input:
- `requirements-files`: newline-separated requirements files.

Optional input:
- `python-version`: defaults to `3.11`.
- `require-hashes`: defaults to `false`. When `true`, every requirements file is
  installed with `python -m pip install --require-hashes -r <file>`.

The action must not implement custom pip cache key calculation. It delegates pip
caching to `actions/setup-python` with `cache: pip` and `cache-dependency-path`.

`require-hashes` is deliberately opt-in so existing repositories that still use
ordinary requirements files continue to work on the `@v1` release line. Migrated
repositories should pass a generated lock file produced by `pip-compile --generate-hashes`.
Prefer one installable lock file per job, such as `requirements-dev.txt`; if
multiple files are listed, each file must satisfy pip hash-checking mode on its
own.

## run-with-bitwarden-env

Runs one caller-provided bash command with the selected Bitwarden project
loaded into that process environment through `python -m bw_sm.env` from the
already installed `bw-sm` package.

Required inputs:
- `command`: bash command to execute.
- `bitwarden-access-token`: project-scoped Bitwarden machine access token.

Project selector inputs:
- `project`: Bitwarden project name.
- `project-id`: Bitwarden project id.

At least one project selector is required.

Optional inputs:
- `org-id`: defaults to the vBase Bitwarden organization id.
- `token-env`: defaults to `BWS_ACCESS_TOKEN`.
- `backend`: defaults to `api`.
- `working-directory`: defaults to `.`.

Caller workflows should install `bw-sm` and `bitwarden-sdk` through normal
locked/private Python requirements before using the default `api` backend. The
action must not export Bitwarden secrets through `$GITHUB_ENV`; secrets stay
scoped to the command process. The composite action must mask the Bitwarden
access token; `bw_sm.env` is responsible for masking loaded secret values before
running the caller command.

## setup-node-deps

Sets up Node.js, enables `actions/setup-node` built-in npm caching, validates
the package lockfile, and installs dependencies with
`npm ci --ignore-scripts`.

This hardened behavior is a breaking change from the `@v1` action contract and
must be published under a new major release ref such as `@v2`.

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
expanded by the shell. `--ignore-scripts` is always added so dependency
install-time lifecycle scripts do not run implicitly in CI. `npm-ci-args` must
not contain `--`, `--ignore-scripts`, `--ignore-scripts=...`, or
`--no-ignore-scripts`, because callers must not be able to override this
security control.

## setup-cypress-deps

Sets up Node.js, enables npm cache through `actions/setup-node`, caches the
Cypress binary through `actions/cache`, installs npm dependencies with
`npm ci --ignore-scripts`, and verifies or installs Cypress explicitly.

This hardened behavior is a breaking change from the `@v1` action contract and
must be published under a new major release ref such as `@v2`.

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

## repo-backup

Creates and uploads restore-friendly repository backups to a backup bucket
through the S3-compatible object storage API.

Required inputs:
- `object-storage-access-key-id`
- `object-storage-secret-access-key`
- `object-storage-bucket-name`
- `object-storage-endpoint-url`
- `object-storage-region`

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

The implementation uploads with AWS CLI's `aws s3 cp` command against the
configured S3-compatible endpoint, while keeping the action inputs
provider-independent. Object storage credential values must be resolved by the
caller's approved secret-management process, passed as action inputs at runtime,
and never logged. Self-hosted runners must provide AWS CLI. The action does not
back up Git LFS objects or submodule repositories.
