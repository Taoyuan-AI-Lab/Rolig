import json
import math
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.demo_data import (
    DemoAsset,
    DemoManifest,
    create_demo_embedding,
    load_and_prepare_manifest,
)


def demo_asset_payload(*, file: str = "approved.png") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "creator_id": str(uuid4()),
        "file": file,
        "media_type": "image",
        "content_type": "image/png",
        "tags": ["Reaction", "reaction", "relatable"],
        "summary": "A surprised cat reacts to an unexpected meeting.",
        "humor_style": "reaction",
        "toxicity_score": 0,
        "approved_for_demo": True,
        "rights": {
            "attribution_text": "Example Creator",
            "source_url": "https://example.com/source",
            "permission_basis": "direct_permission",
            "permission_notes": "Approved for the Rolig demo.",
        },
    }


async def test_manifest_prepares_approved_media(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "approved.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"demo")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"version": 1, "assets": [demo_asset_payload()]}),
        encoding="utf-8",
    )

    manifest, prepared = await load_and_prepare_manifest(manifest_path, assets_dir)

    assert isinstance(manifest, DemoManifest)
    assert prepared[0].byte_size == 12
    assert len(prepared[0].sha256) == 64
    assert prepared[0].manifest.tags == ["reaction", "relatable"]


async def test_manifest_rejects_incorrect_content_type(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "approved.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"demo")
    payload = demo_asset_payload()
    payload["content_type"] = "image/jpeg"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"version": 1, "assets": [payload]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="is image/png, not image/jpeg"):
        await load_and_prepare_manifest(manifest_path, assets_dir)


def test_manifest_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError, match="safe path"):
        DemoAsset.model_validate(demo_asset_payload(file="../private.png"))


def test_demo_embedding_is_normalized_and_stable() -> None:
    asset = DemoAsset.model_validate(demo_asset_payload())

    first = create_demo_embedding(asset)
    second = create_demo_embedding(asset)

    assert first == second
    assert len(first) == 1536
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_licensed_asset_requires_license_metadata() -> None:
    payload = demo_asset_payload()
    rights = dict(payload["rights"])  # type: ignore[arg-type]
    rights["permission_basis"] = "license"
    payload["rights"] = rights

    with pytest.raises(ValidationError, match="require license_name and license_url"):
        DemoAsset.model_validate(payload)


def test_original_asset_accepts_unavailable_source_url() -> None:
    payload = demo_asset_payload()
    rights = dict(payload["rights"])  # type: ignore[arg-type]
    rights["permission_basis"] = "original"
    rights["source_url"] = "N/A"
    payload["rights"] = rights

    asset = DemoAsset.model_validate(payload)

    assert asset.rights.source_url == "N/A"
