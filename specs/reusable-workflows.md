# Reusable Workflows

Reusable workflows live under `.github/workflows/` and should be preferred for
full CI/CD processes.

Planned reusable workflow candidates:
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
