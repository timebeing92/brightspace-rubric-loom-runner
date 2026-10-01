from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))

import install_release  # noqa: E402
import install_state  # noqa: E402
import stable_launcher  # noqa: E402

from helpers import make_release_zip, write_installed_version  # noqa: E402


def test_stable_launcher_reports_the_runner_release_version() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert stable_launcher.LAUNCHER_VERSION == version


def test_side_by_side_install_and_rollback_preserve_user_data(
    tmp_path: Path,
) -> None:
    first_zip, first_sidecar, _ = make_release_zip(tmp_path, "1.0.0")
    second_zip, second_sidecar, _ = make_release_zip(
        tmp_path,
        "1.1.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        first_zip,
        checksum_path=first_sidecar,
    )
    sentinel = install_root / "user-data" / "output" / "keep-me.txt"
    sentinel.write_text("user work\n", encoding="utf-8")
    installed = install_release.install_release_zip(
        install_root,
        second_zip,
        checksum_path=second_sidecar,
    )
    rolled_back = install_state.rollback(install_root)

    assert installed["pointer"]["current_version"] == "1.1.0"
    assert installed["pointer"]["previous_version"] == "1.0.0"
    assert rolled_back["current_version"] == "1.0.0"
    assert rolled_back["previous_version"] == "1.1.0"
    assert sentinel.read_text(encoding="utf-8") == "user work\n"


def test_bad_checksum_does_not_create_a_version_or_pointer(tmp_path: Path) -> None:
    archive, _, _ = make_release_zip(tmp_path, "1.0.0")
    install_root = tmp_path / "managed"

    with pytest.raises(install_release.ReleaseInstallError, match="checksum mismatch"):
        install_release.install_release_zip(
            install_root,
            archive,
            expected_sha256="0" * 64,
        )

    assert not (install_root / "versions" / "1.0.0").exists()
    assert not install_state.pointer_path(install_root).exists()


def test_path_traversal_cannot_change_an_active_version(tmp_path: Path) -> None:
    good_zip, good_sidecar, _ = make_release_zip(tmp_path, "1.0.0")
    bad_zip, _, _ = make_release_zip(
        tmp_path,
        "1.1.0",
        runner_commit="3" * 40,
        bundle_commit="4" * 40,
    )
    with zipfile.ZipFile(bad_zip, "a") as archive:
        archive.writestr("rubric-loom-v1.1.0/../../outside.txt", "unsafe")
    bad_digest = install_release.sha256_file(bad_zip)
    bad_sidecar = bad_zip.with_name(bad_zip.name + ".sha256")
    bad_sidecar.write_text(f"{bad_digest}  {bad_zip.name}\n", encoding="utf-8")
    install_root = tmp_path / "managed"
    install_release.install_release_zip(
        install_root,
        good_zip,
        checksum_path=good_sidecar,
    )

    with pytest.raises(install_release.ReleaseInstallError, match="Unsafe ZIP"):
        install_release.install_release_zip(
            install_root,
            bad_zip,
            checksum_path=bad_sidecar,
        )

    assert install_state.load_pointer(install_root)["current_version"] == "1.0.0"
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.parametrize(
    "unsafe_name, message",
    [
        ("rubric-loom-v1.0.0/CON", "Windows-reserved"),
        ("rubric-loom-v1.0.0/folder\\file", "Unsafe ZIP"),
        ("rubric-loom-v1.0.0/name.", "Non-portable"),
    ],
)
def test_nonportable_archive_names_are_refused(
    tmp_path: Path,
    unsafe_name: str,
    message: str,
) -> None:
    archive, _, _ = make_release_zip(tmp_path, "1.0.0")
    with zipfile.ZipFile(archive, "a") as output:
        output.writestr(unsafe_name, "unsafe")
    digest = install_release.sha256_file(archive)

    with pytest.raises(install_release.ReleaseInstallError, match=message):
        install_release.install_release_zip(
            tmp_path / "managed",
            archive,
            expected_sha256=digest,
        )


