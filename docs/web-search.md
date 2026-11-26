# Free web search

[Back to the README](../README.md)

## Why this is needed

SillyTavern's [Web Search extension](https://github.com/SillyTavern/Extension-WebSearch)
ships six sources and **none of them is both free and self-contained**:

| Source | What it wants |
|---|---|
| SerpApi, Tavily, Serper, Z.AI | an API key |
| KoboldCpp | a running KoboldCpp with websearch |
| SearXNG | the URL of a SearXNG instance |

SearXNG is the only keyless one, so the usual advice is "point it at a public
instance". Measured, that does not work:

```
https://searx.be           HTTP 200  -> captcha page, 0 results
https://baresearch.org     HTTP 200  -> 0 results
https://priv.au            HTTP 429
https://searxng.site       HTTP 429
https://search.inetol.net  HTTP 429
```

Self-hosting real SearXNG normally means Docker.

So `local_search.py` serves the **SearXNG shape** that SillyTavern already
parses, backed by DuckDuckGo through the `ddgs` package. No key, no account, no
container.

## Setting it up by hand

`Install.bat` does all of this. If you would rather not run it:

```bash
python -m pip install -U ddgs
```

Run `Start-LocalSearch.bat` (or `python local_search.py`) and leave it open.
In SillyTavern, **Extensions → Web Search**:

- Source: **SearXNG**
- SearXNG URL: `http://127.0.0.1:18888`
- **Trigger Phrases: off**, **Backticks: on**

Then wrap a query in backticks to search.

## Starting it automatically with SillyTavern

`st-plugin/` is a SillyTavern **server plugin**. SillyTavern starts the search
endpoint when it boots and kills it when it shuts down, so there is no window to
remember and nothing to leave running afterwards.

It needs `enableServerPlugins: true` in SillyTavern's `config.yaml`, then a
junction from SillyTavern's `plugins` folder to `st-plugin`:

```bat
mklink /J "C:\path\to\SillyTavern\plugins\local-search" "C:\path\to\SillyTavern-LocalSearch\st-plugin"
```

A junction rather than a copy, so pulling this repo updates the plugin with no
second step. SillyTavern's plugin auto-update ignores it, because a junction to
a subdirectory is not a Git repository root.

On the next start SillyTavern logs:

```
Initializing plugin from plugins\local-search\index.mjs
[local-search] started on http://127.0.0.1:18888 (pid 12345)
```

The plugin probes the port first, so running `Start-LocalSearch.bat` by hand
still works — SillyTavern sees the endpoint is up and does not start a second
copy. If no Python on `PATH` can `import ddgs` it says so and starts nothing,
instead of failing silently at the first search.

Override the defaults with the `LOCAL_SEARCH_PORT` / `LOCAL_SEARCH_HOST`
environment variables if `18888` is taken, and pass any option below through
`LOCAL_SEARCH_ARGS` (for example `LOCAL_SEARCH_ARGS=--safesearch off --region uk-en`).

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `--safesearch on/moderate/off` | `moderate` | Engine-side filtering. `off` for unfiltered results |
| `--region` | `us-en` | Result locale, e.g. `uk-en`, `de-de`, `wt-wt` (none) |
| `--timelimit d/w/m/y` | any | Only results from the last day / week / month / year |
| `--backend` | `auto` | ddgs engines: `auto` spreads text searches over Brave, DuckDuckGo, Google, Mojeek, Startpage, Wikipedia, Yahoo… (images: Bing, DuckDuckGo); or name them, e.g. `duckduckgo` or `brave,wikipedia` |
| `--max-results` | `10` | Results per search |
| `--cache-ttl` | `600` | Seconds an identical search is answered from memory (swipes and regenerates repeat the query). `0` = off. Empty answers are never cached |
| `--timeout` | `10` | Per-engine request timeout, seconds |
| `--verbose` | off | One log line per request and cache hit |

## Log

Quiet by default: the version, the resolved options and every failure (with
its cause) go to stderr — the `Start-LocalSearch.bat` window, or SillyTavern's
console prefixed `[local-search]` when the plugin runs it. Add `--verbose` for
per-request lines.

```bash
node st-plugin/selfcheck.mjs   # start -> real search -> stop -> port released
```

## Running it by hand, without a window

The `.bat` keeps a console window open on purpose, so it is obvious when search
is on. To run it without a window:

```bat
start "" pythonw local_search.py --port 18888
```

`pythonw` has no console, so nothing then tells you it is running. Check with
`curl http://127.0.0.1:18888/`.

## What it actually implements

`Extension-WebSearch` 1.2.0 parses exactly four things out of the returned
HTML, and only these are produced:

```
#urls p.content                        -> result snippets
#urls .url_header, #urls .url_wrapper  -> result links (href attribute)
#urls .detail img[data-src]            -> image results (categories=images)
.infobox p / .infobox a                -> optional; not emitted
```

SillyTavern's server also GETs the base URL before searching and, if the page
links a `/client*.css`, fetches that too. Both are answered, so the request
flow matches a real instance rather than relying on a lucky shortcut.

`test_local_search.py` asserts that contract the way the extension parses it,
offline against a fake engine (escaping, relative-link and non-http image
filtering, option pass-through, caching, upstream failure), and with `--live`
against the real engines. Run it after changing anything:

```bash
python test_local_search.py          # offline, deterministic
python test_local_search.py --live   # plus the real engines
```

## Limits worth knowing

- **It is public search engines.** Result quality and rate limits are theirs
  (`ddgs` spreads queries across several). A burst can start returning nothing;
  wait a minute. Identical searches within 10 minutes come from the cache.
- **Keep `ddgs` current.** Engines change their pages; `Install.bat` /
  `install.py` always runs `pip install -U ddgs`.
- **Snippets only, by default.** SillyTavern's *Visit* option fetches the linked
  pages for real content. It is off by default because it costs several seconds
  per message. Turn it on in the extension panel if snippets are too thin.
- **Loopback only.** There is no authentication. Do not bind it to `0.0.0.0`.
- A failed upstream returns an empty result page rather than an error, so a
  rate-limited search degrades to "no results" instead of breaking generation.
