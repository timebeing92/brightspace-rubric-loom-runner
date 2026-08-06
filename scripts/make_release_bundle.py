#!/usr/bin/env python3
"""Build one portable Rubric Loom ZIP from explicit runner and bundle refs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

RUNNER_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCHEMA = "coursecraft.rubric_loom_runner_release/1"
RUNNER_NAME = "brightspace-rubric-loom-runner"
BUNDLE_NAME = "brightspace-rubric-bundle"

CONTRACT_FILES = (
    "workspace/reference/schemas/rubrics/rubrics_schema.json",
    "workspace/reference/schemas/rubrics/rubric_authoring_schema.json",
    "workspace/reference/schemas/progress/progress_events_schema.json",
    "workspace/reference/schemas/course/run_identity_schema.json",
)

BUNDLE_RUNTIME_FILES = (
    "scripts/run_rubric_bundle.py",
    "scripts/extract_rubrics_to_workbook.py",
    "scripts/rubrics_to_docx.py",
    "scripts/common_xml.py",
    "scripts/run_weave_bundle.py",
    "scripts/make_rubric_package.py",
    "scripts/rubric_authoring.py",
    "scripts/rubric_package_lib.py",
    "scripts/validate_rubric_package.py",
    "scripts/rubric_loom_wizard.py",
    "scripts/rubric_loom_weave.py",
    "scripts/rubric_loom_templates.py",
    "scripts/loom_progress.py",
    "scripts/loom_ui.py",
    "scripts/loom_art.py",
    "scripts/release_check.py",
    "scripts/bootstrap_env.py",
    "requirements-lock.txt",
    "upstream/workbench_pin.json",
)

RUNNER_RUNTIME_FILES = (
    "rubric_loom.sh",
    "rubric_loom.ps1",
    "launcher/stable_launcher.py",
    "launcher/install_state.py",
    "launcher/install_release.py",
    "launcher/network_update.py",
    "launcher/rubric_loom_launcher.sh",
    "launcher/rubric_loom_launcher.ps1",
)

START_HERE = """\
Rubric Loom v{version}

Rubric Loom is a local, deterministic tool for Brightspace rubrics.

  Unravel  Read one course export—or a folder of exports—and create review
            workbooks, structured JSON, and optional reviewer DOCX files.

  Weave    Read a supported DOCX, Markdown, or JSON rubric source; review the
            interpretation; and build a validated rubric-only import ZIP.

Start here:

  macOS    double-click "Rubric Loom.command"
  Windows  double-click "Rubric Loom.bat"
  Linux    bash brightspace-rubric-loom-runner/rubric_loom.sh

On the first run, Rubric Loom looks for an existing supported Python
3.11-3.13 installation and reuses it. Python itself is not reinstalled when a
supported copy is already present. Before asking you to choose Unravel or
Weave, the Loom checks its required support packages and, if needed, offers
to create a private environment inside user-data/runtime. It asks before
installing anything. Later launches reuse that environment directly. If an
upgrade changes the exact dependency lock, or the cached runtime is damaged,
the Loom offers to refresh only that private environment. Your inputs and
outputs remain on this computer.

If macOS blocks "Rubric Loom.command", try to open it once and dismiss the
warning. Then open System Settings > Privacy & Security, scroll to Security,
choose Open Anyway, authenticate, and confirm Open.

Rubric Loom does not use AI. Versioned Python software reads declared
Brightspace package structures and applies explicit validation and packaging
rules. It reports unfamiliar structures instead of guessing.

The Loom can build a rubric import package, but it cannot import that package
or attach a rubric to a Brightspace activity. Those remain manual steps in
Brightspace.

Folders:

  user-data/                         your inputs, outputs, settings, and runtime
  brightspace-rubric-loom-runner/   launch and release-management code
  brightspace-rubric-bundle/        the pinned Unravel and Weave engine

