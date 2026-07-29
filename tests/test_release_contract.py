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
    assert "Privacy & Security" in text


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
    assert compatibility["bundle_version"] == "1.3.2"
    assert compatibility["bundle_ref"] == "v1.3.2"
    assert compatibility["bundle_commit"] == (
        "8c97c7210a816a02e2487b7ae8b4696bc3236618"
    )
    assert compatibility["status"] == "released"
