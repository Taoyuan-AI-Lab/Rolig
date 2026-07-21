from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.router import create_meme
from app.schemas import MediaType, MemeCreateRequest


async def test_meme_creation_is_unavailable_when_ai_is_disabled() -> None:
    payload = MemeCreateRequest(
        creator_id=uuid4(),
        media_url="https://media.rolig.app/meme.jpg",
        media_type=MediaType.IMAGE,
    )
    settings = SimpleNamespace(ai_analysis_enabled=False)

    with pytest.raises(HTTPException) as exc_info:
        await create_meme(
            payload=payload,
            db=object(),
            openai_client=None,
            settings=settings,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "AI meme analysis is disabled"
