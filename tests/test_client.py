import httpx
import pytest
import respx

import tgscraper as tg
from telegram_scraper import TelegramScraper
from tgscraper import AsyncScraper, ChannelNotFound, Scraper

URL = "https://t.me/s/chan"


def _route_pages(page_factory):
    """chan has ids 1..30, 10 per page."""
    def handler(request):
        before = int(request.url.params.get("before", 31))
        ids = list(range(max(1, before - 10), before))
        nxt = ids[0] if ids and ids[0] > 1 else None
        return httpx.Response(200, text=page_factory("chan", ids, nxt))
    return respx.get(URL).mock(side_effect=handler)


@respx.mock
def test_pagination_and_limit(page_factory):
    route = _route_pages(page_factory)
    with Scraper(delay=0) as s:
        msgs = s.get_messages("chan", limit=15)
    assert [m.id for m in msgs] == list(range(30, 15, -1))
    assert route.call_count == 2


@respx.mock
def test_whole_history(page_factory):
    _route_pages(page_factory)
    with Scraper(delay=0) as s:
        msgs = s.get_messages("@chan", limit=None)
    assert [m.id for m in msgs] == list(range(30, 0, -1))


@respx.mock
def test_min_id_and_before(page_factory):
    _route_pages(page_factory)
    with Scraper(delay=0) as s:
        assert [m.id for m in s.get_messages("chan", limit=None, min_id=25)] == [30, 29, 28, 27, 26]
        assert [m.id for m in s.get_messages("chan", limit=3, before=12)] == [11, 10, 9]


@respx.mock
def test_filters_and_query(page_factory):
    route = _route_pages(page_factory)
    with Scraper(delay=0) as s:
        msgs = s.get_messages("chan", limit=3, min_views=20, keywords=["post"], query="post")
    assert [m.id for m in msgs] == [30, 29, 28]
    assert route.calls[0].request.url.params["q"] == "post"


@respx.mock
def test_since_stops_paging(page_factory):
    def handler(request):
        before = int(request.url.params.get("before", 31))
        ids = list(range(before - 10, before))
        # newer pages are on later days
        return httpx.Response(200, text=page_factory("chan", ids, ids[0], day=before // 10))
    route = respx.get(URL).mock(side_effect=handler)
    with Scraper(delay=0) as s:
        msgs = s.get_messages("chan", limit=None, since="2026-01-02")
    assert [m.id for m in msgs] == list(range(30, 20, -1)) + list(range(20, 10, -1))
    assert route.call_count == 3


@respx.mock
def test_retry_then_success(page_factory):
    respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, text=page_factory("chan", [1]))])
    with Scraper(delay=0, retries=2) as s:
        s._wait_time = lambda *a: 0
        assert [m.id for m in s.get_messages("chan")] == [1]


@respx.mock
def test_channel_not_found():
    respx.get("https://t.me/s/nope").mock(return_value=httpx.Response(302, headers={"Location": "https://t.me/nope"}))
    with pytest.raises(ChannelNotFound):
        tg.scrape("nope")


@respx.mock
def test_get_message_and_info(page1):
    respx.get("https://t.me/s/testchan").mock(return_value=httpx.Response(200, text=page1))
    with Scraper(delay=0) as s:
        assert s.get_message("testchan", 99).reply_to == 98
        assert s.get_message("testchan", 5) is None
        assert s.channel_info("https://t.me/testchan").subscribers == 1_200_000


@respx.mock
def test_incremental(tmp_path, page_factory):
    _route_pages(page_factory)
    state = tmp_path / "state.json"
    assert len(tg.scrape("chan", 5, incremental=True, state_file=state)) == 5
    assert tg.scrape("chan", 5, incremental=True, state_file=state) == []


@respx.mock
async def test_async_scrape_many(page_factory):
    _route_pages(page_factory)
    respx.get("https://t.me/s/missing").mock(return_value=httpx.Response(404))
    async with AsyncScraper(delay=0) as s:
        results = await s.scrape_many(["chan", "missing"], limit=12)
    assert [m.id for m in results["chan"]] == list(range(30, 18, -1))
    assert isinstance(results["missing"], ChannelNotFound)


@respx.mock
def test_legacy_wrapper(page_factory):
    _route_pages(page_factory)
    scraper = TelegramScraper("https://t.me/s/chan", 2)
    assert scraper.fetch_messages() == ["post 30", "post 29"]
