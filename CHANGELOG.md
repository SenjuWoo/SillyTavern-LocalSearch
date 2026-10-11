# Changelog

## 1.1.0 — 2026-10-11

- One shared ddgs client instead of a new one per search (engine sessions stay warm).
- Identical searches within 10 minutes are answered from memory (`--cache-ttl`); swipes and regenerates no longer re-hit the engines. Empty answers are never cached.
- New options: `--safesearch`, `--region`, `--timelimit`, `--backend`, `--max-results`, `--timeout`, `--verbose`. The SillyTavern plugin passes them through `LOCAL_SEARCH_ARGS`.
- Quiet log by default: version, resolved options and failures with their cause; `--verbose` adds per-request lines.
- Relative links and non-http(s) image URLs are dropped; empty titles fall back to the URL.
- Clear error when the port is already taken.
- Plugin spawns the resolved Python executable directly, so stopping SillyTavern stops the process that owns the port.
- Installer always runs `pip install -U ddgs` (engines change; an old copy silently returns nothing).
- Tests: deterministic offline contract suite (fake engine); the live run is `--live`. CI on Python 3.10 and 3.13.

## 1.0.0

- First release: SearXNG-shaped keyless search for SillyTavern's Web Search extension, server plugin, one-shot installer, LM Studio fixes.
