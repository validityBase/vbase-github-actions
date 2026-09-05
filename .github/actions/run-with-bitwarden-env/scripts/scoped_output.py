"""Stream command output while keeping add-mask effects command-scoped."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

ADD_MASK_PREFIX = "::add-mask::"


class ScopedMaskFilter:
    """Consume add-mask commands and redact only the wrapped command's output."""

    def __init__(self, initial_masks: Sequence[str] = ()) -> None:
        self._masks: list[str] = []
        self._mask_set: set[str] = set()
        for value in initial_masks:
            self.add_mask(value)

    def add_mask(self, value: str) -> None:
        """Register the non-empty words GitHub would mask for one value."""
        for word in re.split(r"\s+", value):
            if word and word not in self._mask_set:
                self._mask_set.add(word)
                self._masks.append(word)
        self._masks.sort(key=len, reverse=True)

    def consume(self, line: str) -> None:
        """Capture add-mask commands or emit one sanitized output line."""
        if line.startswith(ADD_MASK_PREFIX):
            encoded_value = line[len(ADD_MASK_PREFIX) :].rstrip("\r\n")
            self.add_mask(decode_workflow_command_value(encoded_value))
            return

        sanitized = line
        for value in self._masks:
            sanitized = sanitized.replace(value, "***")
        sys.stdout.write(sanitized)
        sys.stdout.flush()


def decode_workflow_command_value(value: str) -> str:
    """Decode the escaping used for GitHub workflow command data."""
    return value.replace("%0D", "\r").replace("%0A", "\n").replace("%25", "%")


def run_with_scoped_masks(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    initial_masks: Sequence[str] = (),
    mask_filter: ScopedMaskFilter | None = None,
) -> int:
    """Run a command and prevent its add-mask values from escaping the process."""
    output_filter = mask_filter or ScopedMaskFilter()
    for value in initial_masks:
        output_filter.add_mask(value)

    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None:  # pragma: no cover - guaranteed by stdout=PIPE
        raise RuntimeError("Unable to capture command output")

    with process.stdout:
        for line in process.stdout:
            output_filter.consume(line)
    return process.wait()
