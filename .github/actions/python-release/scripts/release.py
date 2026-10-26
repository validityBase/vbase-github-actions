"""Prepare and validate stable Python releases for caller repositories."""

import argparse
import ast
import datetime
import os
import re
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path


def repository_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if (
        not relative
        or Path(relative).is_absolute()
        or not path.is_relative_to(root.resolve())
    ):
        raise ValueError("Release file paths must stay within the caller repository.")
    return path


def normalized_name(name: str) -> str:
    # PyPA name normalization; prepare/tag run without third-party dependencies.
    return re.sub(r"[-_.]+", "-", name).lower()


def source_version(root: Path, version_file: str) -> str:
    """Read the single literal package version without executing package code."""
    tree = ast.parse(repository_file(root, version_file).read_text(encoding="utf-8"))
    versions = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    ]
    if len(versions) != 1 or not isinstance(versions[0], str):
        raise ValueError("Expected exactly one literal __version__ assignment.")
    return versions[0]


def release_notes(
    root: Path,
    tag: str,
    *,
    version_file: str,
    changelog_file: str = "CHANGELOG.md",
    tag_prefix: str = "v",
) -> str:
    """Require matching source/changelog versions and return just this release's notes."""
    number = r"(0|[1-9][0-9]*)"
    if not re.fullmatch(rf"{re.escape(tag_prefix)}{number}\.{number}\.{number}", tag):
        raise ValueError("Release tag must be stable vX.Y.Z (no prerelease).")
    version = tag[len(tag_prefix) :]
    if source_version(root, version_file) != version:
        raise ValueError(f"Tag does not match __version__ in {version_file}.")

    changelog = repository_file(root, changelog_file).read_text(encoding="utf-8")
    headings = list(re.finditer(r"(?m)^## (.+)$", changelog))
    if not headings or headings[0][1] != "[Unreleased]":
        raise ValueError("CHANGELOG.md must start with an [Unreleased] section.")
    matches = [h for h in headings if h[1].startswith(f"[{version}]")]
    if len(matches) != 1 or len(headings) < 2 or matches[0] != headings[1]:
        raise ValueError(
            "The newest changelog release must match the tag exactly once."
        )
    heading = re.fullmatch(
        rf"\[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})", matches[0][1]
    )
    if not heading:
        raise ValueError("Release heading must be [X.Y.Z] - YYYY-MM-DD.")
    datetime.date.fromisoformat(heading[1])
    end = headings[2].start() if len(headings) > 2 else len(changelog)
    notes = changelog[matches[0].end() : end].strip()
    if not re.search(r"(?m)^- \S", notes):
        raise ValueError("Release notes must contain at least one changelog entry.")
    return notes + "\n"


def validate_distributions(dist_dir: Path, version: str, *, package_name: str) -> None:
    """Check the actual metadata of both distributions, rather than filenames alone."""
    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1 or len(list(dist_dir.iterdir())) != 2:
        raise ValueError("Expected exactly one wheel and one source distribution.")
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = [n for n in wheel.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("Wheel must contain exactly one METADATA file.")
        wheel_metadata = wheel.read(names[0])
    with tarfile.open(sdists[0]) as sdist:
        members = [
            m for m in sdist.getmembers() if re.fullmatch(r"[^/]+/PKG-INFO", m.name)
        ]
        if len(members) != 1 or not members[0].isfile():
            raise ValueError("Source distribution must contain one root PKG-INFO file.")
        with sdist.extractfile(members[0]) as metadata:
            sdist_metadata = metadata.read()
    for raw in (wheel_metadata, sdist_metadata):
        metadata = BytesParser().parsebytes(raw)
        if (
            normalized_name(metadata["Name"] or "") != normalized_name(package_name)
            or metadata["Version"] != version
        ):
            raise ValueError(
                f"Distribution name/version must match {package_name} and the tag."
            )


def next_version(current: str, bump: str) -> str:
    number = r"(0|[1-9][0-9]*)"
    if not re.fullmatch(rf"{number}\.{number}\.{number}", current):
        raise ValueError("Current version must be stable X.Y.Z.")
    if bump not in ("major", "minor", "patch"):
        raise ValueError("Choose a major, minor, or patch increment.")
    parts = list(map(int, current.split(".")))
    index = ("major", "minor", "patch").index(bump)
    parts[index] += 1
    parts[index + 1 :] = [0] * (2 - index)
    return ".".join(map(str, parts))


def prepare_release(
    root: Path,
    bump: str,
    date: datetime.date,
    *,
    version_file: str,
    changelog_file: str = "CHANGELOG.md",
) -> str:
    current = source_version(root, version_file)
    version = next_version(current, bump)
    version_path = repository_file(root, version_file)
    contents, count = re.subn(
        r"(?m)^__version__\s*=\s*(['\"])[^'\"\n]+\1[^\S\n]*$",
        f'__version__ = "{version}"',
        version_path.read_text(encoding="utf-8"),
    )
    if count != 1:
        raise ValueError("Expected a single plain __version__ assignment.")

    changelog_path = repository_file(root, changelog_file)
    changelog = changelog_path.read_text(encoding="utf-8")
    headings = list(re.finditer(r"(?m)^## (.+)$", changelog))
    if not headings or headings[0][1] != "[Unreleased]":
        raise ValueError("CHANGELOG.md must start with an [Unreleased] section.")
    if sum(h[1] == "[Unreleased]" for h in headings) != 1:
        raise ValueError("Expected exactly one [Unreleased] section.")
    if any(h[1].startswith(f"[{version}]") for h in headings):
        raise ValueError(f"CHANGELOG.md already contains version {version}.")
    end = headings[1].start() if len(headings) > 1 else len(changelog)
    if not re.search(r"(?m)^- \S", changelog[headings[0].end() : end]):
        raise ValueError("Add at least one user-facing entry under [Unreleased].")
    start = headings[0].end()
    changelog = (
        changelog[:start]
        + f"\n\n## [{version}] - {date.isoformat()}"
        + changelog[start:]
    )
    version_path.write_text(contents, encoding="utf-8")
    changelog_path.write_text(changelog, encoding="utf-8")
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "validate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--version-file", required=True)
    parser.add_argument("--changelog-file", default="CHANGELOG.md")
    parser.add_argument("--tag-prefix", default="v")
    parser.add_argument("--tag", default="")
    parser.add_argument("--bump", default="")
    parser.add_argument("--dist-dir", default="")
    parser.add_argument("--package-name", default="")
    parser.add_argument("--notes-file", default="")
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            version = prepare_release(
                args.root,
                args.bump,
                datetime.datetime.now(datetime.timezone.utc).date(),
                version_file=args.version_file,
                changelog_file=args.changelog_file,
            )
            tag = args.tag_prefix + version
        else:
            tag = args.tag
        notes = release_notes(
            args.root,
            tag,
            version_file=args.version_file,
            changelog_file=args.changelog_file,
            tag_prefix=args.tag_prefix,
        )
        version = tag[len(args.tag_prefix) :]
        if args.dist_dir:
            if not args.package_name:
                raise ValueError("package-name is required to validate distributions.")
            validate_distributions(
                Path(args.dist_dir), version, package_name=args.package_name
            )
        if args.notes_file:
            Path(args.notes_file).write_text(notes, encoding="utf-8")
        if os.environ.get("GITHUB_OUTPUT"):
            with Path(os.environ["GITHUB_OUTPUT"]).open(
                "a", encoding="utf-8"
            ) as output:
                output.write(f"version={version}\n")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Release {args.operation} failed: {error}\n")
    print(version)


if __name__ == "__main__":
    main()
