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

`notification-level` supports `NONPRD`, `PRD`, and `PRD_CRITICAL`. The selected
level controls Slack webhook routing inside `vbase-common`; email recipients are
read from the descriptor and may be extended with `recipients-json`.

### publish-docs

Publishes Markdown documentation from a product repository into the central docs
repository.

```yaml
- name: Publish Documents
  uses: validityBase/vbase-github-actions/.github/actions/publish-docs@v1
  with:
    docs-repo-access-token: ${{ secrets.DOCS_REPO_ACCESS_TOKEN }}
    source-docs-path: docs
```

The action can optionally preprocess PlantUML diagrams and rewrite absolute
GitHub repository links for the central documentation repository.

## Release Policy

Downstream repositories should reference this repository through reviewed
release refs such as `@v1` or full commit SHAs, depending on the repository's
security policy.

Breaking changes require a new major release ref such as `@v2`.

This repository is public. Do not commit secret values, webhook URLs, private
tokens, or repository-specific private configuration. Secrets must be supplied by
caller workflows.

## Reusable Workflows

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
    secrets:
      DOCS_REPO_ACCESS_TOKEN: ${{ secrets.DOCS_REPO_ACCESS_TOKEN }}
```

For repositories with custom docs generation, put that logic in
`pre-publish-command` and pass the generated directory through
`source-docs-path`. If docs requirements need private `vbase-common` access,
also pass `VBASE_COMMON_REPO_READ_TOKEN` in the workflow `secrets` mapping.
Use `pre-publish-shell: pwsh` for Windows PowerShell commands.
