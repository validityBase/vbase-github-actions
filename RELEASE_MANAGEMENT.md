# Release management

This runbook applies to packages using the shared Python release workflows.
Each package repository's `RELEASE_MANAGEMENT.md` lists its repository, PyPI
project, import name, version file, and workflow settings.

## 1. Prepare the changelog

Add user-facing changes under `[Unreleased]` in the package's changelog through
ordinary PRs. Use Added, Changed, Deprecated, Removed, Fixed, or Security
categories, with PR references where available. Merge those PRs to the default
branch before preparing a release. Ordinary PRs do not change the package
version.

The preparation action requires at least one entry. It finalizes existing
notes; it does not infer user impact or breaking changes from commit messages.
Infrastructure-only changes should not create public package release notes.

## 2. Run Prepare release

1. Open the package repository's **Actions** page.
2. Select **Prepare release**, then **Run workflow**.
3. Select the configured default branch, normally `main`.
4. Choose the increment and run the workflow:

   | Choice | Use for | Example from 1.2.3 |
   | --- | --- | --- |
   | `patch` | Compatible bug fixes | 1.2.4 |
   | `minor` | Compatible features | 1.3.0 |
   | `major` | Breaking API changes | 2.0.0 |

The repository must allow **GitHub Actions to create and approve pull
requests** in Settings → Actions → General → Workflow permissions. Automation
uses the built-in GitHub token and does not approve or merge its own PR.

The action reads the current version from the configured version file and
opens a Release PR that changes only the version and changelog. It creates a
dated `## [X.Y.Z] - YYYY-MM-DD` section using the UTC preparation date and keeps
an empty `[Unreleased]` section above it.

Empty notes, an existing target version/branch/tag, or an open Release PR in
the same repository stop preparation. Fork PRs do not block it. Only stable
versions are supported.

## 3. Approve workflows and review

Open the generated Release PR. If GitHub displays **Approve workflows to
run**, a maintainer with write access must select it to start CI.

Review the version increment and release notes. Obtain independent review
and wait for required repository checks to pass. If changes are requested,
update the Release PR and wait for its checks again.

**Merge the reviewed Release PR only when ready to publish.** Merge authorizes
publication; a separate manual version edit or tag push is unnecessary.

## 4. Automatic publication

After merge, **Tag merged release** validates the merged commit, source
version, release branch, and changelog. It pushes the matching tag on that
commit and explicitly dispatches **Publish Python Package to PyPI** at the
tag. Bot-pushed tags do not trigger another workflow by themselves.

Publication validates and builds the wheel and source archive, checks their
package name and version, and uploads them using the package repository's
existing PyPI trusted publisher. Any configured environment approval still
applies. After PyPI succeeds, the GitHub Release is created from the validated
changelog notes.

Ordinary PRs, unmerged PRs, and fork PRs do not automatically publish. Do not
move or reuse a pushed release tag.

## 5. Verify publication

Confirm **Tag merged release** and every job in **Publish Python Package to
PyPI** succeeded. Check the package's PyPI project for the new version and
both distribution files, then check the GitHub Release's tag and notes.

Install the published package in a new environment. Replace `PYPI_PROJECT`,
`IMPORT_NAME`, and `RELEASED_VERSION` below with the package repository's
settings and the version just released:

```bash
export RELEASE_PACKAGE=PYPI_PROJECT
export RELEASE_IMPORT=IMPORT_NAME
export RELEASE_VERSION=RELEASED_VERSION
python -m venv venv/release-check
source venv/release-check/bin/activate
python -m pip install --index-url https://pypi.org/simple --no-cache-dir "${RELEASE_PACKAGE}==${RELEASE_VERSION}"
python -m pip check
python -I -c 'import importlib, importlib.metadata, os; module = importlib.import_module(os.environ["RELEASE_IMPORT"]); assert importlib.metadata.version(os.environ["RELEASE_PACKAGE"]) == os.environ["RELEASE_VERSION"]; print(module.__file__)'
deactivate
```

Use a fresh environment directory if that path already exists. The printed
module path must belong to the new environment. Isolated mode (`-I`) prevents
the repository checkout from shadowing the installed package.

## Manual publication

For an approved manual publication, use the package repository's workflow
and an existing release tag containing the release integration:

```bash
gh workflow run publish-pypi.yml --repo OWNER/REPOSITORY --ref RELEASE_TAG
```

Replace the repository and tag placeholders before running the command. Manual
runs use the same validation, and branch refs are rejected. Do not dispatch a
version that is already published to PyPI.

Configuration inputs and defaults are documented in the
[shared action contract](.github/actions/python-release/README.md).
