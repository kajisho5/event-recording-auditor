"""Regression tests for the release automation's version-resolution logic
(.github/scripts/resolve_version.py), pinning down the scenarios it was
validated against before being wired into .github/workflows/release.yml.

This tests repo infrastructure, not the event_recording_auditor package,
but lives here so it runs in the same `pytest` invocation as everything
else rather than being forgotten.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "resolve_version.py"


def resolve(current: str, latest_tag_version: str = "", drafter_resolved: str = "") -> str:
    args = [
        sys.executable,
        str(SCRIPT),
        "--current-version",
        current,
        "--latest-tag-version",
        latest_tag_version,
    ]
    if drafter_resolved:
        args += ["--drafter-resolved", drafter_resolved]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_no_existing_tag_never_guesses_a_first_version():
    assert resolve("0.1.0-beta", "") == "skip"


def test_manual_bump_ahead_of_latest_tag_is_respected_verbatim():
    assert resolve("0.2.0-beta", "0.1.1-beta") == "release:0.2.0-beta"


def test_manual_graduation_out_of_beta_drops_the_suffix_as_written():
    assert resolve("1.0.0", "0.9.5-beta") == "release:1.0.0"


def test_auto_path_with_no_drafter_output_skips():
    assert resolve("0.1.1-beta", "0.1.1-beta") == "skip"


def test_auto_path_uses_drafters_resolution_and_keeps_the_beta_suffix():
    assert resolve("0.1.1-beta", "0.1.1-beta", "0.1.2") == "release:0.1.2-beta"


def test_auto_path_self_corrects_the_known_prerelease_graduation_quirk():
    # release-drafter/node-semver can resolve "patch" on a prerelease of that
    # exact patch back to the same numeric core instead of incrementing.
    assert resolve("0.1.1-beta", "0.1.1-beta", "0.1.1") == "release:0.1.2-beta"


def test_auto_path_self_corrects_an_unparseable_drafter_output():
    assert resolve("0.1.1-beta", "0.1.1-beta", "garbage") == "release:0.1.2-beta"


def test_auto_path_honors_a_correctly_resolved_minor_bump():
    assert resolve("0.1.1-beta", "0.1.1-beta", "0.2.0") == "release:0.2.0-beta"


def test_auto_path_with_no_prerelease_suffix_stays_stable():
    assert resolve("1.2.3", "1.2.3", "1.2.4") == "release:1.2.4"
