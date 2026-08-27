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

Runs one caller-provided bash command with Bitwarden values supplied by the
already installed `bw-sm` package. The action supports two mutually exclusive
modes:

- Single-project mode loads one project's values directly into the command
  process environment.
- Env-file mode loads one or more projects into private temporary dotenv files,
  exposes each path through a caller-selected environment variable, runs the
  command, and removes all temporary files afterward.

Inputs required in both modes:

- `command`: bash command to execute.
- `working-directory`: defaults to `.` and must identify an existing directory.

Single-project mode inputs:

- `bitwarden-access-token`: project-scoped Bitwarden machine access token.
- At least one of `project` or `project-id` must identify the project; callers
  should normally provide only one selector.
- `token-env`: defaults to `BWS_ACCESS_TOKEN`.

Env-file mode input:

- `projects-json`: a non-empty JSON array. Each object requires exactly one of
  `project` or `project-id`, plus `token-env` and `env-file-variable`.
- `token-env` names an environment variable supplied by the caller that holds
  that project's machine access token. Tokens are referenced by name and must
  not be embedded in `projects-json`.
- `env-file-variable` names the environment variable through which the caller
  command receives the generated dotenv file path. Values must be unique.
- Each object may override `org-id` and `backend` for its project.

Shared optional inputs:

- `org-id`: defaults to the vBase Bitwarden organization id.
- `backend`: defaults to `api`.

Caller workflows should install `bw-sm` and `bitwarden-sdk` through normal
locked/private Python requirements before using the default `api` backend. The
action must not export Bitwarden secrets or generated paths through
`$GITHUB_ENV`; they stay scoped to the command process. Generated files must be
private and must be removed whether the command succeeds or fails. The
composite action masks Bitwarden access tokens and removes env-file mode tokens
from the caller command environment; `bw_sm.env` masks loaded secret values.

Example env-file mode configuration:

```yaml
- name: Run Docker Compose with Bitwarden env files
  uses: validityBase/vbase-github-actions/.github/actions/run-with-bitwarden-env@v1
  env:
    APP_DOCKER_TOKEN: ${{ secrets.APP_DOCKER_TOKEN }}
    API_DOCKER_TOKEN: ${{ secrets.API_DOCKER_TOKEN }}
  with:
    projects-json: >-
      [
        {
          "project": "app-docker",
          "token-env": "APP_DOCKER_TOKEN",
          "env-file-variable": "APP_DOCKER_ENV_FILE"
        },
        {
          "project": "api-docker",
          "token-env": "API_DOCKER_TOKEN",
          "env-file-variable": "API_DOCKER_ENV_FILE"
        }
      ]
    command: docker compose up --abort-on-container-exit
```

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
dependencies, rebuild and commit the bundled `index.js`. The action must
handle concurrent publishers by fetching and rebasing the target branch before
retrying a rejected push only when the remote branch has advanced, with a
bounded number of attempts. If the remote already contains the local commit,
the publish is considered successful.

## repo-backup

The low-level composite action contract is canonical in
`internal/specs/repo-backup.md#composite-action-contract`.