Release provenance: RELEASE_MANIFEST.json
Documentation: brightspace-rubric-loom-runner/README.md
"""

TOP_COMMAND = """\
#!/usr/bin/env bash
# Double-clickable Rubric Loom launcher for macOS.
exec bash "$(dirname "$0")/brightspace-rubric-loom-runner/rubric_loom.sh" "$@"
"""

TOP_BAT = """\
@echo off
rem Double-clickable Rubric Loom launcher for Windows.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0brightspace-rubric-loom-runner\\rubric_loom.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo %cmdcmdline% | find /i "%~f0" >nul && pause
exit /b %EXITCODE%
"""


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {message}")
    return result.stdout.strip()


def require_clean(repo: Path) -> None:
    if run_git(repo, "status", "--porcelain"):
        raise RuntimeError(f"release repo is dirty: {repo}")


def resolve_commit(repo: Path, ref: str) -> str:
    return run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def read_version(repo: Path = RUNNER_ROOT, ref: str = "HEAD") -> str:
    version = run_git(repo, "show", f"{ref}:VERSION").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RuntimeError(f"Invalid runner VERSION at {ref}: {version!r}")
    return version


def normalized_remote(value: str) -> str:
    text = value.strip()
    if text.startswith("git@") and ":" in text:
        host_path = text.split("@", 1)[1]
        host, path = host_path.split(":", 1)
        return f"https://{host}/{path}"
    if text.startswith(("http://", "https://")):
        parts = urlsplit(text)
        host = parts.hostname or parts.netloc
        if parts.port:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    return text


def export_ref(repo: Path, commit: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    archive = subprocess.Popen(
        ["git", "-C", str(repo), "archive", commit],
        stdout=subprocess.PIPE,
    )
    subprocess.run(
        ["tar", "-x", "-C", str(destination)],
        stdin=archive.stdout,
        check=True,
    )
    if archive.wait() != 0:
        raise RuntimeError(f"git archive failed for {repo} at {commit}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def schema_receipt(bundle_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for relative in CONTRACT_FILES:
        path = bundle_root / relative
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "schema": str(payload.get("$id") or ""),
                "path": f"{BUNDLE_NAME}/{relative}",
                "sha256": sha256_file(path),
            }
        )
    return rows


def runtime_receipt(
    runner_root: Path,
    bundle_root: Path,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for prefix, root, files in (
        (RUNNER_NAME, runner_root, RUNNER_RUNTIME_FILES),
        (BUNDLE_NAME, bundle_root, BUNDLE_RUNTIME_FILES),
    ):
        for relative in files:
            path = root / relative
            if not path.is_file():
                raise RuntimeError(f"Selected release lacks runtime file: {prefix}/{relative}")
            rows.append(
                {
                    "path": f"{prefix}/{relative}",
                    "sha256": sha256_file(path),
                }
            )
    return rows


def require_markers(root: Path, relative: str, markers: tuple[str, ...]) -> None:
    path = root / relative
    if not path.is_file():
        raise RuntimeError(f"Selected bundle lacks runtime file: {relative}")
    source = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise RuntimeError(
            f"Selected bundle lacks required markers in {relative}: "
            + ", ".join(missing)
        )


def bundle_capabilities(bundle_root: Path) -> dict[str, dict[str, Any]]:
    require_markers(
        bundle_root,
        "scripts/run_rubric_bundle.py",
        ("--progress-events", "coursecraft.progress/1", "rubrics_d2l.xml"),
    )
    require_markers(
        bundle_root,
        "scripts/run_weave_bundle.py",
        (
            "--preflight",
            "--progress-events",
            "coursecraft.run/1",
            "manual_only",
        ),
    )
    require_markers(
        bundle_root,
        "scripts/rubric_loom_wizard.py",
        (
            "--door",
            "--approve-weave",
            "RUBRIC_LOOM_USER_DATA",
            "RUBRIC_LOOM_VENV",
        ),
    )
    return {
        "unravel": {
            "status": "enabled",
            "entry_point": f"{BUNDLE_NAME}/scripts/run_rubric_bundle.py",
            "progress_schema": "coursecraft.progress/1",
            "input_shapes": [
                "brightspace_export_zip",
                "unpacked_export_folder",
                "rubrics_d2l.xml",
                "folder_of_exports",
            ],
            "runtime_files": [
                f"{BUNDLE_NAME}/scripts/run_rubric_bundle.py",
                f"{BUNDLE_NAME}/scripts/extract_rubrics_to_workbook.py",
                f"{BUNDLE_NAME}/scripts/rubrics_to_docx.py",
                f"{BUNDLE_NAME}/scripts/common_xml.py",
            ],
        },
        "weave": {
            "status": "enabled",
            "entry_point": f"{BUNDLE_NAME}/scripts/run_weave_bundle.py",
            "terminal_entry_point": (
                f"{BUNDLE_NAME}/scripts/rubric_loom_wizard.py"
            ),
            "progress_schema": "coursecraft.progress/1",
            "activity_attachment": "manual_only",
            "runtime_files": [
                f"{BUNDLE_NAME}/scripts/run_weave_bundle.py",
                f"{BUNDLE_NAME}/scripts/make_rubric_package.py",
                f"{BUNDLE_NAME}/scripts/rubric_authoring.py",
                f"{BUNDLE_NAME}/scripts/rubric_package_lib.py",
                f"{BUNDLE_NAME}/scripts/validate_rubric_package.py",
                f"{BUNDLE_NAME}/upstream/workbench_pin.json",
            ],
        },
    }


def release_manifest(
    *,
    version: str,
    runner_ref: str,
    runner_commit: str,
    bundle_ref: str,
    bundle_commit: str,
    bundle_remote: str,
    runner_root: Path,
    bundle_root: Path,
) -> dict[str, Any]:
    bundle_version = (bundle_root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", bundle_version):
        raise RuntimeError("Selected bundle has an invalid VERSION file")
    return {
        "schema": RELEASE_SCHEMA,
        "version": version,
        "runner": {
            "repository": normalized_remote(
                run_git(RUNNER_ROOT, "remote", "get-url", "origin")
            ),
            "ref": runner_ref,
            "commit": runner_commit,
        },
        "bundle": {
            "repository": bundle_remote,
            "ref": bundle_ref,
            "commit": bundle_commit,
            "version": bundle_version,
        },
        "contracts": schema_receipt(bundle_root),
        "runtime_files": runtime_receipt(runner_root, bundle_root),
        "capabilities": bundle_capabilities(bundle_root),
        "user_data": {
            "schema": "coursecraft.rubric_loom_user_data/1",
            "root": "user-data",
            "persistent_across_updates": True,
            "version_code_may_write_here_only": True,
            "lanes": ["input", "output", "runtime"],
        },
        "licenses": {
            "runner": "AGPL-3.0-or-later",
            "bundle": "AGPL-3.0-or-later",
            "commercial_terms": f"{RUNNER_NAME}/COMMERCIAL.md",
            "attribution": f"{RUNNER_NAME}/NOTICE.md",
            "adoption_map": f"{RUNNER_NAME}/ADOPTION_MAP.md",
        },
    }


def deterministic_zip(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            relative = path.relative_to(source.parent).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=RUNNER_ROOT.parent / BUNDLE_NAME,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RUNNER_ROOT / "dist",
    )
    parser.add_argument("--runner-ref", required=True)
    parser.add_argument("--bundle-ref", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    bundle_repo = args.bundle_dir.expanduser().resolve()
    if not (bundle_repo / "scripts" / "rubric_loom_wizard.py").is_file():
        raise SystemExit(f"Not the Rubric Bundle repo: {bundle_repo}")
    if not args.allow_dirty:
        require_clean(RUNNER_ROOT)
        require_clean(bundle_repo)

    runner_commit = resolve_commit(RUNNER_ROOT, args.runner_ref)
    bundle_commit = resolve_commit(bundle_repo, args.bundle_ref)
    version = read_version(RUNNER_ROOT, runner_commit)
    release_name = f"rubric-loom-v{version}"
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{release_name}.zip"
    zip_path.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / release_name
        runner_staging = staging / RUNNER_NAME
        bundle_staging = staging / BUNDLE_NAME
        export_ref(RUNNER_ROOT, runner_commit, runner_staging)
        export_ref(bundle_repo, bundle_commit, bundle_staging)
        (staging / "user-data" / "input").mkdir(parents=True)
        (staging / "user-data" / "output").mkdir()
        (staging / "user-data" / "runtime").mkdir()
        (staging / "user-data" / "README.txt").write_text(
            "Rubric Loom keeps inputs, outputs, settings, and its private "
            "Python environment here.\n",
            encoding="utf-8",
        )
        (staging / "START_HERE.txt").write_text(
            START_HERE.format(version=version),
            encoding="utf-8",
        )
        manifest = release_manifest(
            version=version,
            runner_ref=args.runner_ref,
            runner_commit=runner_commit,
            bundle_ref=args.bundle_ref,
            bundle_commit=bundle_commit,
            bundle_remote=normalized_remote(
                run_git(bundle_repo, "remote", "get-url", "origin")
            ),
            runner_root=runner_staging,
            bundle_root=bundle_staging,
        )
        (staging / "RELEASE_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        command = staging / "Rubric Loom.command"
        command.write_text(TOP_COMMAND, encoding="utf-8")
        command.chmod(0o755)
        (staging / "Rubric Loom.bat").write_text(TOP_BAT, encoding="utf-8")
        deterministic_zip(staging, zip_path)

    checksum = sha256_file(zip_path)
    checksum_path = zip_path.with_name(zip_path.name + ".sha256")
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    print(f"built {zip_path}")
    print(f"sha256 {checksum}")
    print(f"runner {runner_commit}")
    print(f"bundle {bundle_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
