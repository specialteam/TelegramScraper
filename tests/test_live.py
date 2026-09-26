"""Tests against the real t.me. Skipped unless TGSCRAPER_LIVE=1 (run by the "Live test" workflow)."""
import os

import pytest

import tgscraper as tg

pytestmark = pytest.mark.skipif(os.environ.get("TGSCRAPER_LIVE") != "1", reason="set TGSCRAPER_LIVE=1")

CHANNEL = os.environ.get("TGSCRAPER_LIVE_CHANNEL", "durov")


def test_channel_info():
    info = tg.channel_info(CHANNEL)
    print(info)
    assert info.title
    assert info.subscribers and info.subscribers > 1000


def test_messages_and_paging():
    posts = tg.scrape(CHANNEL, limit=40)  # needs at least 2 pages
    for p in posts[:3]:
        print(p.id, p.date, p.views, p.media_types, p.reactions, repr(p.text[:80]))
    assert len(posts) == 40
    ids = [p.id for p in posts]
    assert ids == sorted(ids, reverse=True) and len(set(ids)) == 40
    assert all(p.date for p in posts)
    assert sum(p.views is not None for p in posts) >= 35
    assert sum(bool(p.text) for p in posts) >= 20
    assert any(p.media for p in posts)


def test_get_message():
    latest = tg.scrape(CHANNEL, limit=1)[0]
    assert tg.get_message(CHANNEL, latest.id).id == latest.id


def test_search():
    posts = tg.search(CHANNEL, "telegram", limit=5)
    print([p.url for p in posts])
    assert posts


def test_not_found():
    with pytest.raises(tg.ChannelNotFound):
        tg.channel_info("this_channel_should_not_exist_1234567")


def test_scrape_many():
    results = tg.scrape_many([CHANNEL, "telegram"], limit=5)
    for ch, res in results.items():
        assert not isinstance(res, Exception), f"{ch}: {res}"
        assert len(res) == 5


def test_reactions_are_split_by_emoji():
    posts = [p for p in tg.scrape(CHANNEL, limit=20) if p.reactions]
    print([p.reactions for p in posts[:3]])
    assert posts, "expected some posts with reactions"
    assert any(len(p.reactions) > 1 for p in posts)
    assert any(not k.startswith("custom") for p in posts for k in p.reactions)
