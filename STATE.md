# STATE — SillyTavern Local Search

Updated 2026-10-11 · v1.1.0 · branch `main`

## Where things are
- Repo: `S:\Misc\SillyTavern-LocalSearch`; the live SillyTavern (`S:\Misc\SillyTavern`) runs it through the junction `plugins\local-search` → `st-plugin\`.
- Last known good: git tag `v1.1.0` / release zip; previous `v1.0.0`.

## Verified (2026-10-11)
- `python test_local_search.py --live`: offline contract suite + real engines, all pass (ddgs 9.16.0, Python 3.14)
- `node st-plugin/selfcheck.mjs`: start → real search → stop → port released
- `install.py --dry-run` against the live SillyTavern 1.19.0
- Extension-WebSearch 1.2.0 selectors and SillyTavern's `/api/search/searxng` flow re-read from source: unchanged

## Design decisions
- One shared DDGS client; 10-minute TTL cache (128 entries), empty results never cached.
- Quiet log by default (version, config, failures to stderr); `--verbose` per request.
- CI: offline suite is the gate; `--live` is informational (engines rate-limit runners).
