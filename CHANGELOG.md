# Changelog

## 1.1.1 — 2026-11-26

- Fix: the server plugin split `LOCAL_SEARCH_ARGS` on the letter `s` instead of on whitespace, so `--safesearch off --region uk-en` reached `local_search.py` as `--`, `afe`, `earch off --region uk-en` and every extra option was lost. It now splits on whitespace (`splitArgs`, exported for the test).
- New offline check `node st-plugin/argscheck.mjs`, run in CI.
- README rebuilt around install, options and proof images; the measured deep dives moved unchanged into `docs/` (what the installer changes, free web search, LM Studio, run-time costs, Vectors and Connection Profiles).

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
