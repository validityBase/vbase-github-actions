# CLAUDE.md

This file is the minimal shared entry point for agentic work in this repository.

## Core Standards

- This public repository contains shared validityBase GitHub Actions and
  reusable workflows. Do not commit secrets, webhook URLs, private keys, or
  private environment values.
- Keep public action/workflow documentation free of technical alpha unless the
  caller already supplies that information.
- Rebuild bundled Node action assets after dependency or source changes.

## Internal Documentation

- Persistent agent memory: [internal/agents/memory/MEMORY.md](internal/agents/memory/MEMORY.md)
- Shared actions spec: [internal/specs/actions.md](internal/specs/actions.md)
- Reusable workflows spec: [internal/specs/reusable-workflows.md](internal/specs/reusable-workflows.md)
- Release policy: [internal/specs/release-policy.md](internal/specs/release-policy.md)
