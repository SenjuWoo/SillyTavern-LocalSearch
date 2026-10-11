"""Assert the contract SillyTavern actually relies on.

The extension does not consume JSON. It runs four CSS selectors over whatever
HTML comes back, so "the server returned 200" proves nothing -- a page with the
wrong class names is a silent zero-results bug. These checks parse the real
response the same way the extension does.

Run:  python test_local_search.py          # offline: fake engine, deterministic
      python test_local_search.py --live   # also hit the real search engines
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import local_search

LIVE_PORT = 18899  # deliberately not 18888, so a running instance is not disturbed
failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    failures += 0 if condition else 1
    print("%-4s %s%s" % ("PASS" if condition else "FAIL", name, ("  -- " + detail) if detail and not condition else ""))


def get(base: str, path: str, timeout: int = 60) -> str:
    with urllib.request.urlopen(base + path, timeout=timeout) as response:
        return response.read().decode("utf-8")


def contract(base: str, text_query: str, image_query: str) -> None:
    # 1. SillyTavern GETs the base URL first and requires it to succeed.
    page = get(base, "/")
    check("base page serves and carries #urls", 'id="urls"' in page)

    # 2. It then looks for href="(/client.+\.css)". ".+" needs at least one
    #    character between "client" and ".css" -- "/client.css" would NOT
    #    match, which is why the served name is longer than that.
    match = re.search(r'href="(/client.+\.css)"', page)
    check("client css href matches SillyTavern's regex", bool(match), "no href satisfies /client.+\\.css")
    if match:
        check("that css path actually serves", isinstance(get(base, match.group(1)), str))

    # 3. The selectors the extension runs over search results.
    html = get(base, "/search?q=" + text_query, timeout=90)
    urls_block = re.search(r'<div id="urls">(.*)</div>', html, re.S)
    check("search response has the #urls container", bool(urls_block))
    inner = urls_block.group(1) if urls_block else ""
    links = re.findall(r'class="url_(?:wrapper|header)"[^>]*href="([^"]+)"', inner)
    snippets = re.findall(r'<p class="content">(.*?)</p>', inner, re.S)
    check("links carry .url_wrapper/.url_header with href", bool(links), "0 links -- the extension would report no results")
    check("snippets carry p.content", bool(snippets))
    check("every link is absolute", all(l.startswith("http") for l in links), "relative hrefs resolve against SillyTavern")

    # 4. Images use data-src, not src. Getting this wrong is invisible because text search keeps working.
    images = get(base, "/search?q=%s&categories=images" % image_query, timeout=90)
    check("image results use data-src", bool(re.findall(r'<img[^>]*data-src="([^"]+)"', images)), "0 images")

    # 5. An empty query must not 500; the extension has no error path.
    check("empty query returns a valid empty page", 'id="urls"' in get(base, "/search?q="))


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.fail = False

    def text(self, query: str, **kw):
        self.calls.append(("text", query, kw))
        if self.fail:
            raise RuntimeError("upstream blocked")
        return [
            {"href": "https://example.org/a?x=1&y=2", "title": 'A <b>"bold"</b> title', "body": "Snippet <script>alert(1)</script>"},
            {"href": "/relative/path", "title": "dropped", "body": "relative links are dropped"},
            {"href": "https://example.org/b", "title": "", "body": ""},
        ]

    def images(self, query: str, **kw):
        self.calls.append(("images", query, kw))
        return [{"image": "https://img.example.org/fox.jpg"}, {"image": "javascript:alert(1)"}, {}]


def offline() -> None:
    print("== offline (fake engine) ==")
    fake = FakeClient()
    searcher = local_search.Searcher(region="uk-en", safesearch="off", timelimit="w", backend="auto",
                                     max_results=7, cache_ttl=600, client=fake)
    server = ThreadingHTTPServer(("127.0.0.1", 0), local_search.make_handler(searcher))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    try:
        contract(base, "rust+programming", "red+fox")
        html = get(base, "/search?q=rust+programming")
        check("html is escaped", "<script>" not in html and "&lt;script&gt;" in html and "&amp;y=2" in html)
        check("relative links are dropped", "/relative/path" not in html)
        check("empty title falls back to the url", ">https://example.org/b</a>" in html)
        imgs = get(base, "/search?q=red+fox&categories=images")
        check("only http(s) images are emitted", "javascript:" not in imgs and imgs.count("data-src=") == 1)
        kw = fake.calls[0][2]
        check("options reach ddgs", kw == {"max_results": 7, "region": "uk-en", "safesearch": "off", "timelimit": "w", "backend": "auto"}, str(kw))
        before = len(fake.calls)
        get(base, "/search?q=RUST+programming")
        check("identical searches are served from cache", len(fake.calls) == before)
        fake.fail = True
        failed = get(base, "/search?q=never+seen")
        check("upstream failure returns a valid empty page, not a 500", 'id="urls"' in failed and "url_wrapper" not in failed)
        fake.fail = False
        get(base, "/search?q=never+seen")
        check("failures are not cached", fake.calls[-1][1] == "never seen" and len([c for c in fake.calls if c[1] == "never seen"]) == 2)
        tiny = local_search.Searcher(cache_ttl=600, cache_size=2, client=FakeClient())
        for q in ("a", "b", "c"):
            tiny.search("text", q)
        check("cache is bounded", len(tiny._cache) == 2 and ("text", "a") not in tiny._cache)
        args = local_search.parse_args(["--safesearch", "off", "--port", "1"])
        check("cli defaults are sane", args.region == "us-en" and args.safesearch == "off" and args.cache_ttl == 600 and not args.verbose)
    finally:
        server.shutdown()
        server.server_close()


def live() -> None:
    print("== live (real engines) ==")
    base = "http://127.0.0.1:%d" % LIVE_PORT
    proc = subprocess.Popen([sys.executable, "local_search.py", "--port", str(LIVE_PORT)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            if proc.poll() is not None:
                raise AssertionError("server exited early with code %s" % proc.returncode)
            try:
                get(base, "/", timeout=2)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        contract(base, "rust+programming+language", "red+fox")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    offline()
    if "--live" in sys.argv:
        live()
    print("\n%s" % ("all checks passed" if not failures else "%d CHECK(S) FAILED" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
