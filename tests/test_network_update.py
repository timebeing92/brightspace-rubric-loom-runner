from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))

import network_update  # noqa: E402


def release_payload(version: str = "1.2.3") -> dict:
    base = (
        "https://github.com/timebeing92/brightspace-rubric-loom-runner/"
        f"releases/download/v{version}"
    )
    zip_name = f"rubric-loom-v{version}.zip"
    checksum_name = f"{zip_name}.sha256"
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": zip_name,
                "browser_download_url": f"{base}/{zip_name}",
                "digest": f"sha256:{'a' * 64}",
            },
            {
                "name": checksum_name,
                "browser_download_url": f"{base}/{checksum_name}",
                "digest": f"sha256:{'b' * 64}",
            },
        ],
    }


def test_exact_release_assets_are_selected() -> None:
    selected = network_update.select_release_assets(release_payload())
    assert selected["version"] == "1.2.3"
    assert selected["zip_name"] == "rubric-loom-v1.2.3.zip"
    assert selected["api_sha256"] == "a" * 64


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda payload: payload.update({"draft": True}), "not a stable"),
        (
            lambda payload: payload["assets"][0].update(
                {"browser_download_url": "https://malicious.example/update.zip"}
            ),
            "Unexpected release asset URL",
        ),
        (
            lambda payload: payload["assets"][0].update({"digest": ""}),
            "does not expose",
        ),
        (
            lambda payload: payload.update({"tag_name": "latest"}),
            "Invalid release version",
        ),
    ],
)
def test_untrusted_release_metadata_is_refused(mutation, message: str) -> None:
    payload = release_payload()
    mutation(payload)
    with pytest.raises(network_update.NetworkUpdateError, match=message):
        network_update.select_release_assets(payload)


def test_release_version_cannot_change_during_update() -> None:
    with pytest.raises(network_update.NetworkUpdateError, match="changed"):
        network_update.select_release_assets(
            release_payload("1.2.4"),
            expected_version="1.2.3",
        )
