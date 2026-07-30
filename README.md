# vbase-github-actions

Shared GitHub Actions for validityBase repositories.

## Actions

### setup-python-deps

Sets up Python, restores pip cache through `actions/setup-python`, validates one
or more requirements files, and installs them in order.

```yaml
- name: Set up Python and install dependencies
  uses: validityBase/vbase-github-actions/.github/actions/setup-python-deps@v1
  with:
    requirements-files: |
      requirements-dev.txt
    python-version: "3.12"
```

For multiple requirements files, list one file per line:

```yaml
with:
  requirements-files: |
    docs/requirements.txt
    requirements.txt
  python-version: "3.11"
```

Hashed lock files can opt in to pip hash-checking mode:

```yaml
- name: Set up Python and install hashed dependencies
  uses: validityBase/vbase-github-actions/.github/actions/setup-python-deps@v1
  with:
    requirements-files: |
      requirements.txt
    python-version: "3.11"
    require-hashes: true
```

`require-hashes` defaults to `false` so existing repositories continue to work.
When it is `true`, each listed requirements file is installed with
`python -m pip install --require-hashes -r <file>`. Prefer passing one generated
lock file per job, for example `requirements-dev.txt`; if multiple files are
listed, each file must be independently installable in hash-checking mode.
See `internal/specs/python-dependency-hashes.md` for the migration pattern.

### run-with-bitwarden-env

Loads one Bitwarden project through the already installed `bw-sm` package and
runs a command with those values in process environment. The action masks the
Bitwarden access token; masking loaded project secret values is delegated to
`bw_sm.env`.

```yaml
- name: Run E2E tests with Bitwarden env
  uses: validityBase/vbase-github-actions/.github/actions/run-with-bitwarden-env@v1
  with:
    project: vbase-django-tools-cypress-runner-stg
    bitwarden-access-token: ${{ secrets.VBASE_DJANGO_TOOLS_CYPRESS_RUNNER_STG_TOKEN }}
    command: |
      python -m unittest discover -s tests -v
```

Use `project-id` instead of `project` when the workflow should avoid resolving
by name. Install `bw-sm` and `bitwarden-sdk` through normal locked/private
Python requirements before this action. The action keeps Bitwarden secrets
scoped to the command step instead of exporting them to later workflow steps.

### setup-node-deps

Sets up Node.js, restores the npm cache through `actions/setup-node`, validates
the caller's lockfile, and installs dependencies with
`npm ci --ignore-scripts`.

```yaml
- name: Set up Node.js and install dependencies
  uses: validityBase/vbase-github-actions/.github/actions/setup-node-deps@v2
  with:
    node-version: "20"
    package-lock-path: package-lock.json
```

`node-version` defaults to `20`, `package-lock-path` defaults to
`package-lock.json`, and `working-directory` defaults to the repository root.
Use `working-directory` plus a matching `package-lock-path` for projects whose
Node package lives in a subdirectory. Use `npm-ci-args` for repository-specific
install flags such as `--prefer-offline --no-audit --no-fund`. Install-time
lifecycle scripts are always disabled; run any trusted setup step explicitly.
`npm-ci-args` must not contain `--` or configure `ignore-scripts`.

### setup-cypress-deps

Sets up Node.js, enables npm cache, caches the Cypress binary, installs npm
dependencies with `npm ci --ignore-scripts`, and explicitly verifies or installs
Cypress from the caller's lockfile.

```yaml
- name: Install NPM dependencies and Cypress
  uses: validityBase/vbase-github-actions/.github/actions/setup-cypress-deps@v2
  with:
    node-version: "24"
```

`node-version` defaults to `24`. Repositories that have not yet validated Node
24 can pass their current version explicitly, for example `node-version: "18"`.
The caller repository must have a readable `package-lock.json` in its root.
The optional `cypress-cache-key-suffix` input defaults to `v2` and can be bumped
when the Cypress binary cache needs to be invalidated.

### notifications

Sends workflow notifications through `vbase_common.notifications.notifiers`.
Slack, email, or Slack+email delivery is configured by the caller-provided
`VBASE_NOTIFICATIONS_JSON_DESCRIPTOR` secret.

```yaml
- name: Send failure notification
  uses: validityBase/vbase-github-actions/.github/actions/notifications@v1
  env:
    VBASE_NOTIFICATIONS_JSON_DESCRIPTOR: ${{ secrets.VBASE_NOTIFICATIONS_JSON_DESCRIPTOR }}
    VBASE_COMMON_REPO_READ_TOKEN: ${{ secrets.VBASE_COMMON_REPO_READ_TOKEN }}
  with:
    title: "Workflow failed"
    message: |
      Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
    notification-level: NONPRD
    metadata-json: |
      {"workflow":"example"}
```

