#!/usr/bin/env python3
"""Download a Read the Docs site as Markdown that Claude can search quickly.

Example:
    uv run fetch_rtd_docs.py https://discordpy.readthedocs.io --contact you@example.com

Output (default): <project>/.claude/docs/<site>/<version>/
    _toc.md         start here: one line per page (title, summary, size)
    .manifest.json  cache for skip-unchanged runs (ETag / Last-Modified / hash)
    <page>.md       one Markdown file per docs page; links point to local files

Page discovery (--discovery auto): sitemap.xml -> Sphinx searchindex.js -> link crawl.

Follows https://docs.readthedocs.com/platform/stable/automated-access.html:
under 4 requests/second, an identifying User-Agent with contact info, robots.txt
respected, conditional requests (ETag / Last-Modified) so unchanged pages are skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as to_markdown

TOOL = "fetch-rtd-docs"
TOOL_VERSION = "1.0"
MIN_DELAY = 0.25  # RTD asks for fewer than 4 requests/second
MAX_RETRIES = 3
MAX_CONSECUTIVE_FAILURES = 5
LARGE_PAGE_BYTES = 50_000
MANIFEST_NAME = ".manifest.json"
TOC_NAME = "_toc.md"

SKIP_PAGES = {"genindex.html", "search.html", "py-modindex.html", "404.html"}
SKIP_DIRS = ("_modules/", "_sources/", "_static/", "_images/", "_downloads/")

# Where the real page content lives, most specific first (Sphinx, MkDocs, Furo, pydata, ...).
MAIN_SELECTORS = (
    "div[role=main]",
    "article[role=main]",
    "main[role=main]",
    "article.md-content__inner",
    "article.bd-article",
    "main#main-content",
    "main",
    "article",
    "div.document",
    "div.body",
    "div#content",
    "body",
)

# Chrome around the content that only costs tokens.
NOISE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "form",
    "button",
    "iframe",
    "svg",
    "a.headerlink",
    ".headerlink",
    ".copybtn",
    ".rst-footer-buttons",
    "[role=contentinfo]",
    "[role=navigation]",
    ".breadcrumbs",
    ".wy-breadcrumbs",
    ".sphinxsidebar",
    ".sidebar-drawer",
    ".related",
    ".edit-this-page",
    ".md-nav",
    ".md-sidebar",
    ".md-footer",
    ".bd-sidebar",
    ".prev-next-area",
    ".bd-toc",
)

SIGNATURE_SELECTOR = (
    "dt.sig, dl.class > dt, dl.function > dt, dl.method > dt, dl.attribute > dt, "
    "dl.data > dt, dl.exception > dt, dl.classmethod > dt, dl.staticmethod > dt, "
    "dl.property > dt, dl.describe > dt"
)

ADMONITION_SELECTOR = (
    "div.admonition, aside.admonition, div.versionadded, div.versionchanged, "
    "div.versionremoved, div.deprecated"
)


def log(message: str = "") -> None:
    print(message, file=sys.stderr, flush=True)


class RobotsDisallowed(Exception):
    pass


class Abort(Exception):
    pass


# --------------------------------------------------------------------------- URLs


def norm(url: str) -> str:
    """Drop fragment and query; fold '/index.html' into the directory URL."""
    url, _ = urldefrag(url)
    url = url.split("?")[0]
    if url.endswith("/index.html"):
        url = url[: -len("index.html")]
    return url


def is_doc_url(url: str, root: str) -> bool:
    """True for HTML documentation pages under the docs root."""
    if not url.startswith(root):
        return False
    rel = url[len(root) :]
    if rel.startswith(SKIP_DIRS) or rel in SKIP_PAGES:
        return False
    last = rel.rsplit("/", 1)[-1]
    return not ("." in last and not last.endswith(".html"))


def local_rel(url: str, root: str) -> str:
    """Map a normalized page URL to its relative .md path."""
    rel = url[len(root) :]
    if rel == "" or rel.endswith("/"):
        rel += "index"
    elif rel.endswith(".html"):
        rel = rel[: -len(".html")]
    rel = re.sub(r"[^A-Za-z0-9._/\-+]", "_", rel)
    rel = "/".join(seg for seg in rel.split("/") if seg not in ("", ".", ".."))
    return (rel or "index") + ".md"


# ------------------------------------------------------------------------ fetching


class Fetcher:
    def __init__(self, user_agent: str, delay: float, timeout: float = 30.0) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.ua_token = user_agent.split("/")[0]
        self.delay = delay
        self.timeout = timeout
        self.robots: robotparser.RobotFileParser | None = None
        self.requests_made = 0
        self._last = 0.0

    def load_robots(self, origin: str) -> None:
        parser = robotparser.RobotFileParser()
        try:
            resp = self.get(origin + "/robots.txt", check_robots=False)
            if resp.status_code == 200:
                parser.parse(resp.content.decode("utf-8", "replace").splitlines())
            else:
                parser.parse([])
                parser.allow_all = True
        except requests.RequestException:
            parser.parse([])
            parser.allow_all = True
        self.robots = parser
        crawl_delay = parser.crawl_delay(self.ua_token)
        if crawl_delay:
            self.delay = max(self.delay, float(crawl_delay))
            log(f"robots.txt asks for Crawl-delay {crawl_delay}s; using it")

    def get(
        self, url: str, headers: dict | None = None, check_robots: bool = True
    ) -> requests.Response:
        if (
            check_robots
            and self.robots is not None
            and not self.robots.can_fetch(self.ua_token, url)
        ):
            raise RobotsDisallowed(url)
        for attempt in range(MAX_RETRIES + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
            except requests.RequestException:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(2**attempt)
                continue
            self.requests_made += 1
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After", "")
                pause = min(
                    int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1),
                    60,
                )
                log(
                    f"  HTTP {resp.status_code} from server, waiting {pause}s before retry"
                )
                time.sleep(pause)
                continue
            return resp
        raise RuntimeError("unreachable")


# --------------------------------------------------------------------- discovery


def read_sitemap(fetcher: Fetcher, url: str, depth: int = 0) -> list[str]:
    try:
        resp = fetcher.get(url)
    except requests.RequestException, RobotsDisallowed:
        return []
    if resp.status_code != 200 or len(resp.content) > 5_000_000:
        return []
    try:
        tree = ET.fromstring(resp.content)
    except ET.ParseError:
        return []
    locs = [
        (el.text or "").strip()
        for el in tree.iter()
        if el.tag.rsplit("}", 1)[-1] == "loc" and (el.text or "").strip()
    ]
    if tree.tag.rsplit("}", 1)[-1] == "sitemapindex":
        urls: list[str] = []
        if depth < 2:
            for child in locs[:20]:
                urls += read_sitemap(fetcher, child, depth + 1)
        return urls
    return locs


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def discover(
    fetcher: Fetcher, origin: str, root: str, mode: str
) -> tuple[str, list[str]]:
    """Return (method, page URLs). An empty list means 'crawl links while processing'."""
    if mode in ("auto", "sitemap"):
        for sitemap in (root + "sitemap.xml", origin + "/sitemap.xml"):
            pages = unique(
                [
                    norm(u)
                    for u in read_sitemap(fetcher, sitemap)
                    if is_doc_url(norm(u), root)
                ]
            )
            if any(p != root for p in pages):
                return f"sitemap ({sitemap})", unique([root] + pages)
        if mode == "sitemap":
            return "sitemap (no page-level URLs found)", []
    if mode in ("auto", "searchindex"):
        try:
            resp = fetcher.get(root + "searchindex.js")
        except requests.RequestException, RobotsDisallowed:
            resp = None
        if resp is not None and resp.status_code == 200:
            text = resp.content.decode("utf-8", "replace")
            # Sphinx writes JS objects, often with unquoted keys: docnames:["a","b"]
            match = re.search(r"[\"']?docnames[\"']?\s*:\s*(\[.*?\])", text, re.S)
            if match:
                try:
                    names = json.loads(match.group(1))
                except json.JSONDecodeError:
                    names = []
                pages = [norm(f"{root}{n}.html") for n in names if isinstance(n, str)]
                pages = unique([root] + [p for p in pages if is_doc_url(p, root)])
                if len(pages) > 1:
                    return "searchindex.js", pages
        if mode == "searchindex":
            return "searchindex.js (not found)", []
    return "link crawl", []


def available_versions(fetcher: Fetcher, origin: str) -> list[str]:
    found = []
    for loc in read_sitemap(fetcher, origin + "/sitemap.xml"):
        m = re.match(r"^https?://[^/]+/([^/]+)/([^/]+)/", loc)
        if m:
            found.append(f"{m.group(1)}/{m.group(2)}")
    return unique(found)


# -------------------------------------------------------------------- conversion


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def shorten(text: str, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _code_language(pre) -> str:
    for el in [pre.find("code"), *pre.parents]:
        if el is None:
            continue
        for cls in el.get("class") or []:
            if cls.startswith("highlight-"):
                lang = cls[len("highlight-") :]
            elif cls.startswith("language-"):
                lang = cls[len("language-") :]
            else:
                continue
            return "" if lang in {"default", "none", "text"} else lang
    return ""


def tidy(md: str) -> str:
    """Trim trailing spaces and extra blank lines, leaving code fences untouched."""
    out: list[str] = []
    blank = 0
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line.rstrip())
            blank = 0
            continue
        if in_fence:
            out.append(line)
            continue
        line = line.rstrip()
        if not line:
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(line)
    return "\n".join(out).strip() + "\n"


def convert_html(
    content: bytes, page_url: str, root: str
) -> tuple[str, str, str, list[str]]:
    """Return (title, summary, markdown body, in-docs links)."""
    soup = BeautifulSoup(content, "html.parser")
    title_tag = soup.find("title")

    main = None
    for selector in MAIN_SELECTORS:
        candidate = soup.select_one(selector)
        if candidate is not None and candidate.get_text(strip=True):
            main = candidate
            break
    if main is None:
        main = soup.body or soup

    for selector in NOISE_SELECTORS:
        for el in main.select(selector):
            el.extract()
    for el in main.find_all(lambda t: t.name and t.name.startswith("readthedocs-")):
        el.extract()
    for el in main.select(".viewcode-link"):
        (el.find_parent("a") or el).extract()

    # Sphinx object signatures -> headings, so API pages stay navigable.
    for dt in main.select(SIGNATURE_SELECTOR):
        text = clean(dt.get_text(""))
        heading = soup.new_tag("h4")
        code = soup.new_tag("code")
        code.string = text
        heading.append(code)
        dt.replace_with(heading)
    # Remaining definition lists: term in bold, definition as its own block.
    for dt in main.find_all("dt"):
        strong = soup.new_tag("strong")
        strong.extend(list(dt.contents))
        dt.append(strong)
        dt.name = "p"
    for dd in main.find_all("dd"):
        dd.name = "div"

    # Notes, warnings and "added in version" blocks matter for decisions: keep as quotes.
    for el in main.select(ADMONITION_SELECTOR):
        el.name = "blockquote"
        label = el.find("p", class_="admonition-title")
        if label is not None:
            label.append(":")
            label.name = "strong"

    for img in main.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if alt:
            img.replace_with(NavigableString(f"[image: {alt}]"))
        else:
            img.extract()

    links: list[str] = []
    page_dir = posixpath.dirname(local_rel(norm(page_url), root))
    for a in main.find_all("a"):
        a.attrs.pop("title", None)  # tooltip text only adds tokens
        href = a.get("href")
        if not href:
            a.unwrap()
            continue
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        absolute = urljoin(page_url, href)
        base, fragment = urldefrag(absolute)
        target = norm(base)
        if is_doc_url(target, root):
            rel = posixpath.relpath(local_rel(target, root), page_dir or ".")
            a["href"] = rel + (f"#{fragment}" if fragment else "")
            links.append(target)
        else:
            a["href"] = absolute

    h1 = main.find("h1")
    title = clean(h1.get_text()) if h1 is not None else ""
    if not title and title_tag is not None:
        title = re.split(r"\s+[—–|]\s+|\s+-\s+", clean(title_tag.get_text()))[0]
    if not title:
        title = posixpath.basename(local_rel(norm(page_url), root))[:-3]

    summary = ""
    for p in main.find_all("p"):
        if p.find_parent("blockquote") is not None:
            continue
        text = clean(p.get_text())
        if len(text) >= 20:
            summary = shorten(text)
            break

    body = to_markdown(
        str(main),
        heading_style="ATX",
        bullets="-",
        code_language_callback=_code_language,
        escape_underscores=False,
        escape_asterisks=False,
        escape_misc=False,
    )
    body = tidy(body)
    if not body.startswith("# "):
        body = f"# {title}\n\n{body}"
    return title, summary, body, unique(links)


def frontmatter(title: str, url: str, version: str) -> str:
    return (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"url: {url}\n"
        f"version: {version}\n"
        f"fetched: {date.today().isoformat()}\n"
        "---\n\n"
    )


# --------------------------------------------------------------------- the run


@dataclass
class Stats:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    missing: int = 0
    skipped: int = 0
    errors: int = 0
    pruned: int = 0


class Scraper:
    def __init__(
        self,
        fetcher: Fetcher,
        root: str,
        out: Path,
        version: str,
        args,
        manifest: dict,
        prefetched: dict[str, requests.Response],
    ) -> None:
        self.fetcher = fetcher
        self.root = root
        self.out = out
        self.version = version
        self.args = args
        self.manifest = manifest
        self.prefetched = prefetched
        self.stats = Stats()
        self.queue: deque[str] = deque()
        self.seen: set[str] = set()
        self.active: dict[str, dict] = {}
        self.crawl = False
        self.hit_limit = False
        self._failures = 0

    def enqueue(self, url: str) -> None:
        if url not in self.seen:
            self.seen.add(url)
            self.queue.append(url)

    def run(self, pages: list[str]) -> None:
        self.crawl = not pages
        for url in pages or [self.root]:
            self.enqueue(url)
        processed = 0
        while self.queue:
            if processed >= self.args.max_pages:
                self.hit_limit = True
                log(f"Stopped at --max-pages {self.args.max_pages}")
                break
            url = self.queue.popleft()
            processed += 1
            for link in self.process(url):
                if self.crawl:
                    self.enqueue(link)

    def fail(self, url: str, reason: str) -> None:
        self.stats.errors += 1
        self._failures += 1
        log(f"  ! {url}: {reason}")
        if self._failures >= MAX_CONSECUTIVE_FAILURES:
            raise Abort(
                f"{MAX_CONSECUTIVE_FAILURES} failures in a row; stopping so the server is not hammered. "
                "If you think you are blocked, see the 'Special considerations' part of "
                "https://docs.readthedocs.com/platform/stable/automated-access.html"
            )

    def process(self, url: str) -> list[str]:
        rel = local_rel(url, self.root)
        dest = (self.out / rel).resolve()
        if not str(dest).startswith(str(self.out.resolve())):
            self.stats.skipped += 1
            return []
        rec = self.manifest["pages"].get(url)

        headers: dict[str, str] = {}
        if rec and not self.args.force and dest.exists():
            if rec.get("etag"):
                headers["If-None-Match"] = rec["etag"]
            if rec.get("last_modified"):
                headers["If-Modified-Since"] = rec["last_modified"]

        # Directory pages are keyed as 'dir/' but fetched as 'dir/index.html', which every builder serves.
        fetch_url = (
            url + "index.html" if url.endswith("/") and url != self.root else url
        )
        try:
            resp = self.prefetched.pop(url, None)
            if resp is None:
                resp = self.fetcher.get(fetch_url, headers)
        except RobotsDisallowed:
            self.stats.skipped += 1
            log(f"  - {url}: disallowed by robots.txt, skipped")
            return []
        except requests.RequestException as exc:
            self.fail(url, f"request failed ({exc.__class__.__name__})")
            return []

        if resp.status_code == 304 and rec:
            self._failures = 0
            self.stats.unchanged += 1
            self.active[url] = rec
            return rec.get("links", [])
        if resp.status_code == 404:
            self._failures = 0
            self.stats.missing += 1
            log(f"  - {url}: 404, not found")
            return []
        if resp.status_code != 200:
            self.fail(url, f"HTTP {resp.status_code}")
            return []
        self._failures = 0

        final = norm(resp.url)
        if final != url:
            if is_doc_url(final, self.root):
                self.enqueue(final)  # handled under its real address
            self.stats.skipped += 1
            return []
        if "html" not in resp.headers.get("Content-Type", "").lower():
            self.stats.skipped += 1
            log(f"  - {url}: not HTML, skipped")
            return []

        title, summary, body, links = convert_html(resp.content, url, self.root)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        unchanged = bool(rec and rec.get("sha256") == digest and dest.exists())

        if unchanged:
            self.stats.unchanged += 1
        else:
            if rec and dest.exists():
                self.stats.updated += 1
                log(f"  ~ updated {rel}")
            else:
                self.stats.new += 1
                log(f"  + new     {rel}")
            if not self.args.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(
                    frontmatter(title, url, self.version) + body, encoding="utf-8"
                )

        self.active[url] = {
            "path": rel,
            "title": title,
            "summary": summary,
            "sha256": digest,
            "size": len(body.encode("utf-8")),
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
            "links": links if self.crawl else [],
        }
        return links

    def prune_files(self) -> None:
        for url in [u for u in self.manifest["pages"] if u not in self.active]:
            rec = self.manifest["pages"][url]
            path = self.out / rec["path"]
            if path.exists() and not self.args.dry_run:
                path.unlink()
                parent = path.parent
                while parent != self.out and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
            self.stats.pruned += 1
            log(f"  - pruned  {rec['path']}")


def render_toc(
    root: str, name: str, version: str, lang: str, pages: dict[str, dict], stamp: str
) -> str:
    items = sorted(pages.values(), key=lambda r: (r["path"] != "index.md", r["path"]))
    lines = [
        f"# {name} documentation ({version}, {lang})",
        "",
        f"Source: {root}",
        f"Pages: {len(items)} · Updated: {stamp}",
        "",
        "One Markdown file per docs page; links between pages point to the local files. "
        "Pick the right page below, and Grep this folder for exact names (a class, function or "
        "option) before reading a whole page. Pages marked `large` are big: grep first, then read "
        "only the matching section.",
        "",
        "## Pages",
        "",
    ]
    for rec in items:
        kb = max(1, round(rec["size"] / 1024))
        flag = ", large" if rec["size"] >= LARGE_PAGE_BYTES else ""
        summary = f" — {rec['summary']}" if rec.get("summary") else ""
        lines.append(
            f"- [{rec['path']}]({rec['path']}) — **{rec['title']}**{summary} ({kb} KB{flag})"
        )
    return "\n".join(lines) + "\n"


def write_toc(
    out: Path, root: str, name: str, version: str, lang: str, pages: dict[str, dict]
) -> None:
    path = out / TOC_NAME
    fresh = render_toc(root, name, version, lang, pages, date.today().isoformat())
    if path.exists():
        old = re.sub(
            r"Updated: \d{4}-\d{2}-\d{2}",
            "Updated: X",
            path.read_text(encoding="utf-8"),
        )
        if old == render_toc(root, name, version, lang, pages, "X"):
            return
    path.write_text(fresh, encoding="utf-8")


def load_manifest(out: Path, root: str, force: bool) -> dict:
    path = out / MANIFEST_NAME
    if path.exists() and not force:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("root") == root and isinstance(data.get("pages"), dict):
                return data
        except json.JSONDecodeError, OSError:
            pass
    return {"schema": 1, "root": root, "pages": {}}


def detect_project_root() -> Path:
    # Look from the script's own location first (like fetch_remote_logs.sh),
    # so the result doesn't depend on where the script is run from.
    here = Path(__file__).resolve()
    if here.parent.parent.name == ".claude":  # <project>/.claude/<dir>/this file
        return here.parent.parent.parent
    cwd = Path.cwd().resolve()
    for start in (here.parent, cwd):
        for candidate in [start, *start.parents]:
            if (candidate / ".git").exists() or (candidate / ".claude").is_dir():
                return candidate
    return cwd


def default_name(netloc: str) -> str:
    host = netloc.split(":")[0]
    labels = host.split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in {
        "readthedocs.io",
        "readthedocs.org",
        "readthedocs.com",
    }:
        name = labels[0]
    else:
        name = netloc
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-") or "docs"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download a Read the Docs site as Markdown for Claude.",
        epilog="Contact info is required by Read the Docs' automated-access policy. "
        "Set RTD_FETCH_CONTACT once instead of passing --contact every time.",
    )
    p.add_argument("site", help="Site URL, e.g. https://discordpy.readthedocs.io")
    p.add_argument(
        "--version", default="stable", help="Docs version slug (default: stable)"
    )
    p.add_argument("--lang", default="en", help="Language code (default: en)")
    p.add_argument(
        "--contact",
        default=os.environ.get("RTD_FETCH_CONTACT"),
        help="Email or URL put in the User-Agent (or env RTD_FETCH_CONTACT)",
    )
    p.add_argument(
        "--out",
        type=Path,
        help="Output folder (default: <project>/.claude/docs/<site>/<version>)",
    )
    p.add_argument(
        "--project-root", type=Path, help="Project root (default: auto-detected)"
    )
    p.add_argument(
        "--name", help="Folder name under .claude/docs (default: derived from the site)"
    )
    p.add_argument(
        "--root-url", help="Docs root URL, for sites not using /<lang>/<version>/ paths"
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help=f"Seconds between requests (default 0.5, minimum {MIN_DELAY})",
    )
    p.add_argument(
        "--discovery",
        choices=["auto", "sitemap", "searchindex", "crawl"],
        default="auto",
        help="How to find pages (default: auto = sitemap, then searchindex.js, then crawl)",
    )
    p.add_argument(
        "--max-pages", type=int, default=2000, help="Safety cap on pages per run"
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache: refetch and rewrite everything",
    )
    p.add_argument(
        "--no-prune",
        action="store_true",
        help="Keep local pages that no longer exist online",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Fetch and report, but write nothing"
    )
    args = p.parse_args(argv)
    if not args.contact:
        p.error(
            "--contact is required (Read the Docs asks bots to identify themselves with an email "
            "or URL). Pass --contact or set RTD_FETCH_CONTACT."
        )
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    delay = args.delay
    if delay < MIN_DELAY:
        log(
            f"--delay raised to {MIN_DELAY}s to stay under Read the Docs' 4 requests/second limit"
        )
        delay = MIN_DELAY

    site = args.site if "://" in args.site else "https://" + args.site
    parsed = urlparse(site)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    root = args.root_url or f"{origin}/{args.lang}/{args.version}/"
    root = root if root.endswith("/") else root + "/"

    project_root = (args.project_root or detect_project_root()).resolve()
    name = (
        re.sub(r"[^A-Za-z0-9_-]+", "-", args.name).strip("-")
        if args.name
        else default_name(parsed.netloc)
    )
    leaf = args.version if args.lang == "en" else f"{args.version}-{args.lang}"
    out = (args.out or project_root / ".claude" / "docs" / name / leaf).resolve()

    fetcher = Fetcher(f"{TOOL}/{TOOL_VERSION} (+{args.contact})", delay)
    started = time.monotonic()
    scraper: Scraper | None = None
    manifest: dict = {"schema": 1, "root": root, "pages": {}}

    try:
        fetcher.load_robots(origin)
        try:
            first = fetcher.get(root)
        except RobotsDisallowed:
            log(f"error: robots.txt disallows fetching {root}")
            return 1
        except requests.RequestException as exc:
            log(f"error: could not reach {root} ({exc.__class__.__name__}: {exc})")
            return 1
        if first.status_code != 200:
            log(
                f"error: {root} returned HTTP {first.status_code}. Check --version and --lang."
            )
            versions = available_versions(fetcher, origin)
            if versions:
                log("Versions listed in the site's sitemap: " + ", ".join(versions))
            return 1
        final_root = first.url.rsplit("/", 1)[0] + "/"
        if final_root != root:
            log(f"Redirected: using {final_root} as docs root")
            root = final_root

        method, pages = discover(fetcher, origin, root, args.discovery)
        if args.discovery in ("sitemap", "searchindex") and not pages:
            log(f"error: discovery via {method} found no pages. Try --discovery auto.")
            return 1
        log(f"Docs root: {root}")
        log(
            f"Discovery: {method}"
            + (f", {len(pages)} pages" if pages else " (following links)")
        )
        log(f"Output:    {out}{'  [dry run]' if args.dry_run else ''}")

        if not args.dry_run:
            out.mkdir(parents=True, exist_ok=True)
        manifest = load_manifest(out, root, args.force)
        scraper = Scraper(
            fetcher, root, out, args.version, args, manifest, {norm(root): first}
        )
        scraper.run(pages)
    except Abort as exc:
        log(f"error: {exc}")
        _finish(scraper, manifest, out, root, name, args, prune=False)
        return 1
    except KeyboardInterrupt:
        log("Interrupted; saving progress")
        _finish(scraper, manifest, out, root, name, args, prune=False)
        return 130

    assert scraper is not None
    prune = not args.no_prune and scraper.stats.errors == 0 and not scraper.hit_limit
    _finish(scraper, manifest, out, root, name, args, prune=prune)

    s = scraper.stats
    elapsed = time.monotonic() - started
    print(
        f"Done: {len(scraper.active)} pages — {s.new} new, {s.updated} updated, {s.unchanged} unchanged, "
        f"{s.missing} missing, {s.skipped} skipped, {s.errors} errors, {s.pruned} pruned "
        f"({fetcher.requests_made} requests, {elapsed:.1f}s)"
    )
    print(f"Output: {out}")
    if not args.dry_run:
        try:
            shown = out.relative_to(project_root).as_posix()
        except ValueError:
            shown = str(out)
        print()
        print("Suggested line for CLAUDE.md:")
        print(
            f"- {name} docs ({args.version}, {args.lang}) are in `{shown}/`. "
            f"Read `_toc.md` first, then Grep/Glob for the exact name and read only the part you need."
        )
    return 1 if s.errors else 0


def _finish(
    scraper: Scraper | None,
    manifest: dict,
    out: Path,
    root: str,
    name: str,
    args,
    prune: bool,
) -> None:
    if scraper is None or args.dry_run:
        return
    if prune:
        scraper.prune_files()
        manifest["pages"] = dict(scraper.active)
    else:
        manifest["pages"].update(scraper.active)
    manifest["root"] = root
    out.mkdir(parents=True, exist_ok=True)
    (out / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8"
    )
    write_toc(out, root, name, args.version, args.lang, manifest["pages"])


if __name__ == "__main__":
    sys.exit(main())
