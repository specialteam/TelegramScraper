import httpx
import pytest
import respx

pytest.importorskip("mcp")

from tgscraper import mcp_server  # noqa: E402


@pytest.fixture
def mocked(page1):
    with respx.mock:
        respx.get("https://t.me/s/testchan").mock(return_value=httpx.Response(200, text=page1))
        respx.get("https://t.me/s/nope").mock(return_value=httpx.Response(404))
        yield


async def test_tools_registered():
    names = {t.name for t in await mcp_server.mcp.list_tools()}
    assert {"get_channel_info", "get_messages", "search_messages", "get_message", "get_new_messages",
            "analyze_channel", "compare_channels", "export_messages"} <= names


async def test_tools(mocked, tmp_path):
    info = await mcp_server.get_channel_info("testchan")
    assert info["subscribers"] == 1_200_000

    res = await mcp_server.get_messages("@testchan", limit=2)
    assert [m["id"] for m in res["messages"]] == [100, 99]
    assert "html" not in res["messages"][0]

    assert (await mcp_server.get_message("testchan", 98))["views"] == 12500
    assert (await mcp_server.get_new_messages("testchan", 99))["latest_id"] == 100
    assert (await mcp_server.analyze_channel("testchan"))["stats"]["count"] == 3
    cmp = await mcp_server.compare_channels(["testchan", "nope"])
    assert cmp["testchan"]["subscribers"] == 1_200_000 and "error" in cmp["nope"]
    saved = await mcp_server.export_messages("testchan", str(tmp_path / "t.json"))
    assert saved["count"] == 3
    assert "error" in await mcp_server.get_channel_info("nope")


async def test_call_through_protocol(mocked):
    result = await mcp_server.mcp.call_tool("get_messages", {"channel": "testchan", "limit": 1})
    assert "100" in str(result)
