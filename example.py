from telegram_scraper import TelegramScraper

def main():
    # URL کانال
    channel_url = 'https://t.me/s/mobydick_crypto'
    
    # ایجاد نمونه‌ای از TelegramScraper
    scraper = TelegramScraper(channel_url, 100)
    
    # تنظیم پراکسی در صورت نیاز
    # scraper.set_proxy('http://your_proxy_address:port')
    
    # استخراج پیام‌ها
    messages = scraper.fetch_messages()
    
    # نمایش پیام‌ها
    for i, message in enumerate(messages, 1):
        print(f"{i}: {message}")

if __name__ == "__main__":
    main()
