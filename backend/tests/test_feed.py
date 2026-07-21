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
