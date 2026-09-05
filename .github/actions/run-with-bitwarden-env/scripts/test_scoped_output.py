"""Tests for command-scoped masking of Bitwarden-backed process output."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest

import scoped_output


class ScopedOutputTests(unittest.TestCase):
    """Keep Bitwarden masks inside the command that uses those values."""

    def test_masks_child_output_without_registering_job_wide_masks(self) -> None:
        """A short Bitwarden value must not redact later workflow output."""
        child = (
            "print('::add-mask::0', flush=True); "
            "print('::add-mask::1', flush=True); "
            "print('::add-mask::credential-value', flush=True); "
            "print('inside: 10 credential-value', flush=True)"
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            return_code = scoped_output.run_with_scoped_masks(
                [sys.executable, "-c", child]
            )
            print("summary: 2026 81.50%")

        self.assertEqual(0, return_code)
        self.assertEqual(
            "inside: ****** ***\nsummary: 2026 81.50%\n",
            output.getvalue(),
        )
        self.assertNotIn("::add-mask::", output.getvalue())
        self.assertNotIn("credential-value", output.getvalue())

    def test_initial_masks_protect_values_before_child_registers_them(self) -> None:
        """Access tokens stay protected even when setup exits before add-mask."""
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            return_code = scoped_output.run_with_scoped_masks(
                [sys.executable, "-c", "print('failed with access-token')"],
                initial_masks=["access-token"],
            )

        self.assertEqual(0, return_code)
        self.assertEqual("failed with ***\n", output.getvalue())

    def test_decodes_workflow_command_escapes_before_redacting(self) -> None:
        """Percent and newline escapes follow GitHub workflow-command encoding."""
        child = (
            "print('::add-mask::part%25value%0Anext', flush=True); "
            "print('part%value next', flush=True)"
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            return_code = scoped_output.run_with_scoped_masks(
                [sys.executable, "-c", child]
            )

        self.assertEqual(0, return_code)
        self.assertEqual("*** ***\n", output.getvalue())

    def test_redacts_stderr_and_preserves_the_child_exit_code(self) -> None:
        """Filtering must not hide failures or leak their secret diagnostics."""
        child = (
            "import sys; "
            "print('::add-mask::failure-secret', flush=True); "
            "print('failed: failure-secret', file=sys.stderr, flush=True); "
            "raise SystemExit(23)"
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            return_code = scoped_output.run_with_scoped_masks(
                [sys.executable, "-c", child]
            )

        self.assertEqual(23, return_code)
        self.assertEqual("failed: ***\n", output.getvalue())


if __name__ == "__main__":
    unittest.main()
