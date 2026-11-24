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

## regenerate-dependabot-locks.yml

Opt-in repair for duplicate hashes in pip-compile locks. A maintainer with
repository write access adds `regenerate-locks` to an open, same-repository
Dependabot pip PR. The caller listens for `pull_request_target: labeled` and
grants `contents: write` and `pull-requests: read`. No caller secrets are
required. To retry, remove and
reapply the label.

- `lock-files`: space-separated basenames for matching
  `requirements/<name>.in` and `.txt` files.
- `repair-paths`: alternative to `lock-files` for repository-relative paths
  to pip-compile-generated `.txt` locks. This mode removes duplicate hash
  rows from allowlisted locks modified by the PR without invoking pip-compile
  or checking out PR files. Existing lock validation in the caller's CI
  still checks the result.
- `allow-unsafe-lock-files`: subset compiled with `--allow-unsafe`.
- `python-version` and `tooling-lock`: Python version and hash-locked tooling
  basename under `requirements/`; default to `3.11` and `tools`.
- `compile-profile`: `standard` (default), or `linux-wheel-cp311` for the
  binary-only manylinux2014 x86-64 / CPython 3.11 settings used by the pilot.

Compilation has no write credentials. Only the separate publish job can
write with the built-in `GITHUB_TOKEN`. It does not
check out the PR. It loads its validator from the reusable workflow's own
commit and only commits a result that exactly matches deleting
duplicate SHA-256 entries from the event head's locks. In the Linux profile it
may also restore the `--only-binary :all:` header option if the base lock
already has it. That option alone never triggers a commit. A moved head,
missing label, or wider diff prevents the commit. After the commit, a
maintainer may need to approve the resulting PR check runs. Push-triggered
workflows do not run for commits made with `GITHUB_TOKEN`. Neither behavior
changes the PR's merge approval requirements.

The regeneration job uses the pinned Python setup action directly because
`setup-python-deps` enables a shared pip cache. Do not enable a shared
cache for dependency resolution based on pull request files.

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
This repository's scheduled/manual self-backup caller is
`.github/workflows/daily-repo-backup.yml`.