def test_untrusted_repository_and_runtime_tampering_are_rejected(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "managed"
    untrusted = write_installed_version(
        install_root,
        "1.0.0",
        runner_repository="https://malicious.example/rubric-loom.git",
    )
    with pytest.raises(install_state.InstallStateError, match="Unexpected runner"):
        install_state.validate_release_manifest(untrusted)

    trusted = write_installed_version(install_root, "1.1.0")
    target = (
        trusted
        / "brightspace-rubric-bundle"
        / "scripts"
        / "run_weave_bundle.py"
    )
    target.write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(install_state.InstallStateError, match="checksum mismatch"):
        install_state.validate_release_manifest(trusted)


def test_contract_tampering_is_rejected(tmp_path: Path) -> None:
    install_root = tmp_path / "managed"
    root = write_installed_version(install_root, "1.0.0")
    (root / "contract-0.json").write_text('{"$id":"changed"}\n', encoding="utf-8")

    with pytest.raises(
        install_state.InstallStateError,
        match="Contract file checksum mismatch",
    ):
        install_state.validate_release_manifest(root)


def test_stable_launcher_passes_the_managed_data_boundary(tmp_path: Path) -> None:
    install_root = tmp_path / "managed"
    write_installed_version(install_root, "1.0.0")
    install_state.activate_version(install_root, "1.0.0")

    assert stable_launcher.launch(install_root, ["--plain", "--version"]) == 0
    capture = json.loads(
        (install_root / "user-data" / "fixture_launch.json").read_text(
            encoding="utf-8"
        )
    )
    assert capture["argv"] == ["--plain", "--version"]
    assert capture["user_data"] == str(install_root / "user-data")
    assert capture["venv"] == str(
        install_root / "user-data" / "runtime" / ".venv"
    )
    assert capture["repository"] == (
        "timebeing92/brightspace-rubric-loom-runner"
    )
    assert capture["version"] == "1.0.0"


def test_stable_launcher_reuses_private_runtime_after_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_root = tmp_path / "managed"
    write_installed_version(install_root, "1.0.0")
    install_state.activate_version(install_root, "1.0.0")
    private_python = stable_launcher.private_runtime_python(install_root)
    private_python.parent.mkdir(parents=True, exist_ok=True)
    private_python.write_bytes(b"private runtime placeholder")
    monkeypatch.setattr(
        stable_launcher,
        "python_runtime_usable",
        lambda candidate: candidate == private_python,
    )

    _, command, environment = stable_launcher.current_command(install_root, [])

    assert command[0] == str(private_python)
    assert environment["RUBRIC_LOOM_VENV"] == str(private_python.parent.parent)


def test_stable_launcher_rejects_a_corrupted_private_runtime(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "managed"
    write_installed_version(install_root, "1.0.0")
    install_state.activate_version(install_root, "1.0.0")
    private_python = stable_launcher.private_runtime_python(install_root)
    private_python.parent.mkdir(parents=True, exist_ok=True)
    private_python.write_bytes(b"this is not a Python executable")
    private_python.chmod(0o755)

    _, command, environment = stable_launcher.current_command(install_root, [])

    assert command[0] == sys.executable
    assert environment["RUBRIC_LOOM_VENV"] == str(private_python.parent.parent)


def test_stable_launcher_uses_bootstrap_python_before_private_runtime_exists(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "managed"
    write_installed_version(install_root, "1.0.0")
    install_state.activate_version(install_root, "1.0.0")

    _, command, _ = stable_launcher.current_command(install_root, [])

    assert command[0] == sys.executable


def test_pointer_cannot_escape_and_current_version_cannot_be_removed(
    tmp_path: Path,
) -> None:
    install_root = tmp_path / "managed"
    write_installed_version(install_root, "1.0.0")
    install_state.activate_version(install_root, "1.0.0")
    with pytest.raises(install_state.InstallStateError, match="current.*cannot"):
        install_state.remove_version(install_root, "1.0.0")

    install_state.atomic_write_json(
        install_state.pointer_path(install_root),
        {
            "schema": install_state.POINTER_SCHEMA,
            "launcher_protocol": 1,
            "current_version": "../../outside",
            "previous_version": "",
        },
    )
    with pytest.raises(install_state.InstallStateError, match="Invalid release version"):
        install_state.load_pointer(install_root)
