# Release Policy

This repository is intended for public reuse across validityBase repositories.

## Version References

Internal consumers should use one of:
- a reviewed moving major tag such as `@v1`;
- a semver tag such as `@v1.2.3`;
- a full commit SHA where a repository requires strict pinning.

Breaking changes require a new major release ref such as `@v2`.

## Compatibility

Patch and minor releases must preserve existing action inputs and reusable
workflow contracts unless the change is explicitly documented as a breaking
change.

## Security

Third-party actions used inside shared workflows or composite actions should be
pinned by full commit SHA. Secrets must remain external to this repository and
must be provided by caller repositories.
