"""Backward-compatible wrapper around the old ``TelegramScraper`` class.

New code should use the ``tgscraper`` package instead::

    import tgscraper as tg
    posts = tg.scrape("mobydick_crypto", limit=100)
"""
from tgscraper import Scraper


class TelegramScraper:
    def __init__(self, base_url, num_messages=100):
        self.base_url = base_url
        self.num_messages = num_messages
        self.messages = []
        self.proxy = None

    def set_proxy(self, proxy):
        """تنظیم پراکسی برای درخواست‌ها"""
        self.proxy = proxy

    def fetch_messages(self):
        """Return the texts of the latest ``num_messages`` posts (newest first)."""
        with Scraper(proxies=self.proxy) as scraper:
            self.messages = [m.text for m in scraper.iter_messages(self.base_url, self.num_messages)]
        return self.messages