`notification-level` supports `NONPRD`, `PRD`, and `PRD_CRITICAL`. Delivery and
routing are handled by `vbase-common` using the descriptor supplied by the
caller. Email recipients are read from the descriptor and may be extended with
`recipients-json`.

### publish-docs

Publishes Markdown documentation from a product repository into the central docs
repository. Prefer the reusable `publish-docs.yml` workflow for full docs
publishing jobs. Use this direct action only when the caller workflow needs to
own checkout, build, or setup steps itself.

```yaml
- name: Publish Documents
  uses: validityBase/vbase-github-actions/.github/actions/publish-docs@v1
  with:
    docs-repo-access-token: ${{ secrets.DOCS_REPO_ACCESS_TOKEN }}
    source-docs-path: docs
    target-repository-branch: main
```

The action can optionally preprocess PlantUML diagrams and rewrite absolute
GitHub repository links for the central documentation repository. If the target
docs repository should always publish to `main`, pass
`target-repository-branch: main`; otherwise the action defaults to the current
product branch name.

### validate-docs-against-product-sources

Monitors commits to a product repository and reports which documentation files
in the calling repo have become inaccurate, using an OpenAI LLM for analysis.
The calling workflow must check out the docs repo before invoking this action so
that `doc-map.json` and the doc files are accessible.

```yaml
- name: Validate docs against product sources
  uses: validityBase/vbase-github-actions/.github/actions/validate-docs-against-product-sources@v1
  with:
    mode: from_last_run
    product-repo: acme/my-library
    product-repo-pat: ${{ secrets.PRODUCT_REPO_PAT }}
    openai-api-key: ${{ secrets.OPENAI_API_KEY }}
```

`mode` controls the commit window to analyse. Supported values: `fresh_check`,
`from_last_run`, `last_1_week`, `last_1_month`, `last_2_months`,
`last_3_months`, `last_5_months`, `last_6_months`, `last_1_year`,
`last_2_years`. `from_last_run` (the default) uses the last successful run of
the calling workflow as the cursor — pass the calling workflow's filename
through `workflow-filename` (default `doc-sync.yml`).

`openai-model` defaults to `gpt-4o`. `python-version` defaults to `3.11`.

`doc-map-path` (default `doc-map.json`) points to a JSON file in the calling
repo that maps repo-relative doc and sample paths to the product API symbols
they cover. This file grounds the LLM analysis.

`exclude-files` is a comma-separated list of repo-relative files the LLM must
not suggest changes to (default `README.md,CONTRIBUTING.md`). Extend it for
auto-generated or non-content files:

```yaml
with:
  mode: from_last_run
  product-repo: acme/my-library
  product-repo-pat: ${{ secrets.PRODUCT_REPO_PAT }}
  openai-api-key: ${{ secrets.OPENAI_API_KEY }}
  exclude-files: "README.md,CONTRIBUTING.md,docs/conf.py,docs/index.rst"
  workflow-filename: doc-sync.yml
```

`product-repo-pat` is optional for public repositories; the action falls back
to `GITHUB_TOKEN` (authenticated, higher rate limits than anonymous access).

### repo-backup

Creates a full-history git bundle for the checked-out caller repository,
verifies the bundle, writes checksum and metadata files, smoke-tests restore,
and uploads all backup artifacts to a private S3-compatible object storage
bucket.

Prefer the reusable `repo-backup.yml` workflow for production repository
backups. Use this direct action only when the caller workflow needs to own
checkout or orchestration itself.

```yaml
- name: Create and upload repo backup
  uses: validityBase/vbase-github-actions/.github/actions/repo-backup@<reviewed-ref>
  with:
    backup-prefix: github-backups
    bundle-name: repo.bundle
    object-storage-access-key-id: ${{ env.OBJECT_STORAGE_ACCESS_KEY_ID }}
    object-storage-secret-access-key: ${{ env.OBJECT_STORAGE_SECRET_ACCESS_KEY }}
    object-storage-bucket-name: ${{ env.OBJECT_STORAGE_BUCKET_NAME }}
    object-storage-endpoint-url: ${{ env.OBJECT_STORAGE_ENDPOINT_URL }}
    object-storage-region: ${{ env.OBJECT_STORAGE_REGION }}
```

The action is secret-source agnostic. Resolve the object storage credential
values from the caller repository's approved secret-management process before
this step, then pass them as the `object-storage-*` inputs.

Replace `<reviewed-ref>` with a full commit SHA or release tag that includes
`repo-backup`.

The action uploads:
- `repo.bundle`
- `repo.bundle.sha256`
- `metadata.json`

Objects are written under:

```text
<backup-prefix>/<owner>/<repo>/YYYY/MM/DD/<timestamp>-<run-id>-<attempt>/
```

