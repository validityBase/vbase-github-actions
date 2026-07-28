# Python Dependency Hashes

This repository supports the organisation-wide migration to deterministic Python
installs with pip hash-checking mode.

## Standard Pattern

Use a human-edited input file plus a generated lock file:

```text
requirements.in
requirements.txt
```

For development or documentation dependencies, keep the same pattern:

```text
requirements-dev.in
requirements-dev.txt
docs/requirements.in
docs/requirements.txt
```

Generate lock files with `pip-tools`:

```bash
python -m pip install pip-tools
pip-compile --generate-hashes -o requirements.txt requirements.in
```

For dependency updates, edit the `.in` file, regenerate the matching `.txt`
file, and review the generated diff in the pull request.

## Shared Action Support

`setup-python-deps` has a backwards-compatible `require-hashes` input. It
defaults to `false` so existing repositories continue to work on `@v1`.

Migrated repositories opt in:

```yaml
- uses: validityBase/vbase-github-actions/.github/actions/setup-python-deps@v1
  with:
    requirements-files: |
      requirements.txt
    require-hashes: true
```

When enabled, the action runs:

```bash
python -m pip install --require-hashes -r requirements.txt
```

Prefer one generated lock file per CI job, such as `requirements-dev.txt`. If a
caller lists multiple requirements files, each file must be independently
installable with `--require-hashes`.

## Reusable Workflow Support

The reusable `python-lint.yml` and `publish-docs.yml` workflows also expose
`require-hashes`, defaulting to `false`. Set it to `true` only after the caller
repository has committed generated hashed lock files.

## Lock Freshness Check

Migrated repositories should add a CI check that regenerates the lock file and
fails on a diff:

```bash
python -m pip install pip-tools
pip-compile --generate-hashes -o requirements.txt requirements.in
git diff --exit-code requirements.txt
```

Repeat the same pattern for `requirements-dev.txt`, `docs/requirements.txt`, or
other generated lock files.

## Git and Private Dependencies

Hash-checking mode is strongest for packages installed from package indexes or
prebuilt artifacts. Repositories that currently depend on mutable VCS refs such
as `git+https://...@main` need a separate migration plan before they can get the
full benefit:

- publish the dependency as a package or wheel;
- use a private package index or reviewed wheelhouse; or
- at minimum, replace mutable branch refs with full commit SHAs while the
  packaging path is being built.
