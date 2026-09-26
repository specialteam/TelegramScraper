# AGENTS.md

Guide for AI coding agents working on this repository. Users of the tool should read
[README.md](README.md) or the skill in `.claude/skills/telegram-scraper/SKILL.md`.

## Setup & checks

```bash
pip install -e ".[dev]"
pytest -q                                   # offline; HTTP is mocked with respx
flake8 . --max-line-length=127
```

The public site `t.me` is never called in tests. Parser tests use `tests/fixtures/page1.html`;
paging tests build pages with `tests/conftest.py::make_page`.

## Architecture

- `tgscraper/parser.py` — the only place that knows Telegram's HTML classes (`tgme_widget_message*`).
  If Telegram changes its markup, fix it here and update the fixture.
- `tgscraper/client.py` — `Scraper` (sync) and `AsyncScraper` share paging logic in `_Walk.feed`.
  Pages come oldest→newest; the public API yields newest→oldest.
- `tgscraper/__init__.py` — the simple functional API (`scrape`, `search`, ...). Keep it simple.
- `tgscraper/cli.py` — `tgscraper <channel>` is shorthand for `tgscraper scrape <channel>`.
  Every command should support `--json`.
- `tgscraper/mcp_server.py` — MCP tools; return JSON-friendly dicts, never raise to the client
  (return `{"error": ...}`), strip `html`, cap limits. Works with `mcp` 1.x (FastMCP) and 2.x (MCPServer).

## Conventions

- Python 3.9+ (`from __future__ import annotations`, `typing.Optional`), core deps only `httpx` + `beautifulsoup4`;
  everything else is an optional extra (`excel`, `mcp`, `dashboard`).
- New features need a test and a line in README (and the skill / MCP tool if agents should use them).
- `telegram_scraper.py` is a backward-compatibility shim; don't remove it.
