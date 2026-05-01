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

Sends workflow notifications without storing secrets in this repository. It can
send through `vbase-common` notification routing or directly to a Slack webhook.

Using `vbase-common`:

```yaml
- name: Send failure notification
  uses: validityBase/vbase-github-actions/.github/actions/notifications@v1
  env:
    VBASE_NOTIFICATIONS_JSON_DESCRIPTOR: ${{ secrets.VBASE_NOTIFICATIONS_JSON_DESCRIPTOR }}
    VBASE_COMMON_REPO_READ_TOKEN: ${{ secrets.VBASE_COMMON_REPO_READ_TOKEN }}
  with:
    provider: vbase-common
    title: "Workflow failed"
    message: |
      Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
    notification-level: NONPRD
    metadata-json: |
      {"workflow":"example"}
```

Using a Slack webhook:

```yaml
- name: Send Slack notification
  uses: validityBase/vbase-github-actions/.github/actions/notifications@v1
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
  with:
    provider: slack-webhook
    title: "Workflow failed"
    message: |
      Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

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
