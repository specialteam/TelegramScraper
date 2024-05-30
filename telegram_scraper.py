import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class TelegramScraper:
    def __init__(self, base_url, num_messages=100):
        self.base_url = base_url
        self.num_messages = num_messages
        self.messages = []
        self.proxy = None

    def set_proxy(self, proxy):
        """تنظیم پراکسی برای درخواست‌ها"""
        self.proxy = {
            'http': proxy,
            'https': proxy
        }

    def fetch_messages(self):
        current_url = self.base_url
        while len(self.messages) < self.num_messages:
            response = self._make_request(current_url)
            
            if response.status_code != 200:
                print(f"Failed to retrieve the page: {response.status_code}")
                return self.messages
            
            soup = BeautifulSoup(response.content, 'html.parser')
            self._parse_messages(soup)
            
            next_url = self._find_next_page(soup)
            if next_url:
                current_url = urljoin('https://t.me', next_url)
            else:
                break

        return self.messages

    def _make_request(self, url):
        """ارسال درخواست HTTP با یا بدون پراکسی"""
        if self.proxy:
            return requests.get(url, proxies=self.proxy)
        else:
            return requests.get(url)

    def _parse_messages(self, soup):
        message_elements = soup.find_all('div', class_='tgme_widget_message_text')
        for element in message_elements:
            message_text = element.get_text(strip=True)
            if message_text not in self.messages:
                self.messages.append(message_text)
            if len(self.messages) >= self.num_messages:
                break

    def _find_next_page(self, soup):
        next_button = soup.find('a', class_='tme_messages_more')
        if next_button and next_button.has_attr('href'):
            return next_button['href']
        return None
