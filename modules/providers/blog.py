import hashlib
import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from loguru import logger
from pathlib import Path

ARTICLE_RE = re.compile(
    r'<article[^>]*class="[^"]*w-richtext[^"]*"[^>]*>(.*?)</article>',
    re.DOTALL,
)
HASH_RE = re.compile(r'^[a-f0-9]{64}$')
CONTENT_FETCH_DELAY_SECONDS = 1

BODY_FORMAT_VERSION = 2

MASS_CHANGE_MIN = 10
MASS_CHANGE_RATIO = 0.2
EXTRACTION_FAIL_MIN = 5
EXTRACTION_FAIL_RATIO = 0.1


class BlogProvider:
    RSS_URL = "https://discord.com/blog/rss.xml"

    def fetch(self, old_entries):
        rss_by_link = self._fetch_rss()
        old_by_link = {e["link"]: e for e in old_entries if e.get("link")}

        posts = []
        refetch_attempts = 0
        extraction_failures = 0

        for link, fresh in rss_by_link.items():
            old = old_by_link.get(link)
            if old and self._is_reusable(old, fresh):
                logger.debug(f"Reusing cached blog post: {link}")
                posts.append(dict(old))
                continue

            refetch_attempts += 1
            entry = self._fetch_post(fresh)
            if entry.get("body") is None:
                extraction_failures += 1
                if old is not None:
                    logger.warning(
                        f"Content extraction failed for {link} — keeping previous entry."
                    )
                    posts.append(dict(old))
                    continue
                logger.warning(f"Content extraction failed for new post {link} — will retry next run.")
            posts.append(entry)

        for link, old in old_by_link.items():
            if link in rss_by_link:
                continue
            if old.get("body") and old.get("body_format") == BODY_FORMAT_VERSION:
                logger.debug(f"Keeping blog post outside RSS window: {link}")
                posts.append(dict(old))
                continue

            refetch_attempts += 1
            logger.info(f"Backfilling content for blog post outside RSS: {link}")
            entry = self._fetch_post(old)
            if entry.get("body") is None:
                extraction_failures += 1
                logger.warning(
                    f"Content extraction failed for {link} — keeping previous entry."
                )
                posts.append(dict(old))
                continue
            posts.append(entry)

        self._run_guards(old_by_link, posts, refetch_attempts, extraction_failures)

        logger.success(f"Processed {len(posts)} blog posts.")
        return {"blog": posts}

    def write(self, entries):
        output_dir = os.environ.get("OUTPUT_DIR", ".")
        blog_path = Path(output_dir) / "blog"
        blog_path.mkdir(parents=True, exist_ok=True)

        written = 0
        for entry in entries:
            body = entry.get("body")
            if body is None or HASH_RE.match(body):
                continue

            slug = self._slug(entry.get("link"))
            if not slug:
                logger.warning(f"Blog write: cannot derive slug from link {entry.get('link')}")
                continue

            file_path = blog_path / f"{slug}.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(body)

            entry["body"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
            entry["body_format"] = BODY_FORMAT_VERSION
            written += 1

        logger.success(f"Wrote {written} blog .md files.")
        return "blog"

    def walker(self, old_entries):
        fetched = self.fetch(old_entries)
        self.write(fetched["blog"])
        return fetched

    def _fetch_rss(self):
        try:
            rss_response = requests.get(self.RSS_URL, timeout=15).text
        except Exception as e:
            raise RuntimeError(f"Blog RSS fetch failed: {e}") from e

        try:
            rss_content = feedparser.parse(rss_response)
            batch = rss_content["entries"]
        except Exception as e:
            raise RuntimeError(f"Blog RSS parse failed: {e}") from e

        logger.success(f"Fetched RSS feed with {len(batch)} items")

        entries = {}
        for post in batch:
            link = post.get("link")
            if not link:
                continue
            entries[link] = {
                "title": post.get("title", ""),
                "link": link,
                "summary": post.get("summary", ""),
                "published": post.get("published", ""),
                "media_thumbnail_url": self._extract_thumbnail(post),
            }
        return entries

    def _fetch_post(self, meta):
        link = meta.get("link")
        body = None

        try:
            response = requests.get(link, timeout=15)
            if response.status_code == 200:
                match = ARTICLE_RE.search(response.text)
                if match and match.group(1).strip():
                    body = self._pretty_print(match.group(1))
                else:
                    logger.warning(f"No article content found for {link}")
            else:
                logger.warning(f"HTTP {response.status_code} while fetching {link}")
        except Exception as e:
            logger.warning(f"Failed to fetch content for {link}: {e}")

        entry = dict(meta)
        if body is not None:
            entry["body"] = body
            entry["body_format"] = BODY_FORMAT_VERSION
        time.sleep(CONTENT_FETCH_DELAY_SECONDS)
        return entry

    def _run_guards(self, old_by_link, posts, refetch_attempts, extraction_failures):
        mass_change_limit = self._mass_change_limit(len(old_by_link))
        suspicious = 0
        for post in posts:
            link = post.get("link")
            old = old_by_link.get(link)
            if old is None:
                suspicious += 1
                continue
            if post != old and old.get("body_format") == BODY_FORMAT_VERSION:
                suspicious += 1

        if suspicious > mass_change_limit:
            raise RuntimeError(
                f"Blog mass-change guard: {suspicious} added/updated posts exceeds "
                f"limit {mass_change_limit} — aborting to prevent notification spam. "
                f"Set BLOG_MASS_CHANGE_LIMIT to override."
            )

        extraction_fail_limit = self._extraction_fail_limit(refetch_attempts)
        if extraction_failures > extraction_fail_limit:
            raise RuntimeError(
                f"Blog extraction guard: {extraction_failures} content extraction "
                f"failures exceeds limit {extraction_fail_limit} — possible HTML "
                f"structure change on Discord's side. "
                f"Set BLOG_EXTRACTION_FAIL_LIMIT to override."
            )

    @staticmethod
    def _mass_change_limit(old_total):
        env = os.environ.get("BLOG_MASS_CHANGE_LIMIT")
        if env:
            return int(env)
        return max(MASS_CHANGE_MIN, int(MASS_CHANGE_RATIO * old_total))

    @staticmethod
    def _extraction_fail_limit(refetch_attempts):
        env = os.environ.get("BLOG_EXTRACTION_FAIL_LIMIT")
        if env:
            return int(env)
        return max(EXTRACTION_FAIL_MIN, int(EXTRACTION_FAIL_RATIO * refetch_attempts))

    @staticmethod
    def _is_reusable(old, fresh):
        return (
            old.get("body_format") == BODY_FORMAT_VERSION
            and old.get("body")
            and BlogProvider._meta_same(old, fresh)
        )

    @staticmethod
    def _pretty_print(html):
        soup = BeautifulSoup(html, "html.parser")
        return soup.prettify().strip()

    @staticmethod
    def _meta_same(old, fresh):
        for key in ("title", "summary", "published", "media_thumbnail_url"):
            if old.get(key) != fresh.get(key):
                return False
        return True

    @staticmethod
    def _extract_thumbnail(entry):
        try:
            return entry["media_thumbnail"][0]["url"]
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _slug(link):
        if not link:
            return None
        slug = link.rstrip("/").rsplit("/", 1)[-1]
        return slug or None
