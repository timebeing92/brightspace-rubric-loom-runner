from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_release_bundle.py"
SPEC = importlib.util.spec_from_file_location("make_release_bundle", SCRIPT)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


def test_user_onboarding_names_both_doors_and_the_no_ai_boundary() -> None:
    text = release.START_HERE
    assert "Unravel" in text
    assert "Weave" in text
    assert "does not use AI" in text
    assert "does not import" not in text
    assert "cannot import" in text
    assert "Python itself is not reinstalled" in text
    assert "Later launches reuse that environment directly" in text
    assert "Privacy & Security" in text


def test_readme_prominently_links_the_loom_install_guide() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "[!IMPORTANT]" in text
    assert "rubric-loom-managed-v<VERSION>.zip" in text
    assert "Code > Download ZIP" in text
    assert "System Settings > Privacy & Security" in text
    assert "click **Open**, then **Open Anyway**" in " ".join(text.split())
    assert "(INSTALL_AND_TROUBLESHOOT.md)" in text
    assert text.index("[!IMPORTANT]") < text.index("If you encounter an error")


def test_loom_install_guide_is_product_specific_and_complete() -> None:
    text = (ROOT / "INSTALL_AND_TROUBLESHOOT.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "Install, update, and troubleshoot Rubric Loom" in text
    assert "rubric-loom-managed-v<VERSION>.zip" in text
    assert "Rubric Loom.command" in text
    assert "Rubric Bundle engine" in normalized
    assert "System Settings > Privacy & Security" in text
    assert "click **Open**, then **Open Anyway**" in normalized
    assert "Python 3.11 through 3.13" in text
    assert "Later launches reuse that private environment directly" in text
    assert "rubric_loom_launcher.sh --health" in text
    assert "rubric_loom_launcher.sh --update" in text
    assert "rubric_loom_launcher.sh --rollback" in text
    assert "unravel_wizard.log" in text
    assert "weave_wizard.log" in text
    assert "attach the rubric" in text


def test_workbench_is_defined_for_human_readers() -> None:
    for relative in ("README.md", "ADOPTION_MAP.md", "NOTICE.md"):
        text = " ".join(
            (ROOT / relative).read_text(encoding="utf-8").split()
        )
        assert "upstream living library and development lab" in text
        assert "production-ready versions" in text

    readme = " ".join(
        (ROOT / "README.md").read_text(encoding="utf-8").split()
    )
    assert "(living library + development lab)" in readme
    assert "reviewed, production-ready tooling" in readme
    assert "do not need to access, install, or operate" in readme


def test_release_runtime_does_not_reimplement_rubric_semantics() -> None:
    python_files = list((ROOT / "launcher").glob("*.py"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in python_files)
    forbidden = (
        "xml.etree",
        "lxml",
        "rubrics_d2l.xml",
        "schemaversion",
        "RubricType",
    )
    for marker in forbidden:
        assert marker not in source


def test_launchers_prefer_the_existing_private_runtime() -> None:
    portable_shell = (ROOT / "rubric_loom.sh").read_text(encoding="utf-8")
    portable_windows = (ROOT / "rubric_loom.ps1").read_text(encoding="utf-8")
    managed_shell = (ROOT / "launcher/rubric_loom_launcher.sh").read_text(
        encoding="utf-8"
    )
    managed_windows = (ROOT / "launcher/rubric_loom_launcher.ps1").read_text(
        encoding="utf-8"
    )

    assert 'candidates+=("$RUBRIC_LOOM_VENV/bin/python")' in portable_shell
    assert 'Join-Path $env:RUBRIC_LOOM_VENV "Scripts\\python.exe"' in (
        portable_windows
    )
    assert 'candidates+=("$HERE/user-data/runtime/.venv/bin/python")' in (
        managed_shell
    )
    assert 'Join-Path $Here "user-data\\runtime\\.venv\\Scripts\\python.exe"' in (
        managed_windows
    )


def test_manifest_contract_is_specific_to_rubric_loom() -> None:
    assert release.RELEASE_SCHEMA == (
        "coursecraft.rubric_loom_runner_release/1"
    )
    assert len(release.CONTRACT_FILES) == 4
    assert "scripts/run_rubric_bundle.py" in release.BUNDLE_RUNTIME_FILES
    assert "scripts/run_weave_bundle.py" in release.BUNDLE_RUNTIME_FILES
    assert "upstream/workbench_pin.json" in release.BUNDLE_RUNTIME_FILES


def test_release_identity_matches_the_exact_bundle_lock() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    compatibility = json.loads(
        (ROOT / "BUNDLE_COMPATIBILITY.json").read_text(encoding="utf-8")
    )
    assert compatibility["runner_version"] == version
    assert compatibility["bundle_version"] == "1.3.3"
    assert compatibility["bundle_ref"] == "v1.3.3"
    assert compatibility["bundle_commit"] == (
        "c9f06def134c01800d6d169b99693b4b53abe564"
    )
    assert compatibility["status"] == "prepared"
