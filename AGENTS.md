# AGENTS.md

Primary instructions are in [CLAUDE.md](CLAUDE.md) - read that first.

## Key Pointers

- Persistent agent memory: [internal/agents/memory/MEMORY.md](internal/agents/memory/MEMORY.md)
- Shared actions spec: [internal/specs/actions.md](internal/specs/actions.md)
- Reusable workflows spec: [internal/specs/reusable-workflows.md](internal/specs/reusable-workflows.md)
- Release policy: [internal/specs/release-policy.md](internal/specs/release-policy.md)

## Agent Notes

- Prefer reusable workflows for full CI/CD processes and composite actions for
  focused reusable building blocks.
- Keep third-party actions pinned by full commit SHA inside shared workflows and
  actions unless a spec explicitly allows a reviewed version tag.
- Do not commit `node_modules`.
- When editing a Node action, run its package build so the checked-in bundle is
  current.
