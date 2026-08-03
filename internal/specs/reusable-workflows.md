# Reusable Workflows

Reusable workflows live under `.github/workflows/` and should be preferred for
full CI/CD processes.

Reusable workflow roadmap:
- `publish-docs.yml` (implemented)
- `python-lint.yml` (implemented)
- `repo-backup.yml` (implemented)
- `python-ci.yml`
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

## python-lint.yml

`python-lint.yml` standardizes the common Python pylint workflow:

- checkout caller repository;
- optionally configure `~/.netrc` for private GitHub dependencies;
- set up Python and install caller requirements through
  `.github/actions/setup-python-deps`;
- run the caller-provided pylint command.

The workflow accepts an optional `PRIVATE_GITHUB_TOKEN` secret. When supplied,
the token is written only to `~/.netrc` and is also exposed as
`VBASE_COMMON_REPO_READ_TOKEN` and `VBASE_REPO_READ_TOKEN` for requirements
files that already use those environment variables.

Important inputs:
- `requirements-files` is required and supports one or more newline-separated
  requirements files.
- `require-hashes` defaults to `false`; migrated repositories can set it to
  `true` to install with pip `--require-hashes`.
- `python-version` defaults to `3.11`.
- `pylint-command` defaults to `pylint $(git ls-files '*.py')`.
- `working-directory` defaults to the repository root.

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

Important inputs:
- `requirements-files` enables shared Python dependency setup.
- `require-hashes` defaults to `false`; set it to `true` when the docs
  requirements file is a generated hashed lock file.
- `node-version` and `node-cache` enable Node.js setup when docs generation
  needs it.
- `pre-publish-command` and `pre-publish-shell` run repository-specific docs
  generation.
- `source-docs-path`, `target-docs-path`, `target-repository`, and
  `target-repository-branch` are passed through to the publish action.
- `preprocess-plant-uml` and `resolve-absolute-links-repos` control publish
  action preprocessing.

Known local workflow variants:
- Sphinx builds from `docs/` to `docs/_build/markdown`;
- TypeDoc builds from TypeScript to `_docs`;
- C# docs require MSBuild plus a repository-local markdown patch script;
- `vbase-django-tools` generates OpenAPI markdown on Windows before publishing;
- some sample repositories publish existing `docs/` without a build step.

## repo-backup.yml

The production repository backup workflow contract is canonical in
`internal/specs/repo-backup.md#reusable-workflow-contract`.
