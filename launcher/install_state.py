#!/usr/bin/env python3
"""Validated pointer and receipt operations for managed Rubric Loom installs."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO
from urllib.parse import urlsplit

POINTER_SCHEMA = "coursecraft.rubric_loom_install_pointer/1"
RELEASE_SCHEMA = "coursecraft.rubric_loom_runner_release/1"
LAUNCH_RECEIPT_SCHEMA = "coursecraft.rubric_loom_launch/1"
RETIRE_RECEIPT_SCHEMA = "coursecraft.rubric_loom_version_retire/1"
LAUNCHER_PROTOCOL = 1

RUNNER_REPOSITORY = "github.com/timebeing92/brightspace-rubric-loom-runner"
BUNDLE_REPOSITORY = "github.com/timebeing92/brightspace-rubric-bundle"

INSTALL_ROOT_ENV = "RUBRIC_LOOM_INSTALL_ROOT"
DATA_ROOT_ENV = "RUBRIC_LOOM_DATA_ROOT"
OUTPUT_ROOT_ENV = "RUBRIC_LOOM_OUTPUT_ROOT"
MANAGED_VERSION_ENV = "RUBRIC_LOOM_MANAGED_VERSION"
LAUNCHER_PATH_ENV = "RUBRIC_LOOM_LAUNCHER_PATH"
USER_DATA_ENV = "RUBRIC_LOOM_USER_DATA"
VENV_ENV = "RUBRIC_LOOM_VENV"
RELEASE_REPOSITORY_ENV = "RUBRIC_LOOM_RELEASE_REPOSITORY"
INSTALLED_VERSION_ENV = "RUBRIC_LOOM_INSTALLED_VERSION"
INSTALL_LOCK_NAME = "install.lock"


class InstallStateError(RuntimeError):
    """A managed install is incomplete, unsafe, or inconsistent."""


def utc_text() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def require_version(value: str) -> str:
    parsed = version_tuple(value)
    if parsed is None:
        raise InstallStateError(f"Invalid release version: {value!r}")
    return ".".join(str(part) for part in parsed)


def canonical_repository(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("git@") and ":" in text:
        text = text.split("@", 1)[1].replace(":", "/", 1)
    elif "://" in text:
        parts = urlsplit(text)
        text = f"{parts.hostname or ''}{parts.path}"
    return text.lower().removesuffix(".git").rstrip("/")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InstallStateError(f"Required file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallStateError(f"Could not read valid JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallStateError(f"Expected a JSON object in {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_receipted_file(
    root: Path,
    receipt: dict[str, Any],
    *,
    kind: str,
) -> None:
    text = str(receipt.get("path") or "")
    relative = Path(text)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise InstallStateError(
            f"Release manifest contains an unsafe {kind} path: {text!r}"
        )
    candidate = root.joinpath(*relative.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise InstallStateError(
            f"Release {kind} path escapes its root: {text!r}"
        ) from exc
    if candidate.is_symlink() or not candidate.is_file():
        raise InstallStateError(f"Receipted {kind} file is missing: {text}")
    if sha256_file(candidate) != receipt["sha256"]:
        raise InstallStateError(f"{kind.title()} file checksum mismatch: {text}")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def pointer_path(install_root: Path) -> Path:
    return install_root / "current.json"


def version_root(install_root: Path, version: str) -> Path:
    normalized = require_version(version)
    return install_root / "versions" / normalized


def ensure_install_directories(install_root: Path) -> None:
    for relative in (
        "versions",
        "staging",
        "receipts",
        "user-data/input",
        "user-data/output",
        "user-data/runtime",
    ):
        (install_root / relative).mkdir(parents=True, exist_ok=True)


def _try_lock(handle: TextIO) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if not handle.read(1):
                handle.seek(0)
                handle.write(" ")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError) as exc:
        raise InstallStateError(
            "Another Rubric Loom install, activation, or cleanup is already in progress"
        ) from exc


def _unlock(handle: TextIO) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def install_lock(install_root: Path) -> Iterator[None]:
    """Hold the cross-process lock for every managed-install mutation."""
    ensure_install_directories(install_root)
    path = install_root / "staging" / INSTALL_LOCK_NAME
    try:
        handle = path.open("a+", encoding="utf-8")
    except OSError as exc:
        raise InstallStateError(
            f"Could not open the Rubric Loom install lock: {exc}"
        ) from exc
    try:
        _try_lock(handle)
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "acquired_at_utc": utc_text(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        try:
            yield
        finally:
            _unlock(handle)
    finally:
        handle.close()


def validate_release_manifest(
    root: Path,
    *,
    expected_version: str | None = None,
) -> dict[str, Any]:
    manifest_path = root / "RELEASE_MANIFEST.json"
    manifest = load_json(manifest_path)
    validate_manifest_payload(
        manifest,
        expected_version=expected_version,
        source=str(manifest_path),
    )

    required = (
        root / "brightspace-rubric-loom-runner" / "rubric_loom.sh",
        root / "brightspace-rubric-loom-runner" / "rubric_loom.ps1",
        root / "brightspace-rubric-bundle" / "scripts" / "rubric_loom_wizard.py",
        root / "brightspace-rubric-bundle" / "scripts" / "run_rubric_bundle.py",
        root / "brightspace-rubric-bundle" / "scripts" / "run_weave_bundle.py",
        root / "brightspace-rubric-bundle" / "requirements-lock.txt",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        detail = "\n".join(f"  - {path}" for path in missing)
        raise InstallStateError(f"Release is missing required files:\n{detail}")
    for receipt in manifest.get("contracts") or []:
        validate_receipted_file(root, receipt, kind="contract")
    for receipt in manifest.get("runtime_files") or []:
        validate_receipted_file(root, receipt, kind="runtime")
    return manifest


def validate_manifest_payload(
    manifest: dict[str, Any],
    *,
    expected_version: str | None = None,
    source: str = "release manifest",
) -> str:
    if manifest.get("schema") != RELEASE_SCHEMA:
        raise InstallStateError(
            f"Unsupported release manifest schema in {source}: "
            f"{manifest.get('schema')!r}"
        )
    version = require_version(str(manifest.get("version") or ""))
    if expected_version is not None and version != require_version(expected_version):
        raise InstallStateError(
            f"Release version mismatch: expected {expected_version}, found {version}"
        )

    for key, expected_repository in (
        ("runner", RUNNER_REPOSITORY),
        ("bundle", BUNDLE_REPOSITORY),
    ):
        record = manifest.get(key)
        if not isinstance(record, dict):
            raise InstallStateError(f"Release manifest is missing its {key} record")
        repository = canonical_repository(record.get("repository"))
        if repository != expected_repository:
            raise InstallStateError(
                f"Unexpected {key} repository in release: {repository or '(blank)'}"
            )
        commit = str(record.get("commit") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise InstallStateError(f"Invalid {key} commit in release manifest")
        if key == "bundle":
            require_version(str(record.get("version") or ""))

    contracts = manifest.get("contracts")
    if not isinstance(contracts, list) or len(contracts) < 4:
        raise InstallStateError("Release manifest is missing contract receipts")
    contract_schemas: set[str] = set()
    for contract in contracts:
        if not isinstance(contract, dict):
            raise InstallStateError("Release manifest contains an invalid contract receipt")
        schema = str(contract.get("schema") or "")
        if not schema or schema in contract_schemas:
            raise InstallStateError(
                "Release manifest contains a duplicate or blank contract schema"
            )
        contract_schemas.add(schema)
        if not re.fullmatch(r"[0-9a-f]{64}", str(contract.get("sha256") or "")):
            raise InstallStateError("Release manifest contains an invalid contract hash")
    expected_contract_schemas = {
        "coursecraft.rubrics/1",
        "coursecraft.rubric_authoring/1",
        "coursecraft.progress/1",
        "coursecraft.run/1",
    }
    if contract_schemas != expected_contract_schemas:
        raise InstallStateError(
            "Release manifest contains an unsupported contract set"
        )
    runtime_files = manifest.get("runtime_files")
    runtime_receipt_paths: set[str] = set()
    if runtime_files is not None:
        if not isinstance(runtime_files, list) or not runtime_files:
            raise InstallStateError("Release manifest contains invalid runtime receipts")
        seen_paths: set[str] = set()
        for receipt in runtime_files:
            if not isinstance(receipt, dict):
                raise InstallStateError("Release manifest contains an invalid runtime receipt")
            path = str(receipt.get("path") or "")
            if not path or path in seen_paths:
                raise InstallStateError("Release manifest contains a duplicate or blank runtime path")
            seen_paths.add(path)
            runtime_receipt_paths.add(path)
            if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256") or "")):
                raise InstallStateError("Release manifest contains an invalid runtime hash")
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, dict):
        raise InstallStateError("Release manifest contains invalid capabilities")
    required_capabilities = {
        "unravel": {
            "status": "enabled",
            "entry_point": (
                "brightspace-rubric-bundle/scripts/run_rubric_bundle.py"
            ),
            "progress_schema": "coursecraft.progress/1",
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
        },
    }
    for name, expected in required_capabilities.items():
        capability = capabilities.get(name)
        if not isinstance(capability, dict):
            raise InstallStateError(
                f"Release manifest is missing the {name} capability"
            )
        if any(capability.get(key) != value for key, value in expected.items()):
            raise InstallStateError(
                f"Release manifest contains an unsupported {name} capability"
            )
        paths = capability.get("runtime_files")
        if (
            not isinstance(paths, list)
            or not paths
            or any(not isinstance(path, str) or not path for path in paths)
        ):
            raise InstallStateError(
                f"Release manifest contains invalid {name} runtime paths"
            )
        if not set(paths).issubset(runtime_receipt_paths):
            raise InstallStateError(
                f"The {name} capability runtime files are not fully receipted"
            )
    user_data = manifest.get("user_data")
    expected_user_data = {
        "schema": "coursecraft.rubric_loom_user_data/1",
        "root": "user-data",
        "persistent_across_updates": True,
        "version_code_may_write_here_only": True,
        "lanes": ["input", "output", "runtime"],
    }
    if user_data != expected_user_data:
        raise InstallStateError(
            "Release manifest contains an unsupported user-data boundary"
        )
    licenses = manifest.get("licenses")
    expected_licenses = {
        "runner": "AGPL-3.0-or-later",
        "bundle": "AGPL-3.0-or-later",
        "commercial_terms": (
            "brightspace-rubric-loom-runner/COMMERCIAL.md"
        ),
        "attribution": "brightspace-rubric-loom-runner/NOTICE.md",
        "adoption_map": "brightspace-rubric-loom-runner/ADOPTION_MAP.md",
    }
    if licenses != expected_licenses:
        raise InstallStateError(
            "Release manifest contains unsupported license records"
        )
    return version


def validate_installed_version(
    install_root: Path,
    version: str,
) -> tuple[Path, dict[str, Any]]:
    normalized = require_version(version)
    root = version_root(install_root, normalized)
    if not root.is_dir():
        raise InstallStateError(f"Rubric Loom version {normalized} is not installed")
    manifest = validate_release_manifest(root, expected_version=normalized)
    return root, manifest


def load_pointer(install_root: Path) -> dict[str, Any]:
    path = pointer_path(install_root)
    pointer = load_json(path)
    if pointer.get("schema") != POINTER_SCHEMA:
        raise InstallStateError(
            f"Unsupported install pointer schema: {pointer.get('schema')!r}"
        )
    if pointer.get("launcher_protocol") != LAUNCHER_PROTOCOL:
        raise InstallStateError(
            "This installation requires a different stable-launcher protocol"
        )
    current = require_version(str(pointer.get("current_version") or ""))
    previous_text = str(pointer.get("previous_version") or "").strip()
    previous = require_version(previous_text) if previous_text else ""
    if previous and previous == current:
        raise InstallStateError("Current and previous versions cannot be identical")
    pointer["current_version"] = current
    pointer["previous_version"] = previous
    validate_installed_version(install_root, current)
    if previous:
        validate_installed_version(install_root, previous)
    return pointer


def _activate_version(install_root: Path, version: str) -> dict[str, Any]:
    ensure_install_directories(install_root)
    normalized = require_version(version)
    _, manifest = validate_installed_version(install_root, normalized)
    prior: dict[str, Any] = {}
    if pointer_path(install_root).exists():
        prior = load_pointer(install_root)
    prior_current = str(prior.get("current_version") or "")
    previous = (
        prior_current
        if prior_current and prior_current != normalized
        else str(prior.get("previous_version") or "")
    )
    pointer = {
        "schema": POINTER_SCHEMA,
        "launcher_protocol": LAUNCHER_PROTOCOL,
        "current_version": normalized,
        "previous_version": previous,
        "activated_at_utc": utc_text(),
        "runner_commit": manifest["runner"]["commit"],
        "bundle_commit": manifest["bundle"]["commit"],
    }
    atomic_write_json(pointer_path(install_root), pointer)
    return pointer


def activate_version(install_root: Path, version: str) -> dict[str, Any]:
    with install_lock(install_root):
        return _activate_version(install_root, version)


def rollback(install_root: Path) -> dict[str, Any]:
    with install_lock(install_root):
        pointer = load_pointer(install_root)
        previous = str(pointer.get("previous_version") or "")
        if not previous:
            raise InstallStateError(
                "No previous Rubric Loom version is available for rollback"
            )
        current = pointer["current_version"]
        result = _activate_version(install_root, previous)
        if result.get("previous_version") != current:
            raise InstallStateError(
                "Rollback pointer did not preserve the prior current version"
            )
        return result


def installed_versions(install_root: Path) -> list[str]:
    versions_dir = install_root / "versions"
    if not versions_dir.is_dir():
        return []
    versions: list[str] = []
    for path in versions_dir.iterdir():
        if not path.is_dir() or version_tuple(path.name) is None:
            continue
        try:
            validate_installed_version(install_root, path.name)
        except InstallStateError:
            continue
        versions.append(path.name)
    return sorted(versions, key=lambda value: version_tuple(value) or (0, 0, 0))


def current_activation_is_proven(
    install_root: Path,
    pointer: dict[str, Any] | None = None,
) -> bool:
    pointer = pointer or load_pointer(install_root)
    current = str(pointer["current_version"])
    activated_at = str(pointer.get("activated_at_utc") or "")
    path = install_root / "receipts" / "launches.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in reversed(lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if (
            record.get("schema") == LAUNCH_RECEIPT_SCHEMA
            and record.get("event") == "launch_end"
            and record.get("version") == current
            and record.get("status") == "ok"
            and str(record.get("recorded_at_utc") or "") >= activated_at
        ):
            return True
    return False


def remove_version(install_root: Path, version: str) -> dict[str, Any]:
    """Explicitly retire one non-current version without touching user data."""
    normalized = require_version(version)
    with install_lock(install_root):
        pointer = load_pointer(install_root)
        if normalized == pointer["current_version"]:
            raise InstallStateError(
                "The current Rubric Loom version cannot be removed"
            )
        if normalized == pointer.get("previous_version") and not current_activation_is_proven(
            install_root,
            pointer,
        ):
            raise InstallStateError(
                "The rollback version is protected until the current version launches successfully"
            )
        target, manifest = validate_installed_version(install_root, normalized)
        versions_root = (install_root / "versions").resolve()
        if target.is_symlink() or target.parent.resolve() != versions_root:
            raise InstallStateError("Version cleanup target is not a direct installed version")

        if normalized == pointer.get("previous_version"):
            updated = {
                **pointer,
                "previous_version": "",
                "updated_at_utc": utc_text(),
            }
            atomic_write_json(pointer_path(install_root), updated)
        try:
            shutil.rmtree(target)
        except OSError as exc:
            raise InstallStateError(
                f"Could not remove Rubric Loom v{normalized}: {exc}"
            ) from exc
        receipt = {
            "schema": RETIRE_RECEIPT_SCHEMA,
            "recorded_at_utc": utc_text(),
            "version": normalized,
            "runner_commit": manifest["runner"]["commit"],
            "bundle_commit": manifest["bundle"]["commit"],
        }
        atomic_write_json(
            install_root / "receipts" / f"retired-v{normalized}.json",
            receipt,
        )
        return receipt


def managed_environment(
    install_root: Path,
    *,
    version: str,
    launcher_path: Path,
) -> dict[str, str]:
    normalized = require_version(version)
    data_root = install_root / "user-data"
    return {
        INSTALL_ROOT_ENV: str(install_root),
        DATA_ROOT_ENV: str(data_root),
        OUTPUT_ROOT_ENV: str(data_root / "output"),
        MANAGED_VERSION_ENV: normalized,
        LAUNCHER_PATH_ENV: str(launcher_path),
        USER_DATA_ENV: str(data_root),
        VENV_ENV: str(data_root / "runtime" / ".venv"),
        RELEASE_REPOSITORY_ENV: (
            "timebeing92/brightspace-rubric-loom-runner"
        ),
        INSTALLED_VERSION_ENV: normalized,
    }


def append_launch_receipt(install_root: Path, payload: dict[str, Any]) -> None:
    ensure_install_directories(install_root)
    path = install_root / "receipts" / "launches.jsonl"
    record = {
        "schema": LAUNCH_RECEIPT_SCHEMA,
        "recorded_at_utc": utc_text(),
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
