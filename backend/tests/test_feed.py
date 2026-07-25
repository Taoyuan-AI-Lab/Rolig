from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app import router


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttl: int | None = None

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttl = ttl


async def test_feed_is_cached_as_json_array(monkeypatch) -> None:
    user_id = uuid4()
    meme_id = uuid4()
    creator_id = uuid4()

    async def fake_fetch_feed(*args, **kwargs):
        return [
            {
                "id": meme_id,
                "creator_id": creator_id,
                "media_url": "https://media.rolig.app/meme.jpg",
                "media_type": "image",
                "tags": ["reaction"],
                "summary": "A reaction meme",
                "humor_style": "reaction",
                "score": 12.5,
                "similarity": 0.91,
                "created_at": datetime.now(UTC),
            }
        ]

    monkeypatch.setattr(router, "fetch_feed", fake_fetch_feed)
    redis = FakeRedis()
    settings = SimpleNamespace(feed_cache_ttl_seconds=60)

    first = await router.get_feed(
        user_id=user_id,
        db=object(),
        redis=redis,
        settings=settings,
        limit=20,
        w1=1.0,
        w2=10.0,
        w3=15.0,
    )
    second = await router.get_feed(
        user_id=user_id,
        db=object(),
        redis=redis,
        settings=settings,
        limit=20,
        w1=1.0,
        w2=10.0,
        w3=15.0,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.items[0].id == meme_id
    assert redis.ttl == 60


async def test_client_feed_uses_lookahead_for_exact_pagination(monkeypatch) -> None:
    creator_id = uuid4()
    rows = [
        {
            "id": uuid4(),
            "creator_id": creator_id,
            "media_url": "https://media.rolig.app/one.jpg",
            "media_type": "image",
            "tags": ["reaction"],
            "summary": "First meme",
            "humor_style": "reaction",
            "like_count": 12,
            "view_count": 345,
            "music_title": "Demo Beat",
            "score": 0,
            "similarity": None,
            "created_at": datetime.now(UTC),
        },
        {
            "id": uuid4(),
            "creator_id": creator_id,
            "media_url": "https://media.rolig.app/two.jpg",
            "media_type": "image",
            "tags": ["relatable"],
            "summary": "Second meme",
            "humor_style": "relatable",
            "like_count": 0,
            "view_count": 1,
            "music_title": None,
            "score": 0,
            "similarity": None,
            "created_at": datetime.now(UTC),
        },
    ]

    async def fake_fetch_feed(*args, **kwargs):
        assert kwargs["limit"] == 2
        return rows

    monkeypatch.setattr(router, "fetch_feed", fake_fetch_feed)
    redis = FakeRedis()
    settings = SimpleNamespace(feed_cache_ttl_seconds=60)

    first = await router.get_client_feed(
        db=object(),
        redis=redis,
        settings=settings,
        cursor=None,
        limit=1,
        user_id=None,
    )
    second = await router.get_client_feed(
        db=object(),
        redis=redis,
        settings=settings,
        cursor=None,
        limit=1,
        user_id=None,
    )

    assert len(first.items) == 1
    assert first.next_cursor is not None
    assert first.items[0].like_count == 12
    assert second == first


async def test_client_feed_returns_null_cursor_when_exhausted(monkeypatch) -> None:
    async def fake_fetch_feed(*args, **kwargs):
        return [
            {
                "id": uuid4(),
                "creator_id": uuid4(),
                "media_url": "https://media.rolig.app/only.jpg",
                "media_type": "image",
                "tags": ["reaction"],
                "summary": "Only meme",
                "humor_style": "reaction",
                "like_count": 0,
                "view_count": 0,
                "music_title": None,
                "score": 0,
                "similarity": None,
                "created_at": datetime.now(UTC),
            }
        ]

    monkeypatch.setattr(router, "fetch_feed", fake_fetch_feed)

    response = await router.get_client_feed(
        db=object(),
        redis=FakeRedis(),
        settings=SimpleNamespace(feed_cache_ttl_seconds=60),
        cursor=None,
        limit=1,
        user_id=None,
    )

    assert len(response.items) == 1
    assert response.next_cursor is None
