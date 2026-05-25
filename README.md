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

### setup-node-deps

Sets up Node.js, restores the npm cache through `actions/setup-node`, validates
the caller's lockfile, and installs dependencies with `npm ci`.

```yaml
- name: Set up Node.js and install dependencies
  uses: validityBase/vbase-github-actions/.github/actions/setup-node-deps@v1
  with:
    node-version: "20"
    package-lock-path: package-lock.json
```

`node-version` defaults to `20`, `package-lock-path` defaults to
`package-lock.json`, and `working-directory` defaults to the repository root.
Use `working-directory` plus a matching `package-lock-path` for projects whose
Node package lives in a subdirectory. Use `npm-ci-args` for repository-specific
install flags such as `--prefer-offline --no-audit --no-fund`.

### setup-cypress-deps

Sets up Node.js, enables npm cache, caches the Cypress binary, installs npm
dependencies with `npm ci`, and verifies or installs Cypress from the caller's
lockfile.

```yaml
- name: Install NPM dependencies and Cypress
  uses: validityBase/vbase-github-actions/.github/actions/setup-cypress-deps@v1
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
  uses: validityBase/vbase-github-actions/validate-docs-against-product-sources@v1
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

## Release Policy

Downstream repositories should reference this repository through reviewed
release refs such as `@v1` or full commit SHAs, depending on the repository's
security policy.

Breaking changes require a new major release ref such as `@v2`.

This repository is public. Do not commit secret values, webhook URLs, private
tokens, or repository-specific private configuration. Secrets must be supplied by
caller workflows.

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
Use `pre-publish-shell: pwsh` for Windows PowerShell commands.
Supported `pre-publish-shell` values are `bash`, `sh`, `pwsh`, `powershell`,
and `cmd`.
