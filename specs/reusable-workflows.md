# Reusable Workflows

Reusable workflows live under `.github/workflows/` and should be preferred for
full CI/CD processes.

Planned reusable workflow candidates:
- `publish-docs.yml`
- `python-ci.yml`
- `python-lint.yml`
- `e2e-tests.yml`
- `coverage.yml`
- `deploy-ecs-service.yml`
- `deploy-lambda.yml`

Reusable workflows should expose stable, minimal inputs and accept caller
secrets explicitly or through `secrets: inherit` only when the workflow is
trusted for the consuming repository.

Example consumption pattern:

```yaml
jobs:
  ci:
    uses: validityBase/vbase-github-actions/.github/workflows/python-ci.yml@v1
    with:
      python-version: "3.11"
      requirements-files: |
        requirements-dev.txt
    secrets: inherit
```

Reusable workflows must avoid printing secrets, generated `.env` files, or
private configuration payloads.

## publish-docs.yml

`publish-docs.yml` standardizes the common documentation publishing skeleton:

- checkout caller repository;
- optionally set up Node.js;
- optionally set up Python and install requirements;
- optionally run a caller-provided docs generation command using
  `pre-publish-shell`;
- publish docs through `.github/actions/publish-docs`.

The workflow intentionally does not hardcode Sphinx, TypeDoc, MSBuild,
Widdershins, or repository-specific patch commands. Those vary across
repositories and are passed through `pre-publish-command`.
Supported `pre-publish-shell` values are `bash`, `sh`, `pwsh`, `powershell`,
and `cmd`.
It accepts `DOCS_REPO_ACCESS_TOKEN` as a required secret and
`VBASE_COMMON_REPO_READ_TOKEN` as an optional secret for private Python
dependencies.

Known local workflow variants:
- Sphinx builds from `docs/` to `docs/_build/markdown`;
- TypeDoc builds from TypeScript to `_docs`;
- C# docs require MSBuild plus a repository-local markdown patch script;
- `vbase-django-tools` generates OpenAPI markdown on Windows before publishing;
- some sample repositories publish existing `docs/` without a build step.
