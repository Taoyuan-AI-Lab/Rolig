from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import ClientFeedItem, MediaType, MemeCreateRequest


def test_video_requires_analysis_frame() -> None:
    with pytest.raises(ValidationError, match="analysis_image_url is required"):
        MemeCreateRequest(
            creator_id=uuid4(),
            media_url="https://media.rolig.app/video.mp4",
            media_type=MediaType.VIDEO,
        )


def test_http_media_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        MemeCreateRequest(
            creator_id=uuid4(),
            media_url="http://media.rolig.app/meme.jpg",
            media_type=MediaType.IMAGE,
        )


def test_client_feed_item_serializes_overlay_metadata() -> None:
    creator_id = uuid4()
    item = ClientFeedItem(
        id=uuid4(),
        creator_id=creator_id,
        url="https://media.rolig.app/meme.jpg",
        type=MediaType.IMAGE,
        tags=["reaction"],
        summary="A surprised cat reacts to a Monday meeting.",
        score=0.82,
        like_count=12,
        view_count=345,
        music_title="Demo Beat",
    )

    payload = item.model_dump(mode="json", by_alias=True)

    assert payload["creatorId"] == str(creator_id)
    assert payload["summary"] == "A surprised cat reacts to a Monday meeting."
    assert payload["likeCount"] == 12
    assert payload["viewCount"] == 345
    assert payload["musicTitle"] == "Demo Beat"
