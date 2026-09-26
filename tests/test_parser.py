from datetime import datetime, timezone

import pytest

from tgscraper.parser import normalize_channel, parse_count, parse_page


@pytest.mark.parametrize("raw", ["durov", "@durov", "t.me/durov", "https://t.me/s/durov", "https://t.me/durov/12",
                                 "http://telegram.me/durov", " durov/ "])
def test_normalize_channel(raw):
    assert normalize_channel(raw) == "durov"


def test_normalize_channel_invalid():
    with pytest.raises(ValueError):
        normalize_channel("not a channel!")


@pytest.mark.parametrize("raw,expected", [("1.2K", 1200), ("3,4M", 3_400_000), ("2,300", 2300), ("980", 980),
                                          ("12 345", 12345), ("", None), (None, None), ("abc", None)])
def test_parse_count(raw, expected):
    assert parse_count(raw) == expected


def test_parse_page(page1):
    messages, info, before = parse_page(page1, "testchan")
    assert [m.id for m in messages] == [98, 99, 100]
    assert before == 98

    assert info.title == "Test Channel"
    assert info.verified
    assert info.subscribers == 1_200_000
    assert info.counters == {"subscribers": 1_200_000, "photos": 3400, "videos": 120}
    assert info.description == "News about crypto\nand more"
    assert info.photo.endswith("photo.jpg")

    m98, m99, m100 = messages
    assert m98.url == "https://t.me/testchan/98"
    assert m98.text.startswith("Bitcoin is going up! Great profit 🚀\n#BTC")
    assert m98.date == datetime(2026, 1, 10, 9, 30, tzinfo=timezone.utc)
    assert m98.views == 12500
    assert m98.forwarded_from == "Other Channel"
    assert m98.hashtags == ["BTC", "crypto"]
    assert m98.mentions == ["someuser"]
    assert m98.links == ["https://example.com/a"]
    assert m98.reactions == {"👍": 1500, "🔥": 320}
    assert [(x.type, x.url) for x in m98.media] == [("photo", "https://cdn4.telesco.pe/file/p98.jpg")]

    # the quoted reply text must not leak into the message text
    assert m99.text == "Warning: market crash, big loss today"
    assert m99.reply_to == 98
    assert m99.edited and m99.author == "Admin"
    assert m99.media[0].type == "video"
    assert m99.media[0].url.endswith("v99.mp4")
    assert m99.media[0].duration == "0:42"

    assert m100.views == 2300 and not m100.media and not m100.edited


def test_message_roundtrip(page1):
    from tgscraper import Message
    messages, _, _ = parse_page(page1, "testchan")
    for m in messages:
        assert Message.from_dict(m.to_dict()) == m


def test_empty_page():
    messages, info, before = parse_page("<html></html>", "x")
    assert messages == [] and before is None and info.username == "x"