The action uploads through AWS CLI's `aws s3 cp` command pointed at the
configured S3-compatible endpoint. The public inputs stay provider-independent;
self-hosted runners must have AWS CLI installed before using the action.

## Release Policy

Downstream repositories should reference this repository through reviewed
release refs such as `@v1` or full commit SHAs, depending on the repository's
security policy.

Breaking changes require a new major release ref such as `@v2`.
Use `@v2` for Node dependency setup actions that enforce
`npm ci --ignore-scripts`; this is a breaking hardening change for callers that
previously relied on install-time lifecycle scripts.

This repository is public. Do not commit secret values, webhook URLs, private
tokens, or repository-specific private configuration. Sensitive values must be
resolved by caller workflows at runtime.

## Reusable Workflows

### python-lint

Reusable workflow for Python pylint jobs that share checkout, Python setup,
requirements installation, and a final pylint command.

```yaml
jobs:
  run-pylint:
    uses: validityBase/vbase-github-actions/.github/workflows/python-lint.yml@v1
    with:
      python-version: "3.11"
      requirements-files: |
        requirements/dev.txt
      pylint-command: pylint --fail-under=8.0 $(git ls-files '*.py')
    secrets:
      PRIVATE_GITHUB_TOKEN: ${{ secrets.VBASE_COMMON_REPO_READ_TOKEN }}
```

Pass `PRIVATE_GITHUB_TOKEN` when requirements install private GitHub
dependencies. The workflow configures `~/.netrc` and also exposes the token as
`VBASE_COMMON_REPO_READ_TOKEN` and `VBASE_REPO_READ_TOKEN` for existing
requirements files that use environment substitution.
`require-hashes` defaults to `false`; set it to `true` after the caller
repository has migrated the selected requirements file to a generated hashed
lock file:

```yaml
with:
  requirements-files: |
    requirements-dev.txt
  require-hashes: true
```

### publish-docs

Reusable workflow for docs publishing jobs that share the same checkout,
optional dependency setup, optional docs build command, and central docs publish
step.

```yaml
jobs:
  update-main-docs:
    uses: validityBase/vbase-github-actions/.github/workflows/publish-docs.yml@v1
    with:
      python-version: "3.11"
      requirements-files: |
        docs/requirements.txt
      pre-publish-command: |
        sphinx-build -b markdown docs/ docs/_build/markdown
      pre-publish-shell: bash
      source-docs-path: docs/_build/markdown
      target-repository-branch: main
    secrets:
      DOCS_REPO_ACCESS_TOKEN: ${{ secrets.DOCS_REPO_ACCESS_TOKEN }}
```

For repositories with custom docs generation, put that logic in
`pre-publish-command` and pass the generated directory through
`source-docs-path`. If docs requirements need private `vbase-common` access,
also pass `VBASE_COMMON_REPO_READ_TOKEN` in the workflow `secrets` mapping.
For migrated docs lock files, pass `require-hashes: true`.
Use `pre-publish-shell: pwsh` for Windows PowerShell commands.
Supported `pre-publish-shell` values are `bash`, `sh`, `pwsh`, `powershell`,
and `cmd`.

### repo-backup

Reusable workflow for daily or manual production repository backups to
S3-compatible object storage. The schedule lives in the caller repository; this
workflow holds the shared backup implementation.

```yaml
name: Daily repo backup

on:
  schedule:
    - cron: "17 2 * * *"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  backup:
    uses: validityBase/vbase-github-actions/.github/workflows/repo-backup.yml@<reviewed-ref>
    with:
      backup-prefix: github-backups
      bundle-name: repo.bundle
      bitwarden-project: vbase-repo-backups
    secrets:
      VBASE_COMMON_REPO_READ_TOKEN: ${{ secrets.VBASE_COMMON_REPO_READ_TOKEN }}
      BWS_ACCESS_TOKEN: ${{ secrets.VBASE_REPO_BACKUP_SECRETS_TOKEN }}
```

The reusable workflow backs up Git history through the shared `repo-backup`
action. Git LFS objects and submodule repositories need separate backup
coverage if a production repository uses them. Bucket lifecycle rules and
quarterly restore-test scheduling are managed outside this workflow.

`VBASE_COMMON_REPO_READ_TOKEN` is used only to install `vbase-common`.
`BWS_ACCESS_TOKEN` is the Bitwarden machine access token for the backup project.
The Bitwarden project must contain `OBJECT_STORAGE_ACCESS_KEY_ID`,
`OBJECT_STORAGE_SECRET_ACCESS_KEY`, `OBJECT_STORAGE_BUCKET_NAME`,
`OBJECT_STORAGE_ENDPOINT_URL`, and `OBJECT_STORAGE_REGION`.

Replace `<reviewed-ref>` with a full commit SHA or release tag that includes
`repo-backup`.
