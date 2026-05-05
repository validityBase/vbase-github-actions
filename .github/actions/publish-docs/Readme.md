## Publish Product Documentation

This action publishes Markdown documentation from a product repository to the
central validityBase docs repository. It is the lower-level building block used
by the shared reusable workflow:

```yaml
jobs:
  update-main-docs:
    uses: validityBase/vbase-github-actions/.github/workflows/publish-docs.yml@v1
    with:
      source-docs-path: docs
      target-repository-branch: main
    secrets:
      DOCS_REPO_ACCESS_TOKEN: ${{ secrets.DOCS_REPO_ACCESS_TOKEN }}
```

Prefer the reusable workflow for complete documentation publishing jobs. Use
this direct action when the caller workflow needs custom checkout, setup, or
build steps:

```yaml
name: Update the Main Docs Repository

on:
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  update-main-docs:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd  # actions/checkout v5.0.1

      - name: Publish Documents
        uses: validityBase/vbase-github-actions/.github/actions/publish-docs@v1
        with:
          docs-repo-access-token: ${{ secrets.DOCS_REPO_ACCESS_TOKEN }}
          source-docs-path: docs
          target-repository-branch: main
```

## Inputs

Required input:
- `docs-repo-access-token`: token that can push to the central docs repository.

Optional inputs:
- `source-docs-path`: source Markdown folder, defaults to `docs`.
- `target-docs-path`: target folder in the central docs repository, defaults to
  the current repository name.
- `target-repository`: defaults to `validityBase/docs`.
- `target-repository-branch`: target branch in the docs repository. If omitted,
  the action uses the current product branch name.
- `preprocess-plant-uml`: defaults to `true`.
- `resolve-absolute-links-repos`: newline-separated repository names whose
  absolute GitHub links should be rewritten.

## Behavior

The action copies Markdown files into the target docs repository. It can
preprocess PlantUML blocks into image links and can rewrite selected absolute
GitHub repository links into relative links that work inside the central docs
site.

## Maintenance

Make source changes in `src/`, then run:

```bash
npm run build
```

The bundled `index.js` must be committed with any TypeScript source changes.
Do not commit `node_modules`.
