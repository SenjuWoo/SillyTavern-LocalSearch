# STATE — SillyTavern Local Search

Updated 2026-11-26 · v1.1.1 · branch `main`

## Where things are
- A live SillyTavern runs this repo through the junction `<SillyTavern>\plugins\local-search` → `st-plugin\`.
- Last known good: git tag `v1.1.1` / release zip; previous `v1.1.0`, `v1.0.0`.
- Deep reference lives in `docs/`; README presentation images in `docs/presentation/`.

## Verified (2026-11-26, 1.1.1)
- `python test_local_search.py`: offline contract suite, all pass (ddgs 9.16.1, Python 3.14)
- `node st-plugin/argscheck.mjs`: failed on 1.1.0 (no whitespace split), passes after the fix
- `node st-plugin/selfcheck.mjs` with `LOCAL_SEARCH_ARGS="--region uk-en --safesearch off"`: the endpoint logs `region=uk-en safesearch=off`, a real search returns links, the port is released
- `install.py --dry-run` against a scratch SillyTavern layout

## Verified (2026-10-11, 1.1.0)
- `python test_local_search.py --live`: offline contract suite + real engines, all pass (ddgs 9.16.0, Python 3.14)
- `node st-plugin/selfcheck.mjs`: start → real search → stop → port released
- `install.py --dry-run` against a live SillyTavern 1.19.0
- Extension-WebSearch 1.2.0 selectors and SillyTavern's `/api/search/searxng` flow re-read from source: unchanged

## Design decisions
- One shared DDGS client; 10-minute TTL cache (128 entries), empty results never cached.
- Quiet log by default (version, config, failures to stderr); `--verbose` per request.
- CI: offline suite and the plugin argument check are the gate; `--live` is informational (engines rate-limit runners).
