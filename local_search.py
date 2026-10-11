"""A local, keyless search endpoint that SillyTavern already knows how to read.

SillyTavern's Web Search extension has no free backend. Of its sources, SerpApi,
Tavily, Serper and Z.AI all want an API key, KoboldCpp wants a KoboldCpp, and
SearXNG wants an instance URL. Public SearXNG instances answer captcha pages or
HTTP 429.

So this serves the SearXNG *shape* from ddgs metasearch results (DuckDuckGo,
Brave, Google, Wikipedia... picked automatically), locally, with
no account anywhere. Point the extension's SearXNG URL at this process.

The contract is narrow and comes from reading the extension, not from guessing.
Extension-WebSearch 1.2.0 parses exactly:

    #urls p.content                          -> result snippets
    #urls .url_header, #urls .url_wrapper    -> result links (href)
    .infobox p / .infobox a                  -> optional infobox (not emitted)
    #urls .detail img[data-src]              -> image results

SillyTavern's server also GETs the base URL first and, if it finds
href="/client*.css", fetches that too. Both are answered below so the flow
matches what the server expects.

Run:
    python local_search.py [--port 18888] [--host 127.0.0.1] [--safesearch off]
    python local_search.py --help      # every option

Binds to loopback by default. There is no auth, so do not expose it.
Logging is quiet by default (version, config and failures, to stderr);
--verbose adds one line per request.
"""

from __future__ import annotations

import argparse
import html
import logging
import sys
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - the message is the whole point
    sys.exit("ddgs is not installed. Run:  python -m pip install -U ddgs")

VERSION = "1.1.0"
log = logging.getLogger("local-search")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>local-search</title>
<link rel="stylesheet" href="/client.local.css"></head>
<body><div id="urls">{body}</div></body></html>"""


class Searcher:
    """One shared ddgs client (keeps engine sessions warm) plus a small TTL cache.

    SillyTavern repeats the same query on every swipe and regenerate; serving those
    from memory is faster and keeps the upstream engines from rate-limiting us.
    """

    def __init__(self, *, region="us-en", safesearch="moderate", timelimit=None,
                 backend="auto", max_results=10, timeout=10, cache_ttl=600, cache_size=128,
                 client=None):
        self.opts = {"region": region, "safesearch": safesearch, "timelimit": timelimit, "backend": backend}
        self.max_results = max_results
        self.cache_ttl = cache_ttl
        self.cache_size = cache_size
        self.client = client or DDGS(timeout=timeout)
        self._cache: OrderedDict[tuple[str, str], tuple[float, list[dict]]] = OrderedDict()
        self._lock = threading.Lock()

    def search(self, category: str, query: str) -> list[dict]:
        key = (category, query.casefold())
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < self.cache_ttl:
                self._cache.move_to_end(key)
                log.debug("cache hit %s %r", category, query)
                return hit[1]
        fn = self.client.images if category == "images" else self.client.text
        results = fn(query, max_results=self.max_results, **self.opts) or []
        if self.cache_ttl > 0 and results:  # never cache an empty answer: it is usually a transient block
            with self._lock:
                self._cache[key] = (now, results)
                self._cache.move_to_end(key)
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
        return results


def render_text(results: list[dict]) -> str:
    rows = []
    for item in results:
        href = item.get("href") or ""
        if not href.startswith(("http://", "https://")):
            continue  # relative links would resolve against SillyTavern, not the source
        rows.append(
            '<article class="result">'
            '<a class="url_wrapper" href="{href}">{title}</a>'
            '<p class="content">{snippet}</p>'
            "</article>".format(
                href=html.escape(href, quote=True),
                title=html.escape(item.get("title") or href),
                snippet=html.escape(item.get("body") or ""),
            )
        )
    return "\n".join(rows)


def render_images(results: list[dict]) -> str:
    # data-src, not src: that is the attribute the extension reads.
    return "\n".join(
        '<div class="detail"><img data-src="{}"></div>'.format(html.escape(item["image"], quote=True))
        for item in results
        if str(item.get("image") or "").startswith(("http://", "https://"))
    )


def make_handler(searcher: Searcher) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"local-search/{VERSION}"

        def _send(self, body: str, status: int = 200, ctype: str = "text/html; charset=utf-8") -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
            parsed = urlparse(self.path)

            if parsed.path == "/client.local.css":
                self._send("/* intentionally empty */", ctype="text/css")
                return

            if parsed.path != "/search":
                # The base page. SillyTavern fetches this before searching.
                self._send(PAGE.format(body=""))
                return

            params = parse_qs(parsed.query)
            query = (params.get("q") or [""])[0].strip()[:500]
            category = "images" if (params.get("categories") or [""])[0].strip().lower() == "images" else "text"

            if not query:
                self._send(PAGE.format(body=""))
                return

            started = time.monotonic()
            try:
                results = searcher.search(category, query)
                body = render_images(results) if category == "images" else render_text(results)
            except Exception as exc:  # a dead upstream must not 500 the extension: it has no error path
                log.warning("%s search failed for %r: %s: %s", category, query, type(exc).__name__, exc)
                body = ""
            log.debug("%s %r -> %d bytes in %.2fs", category, query, len(body), time.monotonic() - started)
            self._send(PAGE.format(body=body))

        def log_message(self, fmt: str, *args) -> None:
            log.debug("%s - %s", self.address_string(), fmt % args)

    return Handler


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SearXNG-shaped local search for SillyTavern (keyless, via ddgs).")
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1; there is no auth)")
    ap.add_argument("--port", type=int, default=18888)
    ap.add_argument("--region", default="us-en", help="e.g. us-en, uk-en, de-de, wt-wt (no region)")
    ap.add_argument("--safesearch", default="moderate", choices=["on", "moderate", "off"])
    ap.add_argument("--timelimit", default=None, choices=["d", "w", "m", "y"], help="only results from the last day/week/month/year")
    ap.add_argument("--backend", default="auto", help='ddgs engines, e.g. "auto", "duckduckgo", "bing,brave,wikipedia"')
    ap.add_argument("--max-results", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=10, help="per-engine request timeout in seconds")
    ap.add_argument("--cache-ttl", type=int, default=600, help="seconds to reuse an identical search (0 = off)")
    ap.add_argument("--verbose", action="store_true", help="log every request (default: startup, config and failures only)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.verbose:
        for noisy in ("ddgs", "primp", "httpx", "httpcore"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    searcher = Searcher(region=args.region, safesearch=args.safesearch, timelimit=args.timelimit,
                        backend=args.backend, max_results=max(1, args.max_results), timeout=args.timeout,
                        cache_ttl=max(0, args.cache_ttl))
    try:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(searcher))
    except OSError as exc:
        log.error("cannot listen on %s:%d: %s (already running?)", args.host, args.port, exc)
        return 1
    server.daemon_threads = True

    try:
        from importlib.metadata import version as pkg_version
        ddgs_version = pkg_version("ddgs")
    except Exception:  # noqa: BLE001 - informational only
        ddgs_version = "?"
    log.info("v%s (ddgs %s, Python %s) on http://%s:%d", VERSION, ddgs_version, sys.version.split()[0], args.host, args.port)
    log.info("config: region=%s safesearch=%s timelimit=%s backend=%s max_results=%d cache_ttl=%ds verbose=%s",
             args.region, args.safesearch, args.timelimit or "any", args.backend, searcher.max_results,
             searcher.cache_ttl, args.verbose)
    log.info("point SillyTavern's Web Search -> SearXNG URL at http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
