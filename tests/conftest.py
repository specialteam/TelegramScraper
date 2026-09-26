from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def page1() -> str:
    return (FIXTURES / "page1.html").read_text(encoding="utf-8")


def make_page(channel, ids, before=None, day=1):
    """A minimal t.me/s page with text messages ``ids`` (oldest first)."""
    more = (f'<a class="tme_messages_more" data-before="{before}" href="/s/{channel}?before={before}"></a>'
            if before else "")
    items = "".join(
        f'<div class="tgme_widget_message" data-post="{channel}/{i}">'
        f'<div class="tgme_widget_message_text">post {i}</div>'
        f'<span class="tgme_widget_message_views">{i}</span>'
        f'<a class="tgme_widget_message_date"><time datetime="2026-01-{day:02d}T{i % 24:02d}:00:00+00:00"></time></a>'
        f"</div>"
        for i in ids
    )
    return f"<html><body>{more}{items}</body></html>"


@pytest.fixture
def page_factory():
    return make_page
