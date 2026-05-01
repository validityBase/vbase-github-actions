# AGENTS.md

## Setup

- Claude entry point: [CLAUDE.md](CLAUDE.md)
- Agent data and memory: [agents/](agents/)
- Specs: [specs/](specs/)

## Workflow

When making code or action changes in this repo, follow this order:

0. Confirm the task scope is clear before starting work.
1. Define or confirm behavior, acceptance criteria, and edge cases.
2. Implement the smallest scoped change.
3. Update specs and README examples to match behavior.
4. Add or update validation where practical.
5. Run relevant static checks, or list exact commands if they cannot be run.
6. Prepare a PR-ready summary with validation and follow-ups.

## Security

- Do not commit secrets, webhook URLs, tokens, private keys, or environment
  values.
- Shared actions and reusable workflows must accept secrets from callers through
  `secrets`, `env`, or documented inputs.
- Avoid logging secret-bearing values, generated `.env` files, request headers,
  or full notification descriptors.
- Public actions should not expose technical alpha or repository-specific
  implementation details unless the caller already supplies that information.

## GitHub Actions Design

- Prefer reusable workflows for full processes such as CI, linting, docs
  publication, coverage, E2E tests, and deployments.
- Use composite actions for small reusable building blocks such as dependency
  setup, notification sending, and environment preparation.
- Keep third-party actions pinned by full commit SHA inside shared workflows and
  actions unless a spec explicitly allows a reviewed version tag.
- Public consumers should use reviewed release refs such as `@v1` or full commit
  SHAs depending on the consuming repository's security policy.

## Tests

This repo primarily contains GitHub Actions code. Prefer:

```bash
find . -name '*.yml' -o -name '*.yaml'
git diff --check
```

Use action-specific package commands when editing a Node action, for example:

```bash
cd .github/actions/publish-docs
npm run build
```
