from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import MediaType, MemeCreateRequest


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
