#!/usr/bin/env python3
"""Build the managed Rubric Loom package from explicit git refs."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import make_release_bundle as release

RUNNER_ROOT = Path(__file__).resolve().parents[1]

START_HERE = """\
Rubric Loom managed installation v{version}

This is the recommended Rubric Loom download. It keeps complete, verified
releases under versions/ and keeps your inputs, outputs, settings, logs, and
private Python environment under user-data/.

Start here:

  macOS    double-click "Rubric Loom.command"
  Windows  double-click "Rubric Loom.bat"
  Linux    bash rubric_loom_launcher.sh

Rubric Loom first looks for an existing supported Python 3.11-3.13
installation and reuses it. Python itself is not reinstalled when a supported
copy is already present. Before asking you to choose Unravel or Weave, the
Loom checks its required support packages and, if needed, offers to create a
private environment under user-data/runtime. It asks before installing
anything.

Rubric Loom does not use AI, upload course material, import into Brightspace,
or attach rubrics to activities.

Updates are installed beside the active version. The launcher verifies the
GitHub asset digest, checksum sidecar, repository identities, exact commits,
runtime file hashes, and schema receipts before activation. The prior complete
version remains available for rollback; removing an older version is always
explicit and never removes user-data/.

Maintenance:

  bash rubric_loom_launcher.sh --health
  bash rubric_loom_launcher.sh --list-versions
  bash rubric_loom_launcher.sh --update
  bash rubric_loom_launcher.sh --rollback

This release is unsigned. If macOS blocks "Rubric Loom.command", try to open
it once and dismiss the warning. Then open System Settings > Privacy &
Security, scroll to Security, choose Open Anyway, authenticate, and confirm
Open. Windows or institution-managed devices may show an equivalent trust
prompt. Use an exception only for a release downloaded from this project's
GitHub page; do not weaken system-wide security settings.
"""

TOP_COMMAND = """\
#!/usr/bin/env bash
# Stable double-clickable Rubric Loom launcher for macOS.
exec bash "$(dirname "$0")/rubric_loom_launcher.sh" "$@"
"""

TOP_BAT = """\
@echo off
rem Stable double-clickable Rubric Loom launcher for Windows.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rubric_loom_launcher.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo %cmdcmdline% | find /i "%~f0" >nul && pause
exit /b %EXITCODE%
"""


def initial_pointer(version: str, manifest: dict) -> dict:
    return {
        "schema": "coursecraft.rubric_loom_install_pointer/1",
        "launcher_protocol": 1,
        "current_version": version,
        "previous_version": "",
        "activated_at_utc": "1980-01-01T00:00:00Z",
        "runner_commit": manifest["runner"]["commit"],
        "bundle_commit": manifest["bundle"]["commit"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-ref", required=True)
    parser.add_argument("--bundle-ref", required=True)
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=RUNNER_ROOT.parent / release.BUNDLE_NAME,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RUNNER_ROOT / "dist",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    bundle_repo = args.bundle_dir.expanduser().resolve()
    if not args.allow_dirty:
        release.require_clean(RUNNER_ROOT)
        release.require_clean(bundle_repo)
    runner_commit = release.resolve_commit(RUNNER_ROOT, args.runner_ref)
    bundle_commit = release.resolve_commit(bundle_repo, args.bundle_ref)
    version = release.read_version(RUNNER_ROOT, runner_commit)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = f"rubric-loom-managed-v{version}"
    zip_path = output_dir / f"{package_name}.zip"
    zip_path.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / package_name
        version_root = staging / "versions" / version
        runner_staging = version_root / release.RUNNER_NAME
        bundle_staging = version_root / release.BUNDLE_NAME
        release.export_ref(RUNNER_ROOT, runner_commit, runner_staging)
        release.export_ref(bundle_repo, bundle_commit, bundle_staging)
        manifest = release.release_manifest(
            version=version,
            runner_ref=args.runner_ref,
            runner_commit=runner_commit,
            bundle_ref=args.bundle_ref,
            bundle_commit=bundle_commit,
            bundle_remote=release.normalized_remote(
                release.run_git(bundle_repo, "remote", "get-url", "origin")
            ),
            runner_root=runner_staging,
            bundle_root=bundle_staging,
        )
        (version_root / "RELEASE_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        shutil.copytree(runner_staging / "launcher", staging / "launcher")
        shell = staging / "rubric_loom_launcher.sh"
        shutil.copy2(
            runner_staging / "launcher" / "rubric_loom_launcher.sh",
            shell,
        )
        shell.chmod(0o755)
        shutil.copy2(
            runner_staging / "launcher" / "rubric_loom_launcher.ps1",
            staging / "rubric_loom_launcher.ps1",
        )
        command = staging / "Rubric Loom.command"
        command.write_text(TOP_COMMAND, encoding="utf-8")
        command.chmod(0o755)
        (staging / "Rubric Loom.bat").write_text(TOP_BAT, encoding="utf-8")
        (staging / "START_HERE.txt").write_text(
            START_HERE.format(version=version),
            encoding="utf-8",
        )
        (staging / "current.json").write_text(
            json.dumps(initial_pointer(version, manifest), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        (staging / "MANAGED_INSTALL_MANIFEST.json").write_text(
            json.dumps(
                {
                    "schema": "coursecraft.rubric_loom_managed_package/1",
                    "launcher_protocol": 1,
                    "initial_version": version,
                    "runner_commit": runner_commit,
                    "bundle_commit": bundle_commit,
                    "user_data": "user-data",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        user_data = staging / "user-data"
        user_data.mkdir()
        (user_data / "README.txt").write_text(
            "Rubric Loom keeps inputs, outputs, settings, and its private "
            "Python environment here. Updates and rollback do not remove "
            "this folder.\n",
            encoding="utf-8",
        )
        release.deterministic_zip(staging, zip_path)

    checksum = release.sha256_file(zip_path)
    checksum_path = zip_path.with_name(zip_path.name + ".sha256")
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    print(f"built {zip_path}")
    print(f"sha256 {checksum}")
    print(f"runner {runner_commit}")
    print(f"bundle {bundle_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
