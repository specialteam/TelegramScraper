"""Web dashboard. Run with ``tgscraper dashboard`` (needs ``pip install 'tgscraper[dashboard]'``)."""
from __future__ import annotations

import datetime as dt
import io
import json

import streamlit as st

import tgscraper as tg
from tgscraper.exporters import FLAT_COLUMNS, flatten

st.set_page_config(page_title="Telegram Scraper", page_icon="📡", layout="wide")
st.title("📡 Telegram Scraper")
st.caption("Read any public Telegram channel — no API key, no login.")

with st.sidebar:
    channels_text = st.text_input("Channel(s)", "durov", help="Comma separated: durov, telegram, t.me/xyz")
    limit = st.slider("Messages per channel", 10, 1000, 100, step=10)
    query = st.text_input("Telegram search (optional)")
    keywords = st.text_input("Keywords filter (comma separated)")
    use_dates = st.checkbox("Date range")
    since = until = None
    if use_dates:
        since = st.date_input("Since", dt.date.today() - dt.timedelta(days=30))
        until = st.date_input("Until", dt.date.today())
    media_only = st.checkbox("Only posts with media")
    proxy = st.text_input("Proxy (optional)", placeholder="socks5://127.0.0.1:1080")
    go = st.button("🚀 Scrape", type="primary", use_container_width=True)


@st.cache_data(ttl=300, show_spinner=False)
def fetch(channel, limit, query, keywords, since, until, media_only, proxy):
    info = tg.channel_info(channel, proxy=proxy or None)
    msgs = tg.scrape(channel, limit, proxy=proxy or None, query=query or None,
                     keywords=keywords, since=since, until=until, media_only=media_only)
    return info.to_dict(), [m.to_dict() for m in msgs]


if go:
    st.session_state["channels"] = [c.strip() for c in channels_text.split(",") if c.strip()]

for channel in st.session_state.get("channels", []):
    try:
        with st.spinner(f"Scraping {channel}…"):
            info, raw = fetch(channel, limit, query, [k.strip() for k in keywords.split(",") if k.strip()],
                              since, until, media_only, proxy)
    except Exception as exc:  # noqa: BLE001
        st.error(f"{channel}: {exc}")
        continue
    messages = [tg.Message.from_dict(d) for d in raw]
    stats = tg.summarize(messages)

    left, right = st.columns([1, 5])
    if info.get("photo"):
        left.image(info["photo"], width=96)
    right.subheader(f"{info.get('title') or channel}  ·  [t.me/{info['username']}]({info['url']})")
    if info.get("description"):
        right.caption(info["description"])

    c = st.columns(5)
    c[0].metric("Subscribers", f"{info.get('subscribers') or 0:,}")
    c[1].metric("Messages", stats.get("count", 0))
    c[2].metric("Avg views", f"{stats.get('avg_views') or 0:,}")
    c[3].metric("Posts / day", stats.get("posts_per_day", 0))
    c[4].metric("Sentiment", f"{stats.get('sentiment', {}).get('average', 0):+.2f}")
    if not messages:
        st.info("No messages matched.")
        continue

    rows = [flatten(m) for m in messages]
    tab_posts, tab_charts, tab_words, tab_export = st.tabs(["📰 Posts", "📈 Charts", "🔤 Words & tags", "💾 Export"])
    with tab_posts:
        st.dataframe(rows, use_container_width=True, hide_index=True, column_config={
            "url": st.column_config.LinkColumn("url"), "text": st.column_config.TextColumn("text", width="large")})
    with tab_charts:
        a, b = st.columns(2)
        a.markdown("**Posts per day**")
        a.bar_chart(stats["posts_by_day"])
        b.markdown("**Posts by hour (UTC)**")
        b.bar_chart({str(k): v for k, v in stats["posts_by_hour"].items()})
        views = {m.date.isoformat(): m.views for m in messages if m.date and m.views is not None}
        if views:
            st.markdown("**Views per post**")
            st.line_chart(dict(sorted(views.items())))
    with tab_words:
        a, b = st.columns(2)
        a.markdown("**Top words**")
        a.bar_chart(dict(stats["top_words"]))
        b.markdown("**Top hashtags**")
        if stats["top_hashtags"]:
            b.bar_chart(dict(stats["top_hashtags"]))
        else:
            b.caption("No hashtags")
        st.markdown("**🔥 Most viewed**")
        for p in stats["top_posts"]:
            st.markdown(f"- **{p['views'] or 0:,}** views — [{p['url']}]({p['url']}): {p['text']}")
    with tab_export:
        buf = io.StringIO()
        import csv
        writer = csv.DictWriter(buf, fieldnames=FLAT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ CSV", buf.getvalue().encode("utf-8-sig"), f"{channel}.csv", "text/csv")
        d2.download_button("⬇️ JSON", json.dumps(raw, ensure_ascii=False, indent=2), f"{channel}.json",
                           "application/json")
        d3.download_button("⬇️ Markdown", tg.to_markdown(messages), f"{channel}.md", "text/markdown")
    st.divider()

if not st.session_state.get("channels"):
    st.info("👈 Enter a channel and press **Scrape**.")
