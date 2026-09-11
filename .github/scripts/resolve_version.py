#!/usr/bin/env python3
"""Resolve the next release version for the single-workflow release
automation in .github/workflows/release.yml.

Pure logic, no GitHub/network calls -- validated offline against
constructed scenarios (see this PR's description) before being wired into
the workflow.

Output convention (stdout, one line):
  skip               -- nothing to release this run
  release:<version>  -- release exactly this version string (no leading "v")
"""

from __future__ import annotations

import argparse
import re
import sys

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(-.+)?$")


def parse(v: str) -> tuple[int, int, int, str]:
    m = VERSION_RE.match(v)
    if not m:
        raise ValueError(f"not a MAJOR.MINOR.PATCH[-suffix] version: {v!r}")
    major, minor, patch, suffix = m.groups()
    return int(major), int(minor), int(patch), suffix or ""


def bump_patch(core: tuple[int, int, int]) -> tuple[int, int, int]:
    major, minor, patch = core
    return major, minor, patch + 1


def resolve(current_version: str, latest_tag_version: str, drafter_resolved: str) -> str:
    if not latest_tag_version:
        # No existing tag to compare against. Deliberately conservative: this
        # automation never guesses a first version on its own; an initial
        # tag is expected to be created manually.
        return "skip"

    if current_version != latest_tag_version:
        # Someone already bumped pyproject.toml by hand -- respect it
        # verbatim, including any prerelease suffix. This is also how the
        # project graduates out of beta: edit pyproject.toml directly.
        return f"release:{current_version}"

    if not drafter_resolved:
        return "skip"

    latest_major, latest_minor, latest_patch, latest_suffix = parse(latest_tag_version)
    latest_core = (latest_major, latest_minor, latest_patch)

    drafter_core: tuple[int, int, int] | None
    try:
        d_major, d_minor, d_patch, _ = parse(drafter_resolved)
        drafter_core = (d_major, d_minor, d_patch)
    except ValueError:
        drafter_core = None

    # Known node-semver/release-drafter quirk: resolving "patch" starting
    # from a PRERELEASE tag of that exact patch (e.g. 0.1.1-beta) can
    # resolve back to the *same* numeric core (0.1.1) instead of
    # incrementing -- semver's `inc('patch')` treats "graduate the
    # prerelease" and "bump" as the same operation. If that happens (or
    # resolution failed to parse), bump patch ourselves on top of the
    # latest tag instead of trusting the resolver verbatim.
    if drafter_core is None or drafter_core <= latest_core:
        next_core = bump_patch(latest_core)
    else:
        next_core = drafter_core

    next_version = f"{next_core[0]}.{next_core[1]}.{next_core[2]}{latest_suffix}"
    return f"release:{next_version}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--current-version", required=True)
    p.add_argument("--latest-tag-version", default="")
    p.add_argument("--drafter-resolved", default="")
    args = p.parse_args()

    try:
        result = resolve(args.current_version, args.latest_tag_version, args.drafter_resolved)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()
