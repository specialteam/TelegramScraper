import csv
import json

import httpx
import pytest
import respx

import tgscraper as tg
from tgscraper.cli import main
from tgscraper.parser import parse_page


@pytest.fixture
def messages(page1):
    return list(reversed(parse_page(page1, "testchan")[0]))


@pytest.mark.parametrize("ext", ["json", "jsonl", "db"])
def test_export_roundtrip(tmp_path, messages, ext):
    path = tg.export(messages, tmp_path / f"out.{ext}")
    loaded = tg.load(path)
    assert sorted(loaded, key=lambda m: m.id) == sorted(messages, key=lambda m: m.id)


def test_sqlite_upsert(tmp_path, messages):
    path = tmp_path / "a.db"
    tg.export(messages, path)
    tg.export(messages[:1], path)
    assert len(tg.load(path)) == 3


def test_csv_xlsx_md(tmp_path, messages):
    tg.export(messages, tmp_path / "o.csv")
    with open(tmp_path / "o.csv", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[2]["hashtags"] == "#BTC #crypto" and rows[2]["media_types"] == "photo"
    pytest.importorskip("openpyxl")
    assert tg.export(messages, tmp_path / "o.xlsx").stat().st_size > 0
    assert "testchan/98" in tg.export(messages, tmp_path / "o.md").read_text(encoding="utf-8")


def test_bad_format(tmp_path, messages):
    with pytest.raises(ValueError):
        tg.export(messages, tmp_path / "out.txt")


def test_filter(messages):
    f = tg.MessageFilter(since="2026-01-11", until="2026-01-11")
    assert [m.id for m in f.apply(messages)] == [99]
    assert [m.id for m in tg.MessageFilter(media_types=["video"]).apply(messages)] == [99]
    assert [m.id for m in tg.MessageFilter(hashtag="#btc").apply(messages)] == [98]
    assert [m.id for m in tg.MessageFilter(regex=r"crash|سلام").apply(messages)] == [100, 99]


def test_analytics(messages):
    assert tg.sentiment("great profit, bullish!") > 0
    assert tg.sentiment("crash and loss") < 0
    assert tg.sentiment("خبر خوب و رشد عالی") > 0
    stats = tg.summarize(messages)
    assert stats["count"] == 3 and stats["total_views"] == 12500 + 980 + 2300
    assert stats["top_posts"][0]["id"] == 98
    assert stats["media_types"] == {"video": 1, "photo": 1}
    assert stats["reactions"]["👍"] == 1500
    assert "Top posts" in tg.format_summary(stats)
    json.dumps(stats)
    assert tg.summarize([]) == {"count": 0}


@respx.mock
def test_cli(tmp_path, page1, capsys):
    respx.get("https://t.me/s/testchan").mock(return_value=httpx.Response(200, text=page1))
    assert main(["testchan", "-n", "2", "--json"]) == 0
    assert [m["id"] for m in json.loads(capsys.readouterr().out)] == [100, 99]

    out = tmp_path / "x.csv"
    assert main(["scrape", "testchan", "-o", str(out), "--media-only"]) == 0
    assert out.exists()

    assert main(["info", "testchan", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["title"] == "Test Channel"

    assert main(["stats", "testchan"]) == 0
    assert "Top posts" in capsys.readouterr().out

    assert main(["testchan", "-n", "1"]) == 0
    assert "t.me/testchan/100" in capsys.readouterr().out


@respx.mock
def test_cli_error(capsys):
    respx.get("https://t.me/s/nope").mock(return_value=httpx.Response(404))
    assert main(["nope"]) == 1
    assert "not found" in capsys.readouterr().err
