from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


RUNNER_REPOSITORY = (
    "https://github.com/timebeing92/brightspace-rubric-loom-runner.git"
)
BUNDLE_REPOSITORY = (
    "https://github.com/timebeing92/brightspace-rubric-bundle.git"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_release_root(
    release_root: Path,
    version: str,
    *,
    runner_commit: str = "1" * 40,
    bundle_commit: str = "2" * 40,
    runner_repository: str = RUNNER_REPOSITORY,
) -> dict:
    runner = release_root / "brightspace-rubric-loom-runner"
    bundle = release_root / "brightspace-rubric-bundle"
    (runner / "launcher").mkdir(parents=True)
    (bundle / "scripts").mkdir(parents=True)
    (runner / "rubric_loom.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (runner / "rubric_loom.ps1").write_text("# fixture\n", encoding="utf-8")
    wizard = bundle / "scripts" / "rubric_loom_wizard.py"
    wizard.write_text(
        """
import json
import os
import sys
from pathlib import Path

data = Path(os.environ["RUBRIC_LOOM_USER_DATA"])
data.mkdir(parents=True, exist_ok=True)
(data / "fixture_launch.json").write_text(json.dumps({
    "argv": sys.argv[1:],
    "user_data": os.environ["RUBRIC_LOOM_USER_DATA"],
    "venv": os.environ["RUBRIC_LOOM_VENV"],
    "repository": os.environ["RUBRIC_LOOM_RELEASE_REPOSITORY"],
    "version": os.environ["RUBRIC_LOOM_INSTALLED_VERSION"],
}), encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    unravel = bundle / "scripts" / "run_rubric_bundle.py"
    unravel.write_text("# fixture\n", encoding="utf-8")
    weave = bundle / "scripts" / "run_weave_bundle.py"
    weave.write_text("# fixture\n", encoding="utf-8")
    requirements = bundle / "requirements-lock.txt"
    requirements.write_text("# fixture\n", encoding="utf-8")

    runtime_paths = (
        "brightspace-rubric-loom-runner/rubric_loom.sh",
        "brightspace-rubric-loom-runner/rubric_loom.ps1",
        "brightspace-rubric-bundle/scripts/rubric_loom_wizard.py",
        "brightspace-rubric-bundle/scripts/run_rubric_bundle.py",
        "brightspace-rubric-bundle/scripts/run_weave_bundle.py",
        "brightspace-rubric-bundle/requirements-lock.txt",
    )
    contracts = []
    for index, schema in enumerate(
        (
            "coursecraft.rubrics/1",
            "coursecraft.rubric_authoring/1",
            "coursecraft.progress/1",
            "coursecraft.run/1",
        )
    ):
        path = release_root / f"contract-{index}.json"
        path.write_text(json.dumps({"$id": schema}) + "\n", encoding="utf-8")
        contracts.append(
            {
                "schema": schema,
                "path": path.relative_to(release_root).as_posix(),
                "sha256": sha256(path),
            }
        )

    manifest = {
        "schema": "coursecraft.rubric_loom_runner_release/1",
        "version": version,
        "runner": {
            "repository": runner_repository,
            "ref": runner_commit,
            "commit": runner_commit,
        },
        "bundle": {
            "repository": BUNDLE_REPOSITORY,
            "ref": bundle_commit,
            "commit": bundle_commit,
            "version": "1.3.1",
        },
        "contracts": contracts,
        "runtime_files": [
            {
                "path": relative,
                "sha256": sha256(release_root / relative),
            }
            for relative in runtime_paths
        ],
        "capabilities": {
            "unravel": {
                "status": "enabled",
                "entry_point": (
                    "brightspace-rubric-bundle/scripts/run_rubric_bundle.py"
                ),
                "progress_schema": "coursecraft.progress/1",
                "runtime_files": [
                    "brightspace-rubric-bundle/scripts/run_rubric_bundle.py"
                ],
            },
            "weave": {
                "status": "enabled",
                "entry_point": (
                    "brightspace-rubric-bundle/scripts/run_weave_bundle.py"
                ),
                "terminal_entry_point": (
                    "brightspace-rubric-bundle/scripts/rubric_loom_wizard.py"
                ),
                "progress_schema": "coursecraft.progress/1",
                "activity_attachment": "manual_only",
                "runtime_files": [
                    "brightspace-rubric-bundle/scripts/run_weave_bundle.py",
                    "brightspace-rubric-bundle/scripts/rubric_loom_wizard.py",
                ],
            },
        },
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
            "commercial_terms": (
                "brightspace-rubric-loom-runner/COMMERCIAL.md"
            ),
            "attribution": "brightspace-rubric-loom-runner/NOTICE.md",
            "adoption_map": (
                "brightspace-rubric-loom-runner/ADOPTION_MAP.md"
            ),
        },
    }
    (release_root / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_installed_version(
    install_root: Path,
    version: str,
    **kwargs,
) -> Path:
    root = install_root / "versions" / version
    write_release_root(root, version, **kwargs)
    return root


def make_release_zip(
    directory: Path,
    version: str,
    **kwargs,
) -> tuple[Path, Path, str]:
    source = directory / f"source-{version}"
    root = source / f"rubric-loom-v{version}"
    write_release_root(root, version, **kwargs)
    archive = directory / f"rubric-loom-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(source).as_posix())
    digest = sha256(archive)
    sidecar = archive.with_name(archive.name + ".sha256")
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, sidecar, digest
