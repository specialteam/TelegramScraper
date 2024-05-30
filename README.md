
# Telegram Scraper

Telegram Scraper is a Python tool for scraping messages from a Telegram channel using web scraping techniques. This tool extracts a specified number of messages from a given Telegram channel URL and supports the use of a proxy.

## Features

- Extract messages from a Telegram channel.
- Supports pagination to retrieve older messages.
- Optional proxy support for making requests.

## Requirements

- Python 3.x
- `requests` library
- `beautifulsoup4` library

## Installation

First, clone the repository:

```bash
git clone https://github.com/yourusername/telegram-scraper.git
cd telegram-scraper
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Usage

### Example Script

Here's an example script (`example.py`) to demonstrate how to use the `TelegramScraper` class:

```python
from telegram_scraper import TelegramScraper

def main():
    # URL of the Telegram channel
    channel_url = 'https://t.me/s/mobydick_crypto'
    
    # Create an instance of TelegramScraper
    scraper = TelegramScraper(channel_url, 100)
    
    # Set proxy if needed
    # scraper.set_proxy('http://your_proxy_address:port')
    
    # Fetch messages
    messages = scraper.fetch_messages()
    
    # Display messages
    for i, message in enumerate(messages, 1):
        print(f"{i}: {message}")

if __name__ == "__main__":
    main()
```

To run the example script:

```bash
python example.py
```

### Class Details

#### TelegramScraper

A class for scraping messages from a Telegram channel.

##### `__init__(self, base_url, num_messages=100)`

- `base_url` (str): The URL of the Telegram channel.
- `num_messages` (int): The number of messages to retrieve.

##### `set_proxy(self, proxy)`

- `proxy` (str): The proxy address (e.g., `'http://127.0.0.1:8080'`).

Sets the proxy for making requests.

##### `fetch_messages(self)`

Fetches messages from the Telegram channel.

- Returns: `list` of messages.

## Tests

Unit tests for the `TelegramScraper` class are provided in `test_telegram_scraper.py`.

### Running Tests

To run the tests, use the following command:

```bash
python -m unittest test_telegram_scraper.py
```

## Project Structure

```
.
├── telegram_scraper.py
├── test_telegram_scraper.py
├── example.py
├── requirements.txt
└── README.md
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Contact

If you have any questions or suggestions, please feel free to contact me at your.email@example.com.
