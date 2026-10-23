# Python releases

These components prepare a reviewed Release PR, tag its merged commit, build
validated distributions, publish through the caller's trusted publisher, and
create a GitHub Release from the validated changelog notes.

## Components

| Component | Purpose |
| --- | --- |
| `prepare-python-release.yml` | Read the current version, apply a patch/minor/major increment, finalize existing Unreleased entries, and open a Release PR |
| `tag-python-release.yml` | Handle merged release PRs, push the matching tag, and dispatch the caller's publication workflow |
| `build-python-release.yml` | Validate the tag/source/changelog, build and inspect wheel/sdist metadata, and store distributions and release notes as artifacts |
| `github-python-release.yml` | Create the GitHub Release from the notes artifact after publication succeeds |
| `python-release/action.yml` | Focused prepare/validate helper using Python's standard library |
| `publish-python-release/action.yml` | Download the validated distributions and upload them using OIDC in a caller-owned job |

Workflows live in `.github/workflows/`; actions live in `.github/actions/`.
The caller owns event triggers, permissions, and the `pypi` environment. A
maintainer may need to approve workflows on the bot-created PR. Merging its
reviewed Release PR authorizes publication.

Maintainer steps are kept in the shared
[release runbook](../../../RELEASE_MANAGEMENT.md); package repositories link
to that runbook and supply their own settings.

## Configuration

Required workflow inputs:

- `version-file`: caller-relative Python file with a literal `__version__`.
- `bump`: `patch`, `minor`, or `major`, for preparation only.
- `package-name`: expected PyPI name, for distribution builds only.

Optional inputs are exposed only by the workflows that use them:

| Input | Default |
| --- | --- |
| `changelog-file` | `CHANGELOG.md` |
| `default-branch` | `main` |
| `release-branch-prefix` | `release/` |
| `tag-prefix` | `v` |
| `python-version` | `3.12` |
| `runner` | `ubuntu-24.04` (Linux is required for publishing) |
| `release-tools-ref` | `v1` |
| `commit-author-name` | `github-actions[bot]` |
| `commit-author-email` | `41898282+github-actions[bot]@users.noreply.github.com` |
| `publish-workflow` | `publish-pypi.yml` |
| `dist-dir` | `dist` |
| `artifact-name` | `python-package-distributions` |
| `notes-artifact-name` | `python-release-notes` |
| `build-requirements` | `build twine` (space-separated tool requirements, optionally versioned) |

The default commit email is GitHub's public Actions bot identity, not a personal
account or credential. Override the author inputs to use another service
identity. Adjust caller event filters as well when changing a branch or tag
prefix; event filters are defined in the caller's workflow.

When pinning a reusable workflow to a full SHA, pass that **same SHA** as
`release-tools-ref`. Reusable workflows check out the caller repository by
default, so they separately check out this repository to run its helper action.
Using matching refs prevents a new workflow from running older helper code.
Production consumers may instead use a reviewed release ref such as `v1` for
both values after the new components are available on that release line.

## Caller example

```yaml
name: Prepare release
on:
  workflow_dispatch:
    inputs:
      bump:
        type: choice
        required: true
        options: [patch, minor, major]
permissions:
  contents: write
  pull-requests: write
jobs:
  prepare:
    uses: validityBase/vbase-github-actions/.github/workflows/prepare-python-release.yml@v1
    with:
      version-file: src/example_package/_version.py
      bump: ${{ inputs.bump }}
```

Do not add a caller concurrency group identical to the reusable prepare/tag
workflow's group: both levels would compete for the same lock.

## Trusted publishing

Keep the upload job in the caller workflow registered with PyPI. PyPI does not
currently support a reusable workflow as the Trusted Publisher. This composite
action executes inside the caller's upload job and preserves that identity:

```yaml
publish-to-pypi:
  needs: build
  runs-on: ubuntu-24.04
  environment:
    name: pypi
    url: https://pypi.org/p/example-package
  permissions:
    id-token: write
    actions: read
  steps:
    - uses: validityBase/vbase-github-actions/.github/actions/publish-python-release@v1
```

The preceding build job calls `build-python-release.yml`; the following release
job calls `github-python-release.yml` with `needs: publish-to-pypi`. Preserve
these dependencies: a failed upload must not create a GitHub Release. Do not
move the upload into a reusable workflow or add a static PyPI token.

## Validation

```bash
python -m unittest discover -s .github/actions/python-release/tests -v
```

Tests cover both `src/vbase_api/_version.py` and `vbase/_version.py` layouts,
alternate changelog paths/tag prefixes, component resets, unchanged files on
invalid input, path escapes, and wheel/sdist metadata matching. Preparation
requires real entries under Unreleased. User impact is reviewed by maintainers;
the helper does not infer it from arbitrary prose or commit messages.
The open-PR guard checks every page, ignores fork heads and missing head
repositories, and blocks only release branches in the caller repository.
