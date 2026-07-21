import pytest

from app.services import (
    calculate_feed_score,
    decode_feed_cursor,
    encode_feed_cursor,
    normalize_feed_score,
)


def test_calculate_feed_score() -> None:
    score = calculate_feed_score(
        watch_time=4.5,
        liked=True,
        skipped=False,
        w1=2.0,
        w2=10.0,
        w3=15.0,
    )
    assert score == 19.0


def test_skip_penalty_is_subtracted() -> None:
    score = calculate_feed_score(
        watch_time=2.0,
        liked=False,
        skipped=True,
        w1=1.0,
        w2=10.0,
        w3=5.0,
    )
    assert score == -3.0


def test_client_score_is_normalized() -> None:
    assert normalize_feed_score(0) == 0.5
    assert 0 < normalize_feed_score(-100) < 0.5
    assert 0.5 < normalize_feed_score(100) < 1


def test_feed_cursor_round_trip() -> None:
    assert decode_feed_cursor(encode_feed_cursor(40)) == 40


def test_invalid_feed_cursor_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid feed cursor"):
        decode_feed_cursor("not-a-valid-cursor")
