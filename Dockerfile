FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE telegram_scraper.py ./
COPY tgscraper ./tgscraper
RUN pip install --no-cache-dir ".[all]"

# Data (exports, state file) goes here: docker run -v "$PWD/data:/data" ...
WORKDIR /data
ENV TGSCRAPER_STATE=/data/.tgscraper-state.json
EXPOSE 8501

ENTRYPOINT ["tgscraper"]
CMD ["--help"]
