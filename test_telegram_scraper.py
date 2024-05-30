import unittest
from unittest.mock import patch, Mock
from telegram_scraper import TelegramScraper

class TestTelegramScraper(unittest.TestCase):
    
    @patch('telegram_scraper.requests.get')
    def test_fetch_messages(self, mock_get):
        # شبیه‌سازی پاسخ HTML
        mock_html = """
        <html>
        <body>
            <div class="tgme_widget_message_text">Message 1</div>
            <div class="tgme_widget_message_text">Message 2</div>
            <a class="tme_messages_more" href="/s/mobydick_crypto?before=12345"></a>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = mock_html
        mock_get.return_value = mock_response
        
        # ایجاد نمونه‌ای از TelegramScraper
        channel_url = 'https://t.me/s/mobydick_crypto'
        scraper = TelegramScraper(channel_url, 2)
        
        # استخراج پیام‌ها
        messages = scraper.fetch_messages()
        
        # بررسی نتایج
        self.assertEqual(len(messages), 2)
        self.assertIn('Message 1', messages)
        self.assertIn('Message 2', messages)
    
    @patch('telegram_scraper.requests.get')
    def test_set_proxy(self, mock_get):
        # ایجاد نمونه‌ای از TelegramScraper
        channel_url = 'https://t.me/s/mobydick_crypto'
        scraper = TelegramScraper(channel_url, 2)
        
        # تنظیم پراکسی
        scraper.set_proxy('http://127.0.0.1:8080')
        
        # شبیه‌سازی پاسخ HTML
        mock_html = """
        <html>
        <body>
            <div class="tgme_widget_message_text">Message 1</div>
        </body>
        </html>
        """
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = mock_html
        mock_get.return_value = mock_response
        
        # استخراج پیام‌ها
        messages = scraper.fetch_messages()
        
        # بررسی اینکه پراکسی تنظیم شده است
        mock_get.assert_called_with(channel_url, proxies={'http': 'http://127.0.0.1:8080', 'https': 'http://127.0.0.1:8080'})
        self.assertEqual(len(messages), 1)
        self.assertIn('Message 1', messages)

if __name__ == "__main__":
    unittest.main()
