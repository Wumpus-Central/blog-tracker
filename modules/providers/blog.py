import hashlib
import os
import re
import time
import requests
import feedparser
from loguru import logger
from pathlib import Path

ARTICLE_RE = re.compile(
    r'<article[^>]*class="[^"]*w-richtext[^"]*"[^>]*>(.*?)</article>',
    re.DOTALL,
)
HASH_RE = re.compile(r'^[a-f0-9]{64}$')
CONTENT_FETCH_DELAY_SECONDS = 1


class BlogProvider:
    RSS_URL = "https://discord.com/blog/rss.xml"

    def fetch(self, old_entries):
        rss_by_link = self._fetch_rss()
        old_by_link = {e["link"]: e for e in old_entries if e.get("link")}

        posts = []

        for link, fresh in rss_by_link.items():
            old = old_by_link.get(link)
            if old and old.get("body") and self._meta_same(old, fresh):
                logger.debug(f"Reusing cached blog post: {link}")
                posts.append(dict(old))
                continue
            posts.append(self._fetch_post(fresh))

        for link, old in old_by_link.items():
            if link in rss_by_link:
                continue
            if old.get("body"):
                logger.debug(f"Keeping blog post outside RSS window: {link}")
                posts.append(dict(old))
                continue
            logger.info(f"Backfilling content for blog post outside RSS: {link}")
            posts.append(self._fetch_post(old))

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
        body = ""

        try:
            response = requests.get(link, timeout=15)
            if response.status_code == 200:
                match = ARTICLE_RE.search(response.text)
                if match:
                    body = match.group(1).strip()
                else:
                    logger.warning(f"No article content found for {link}")
            else:
                logger.warning(f"HTTP {response.status_code} while fetching {link}")
        except Exception as e:
            logger.warning(f"Failed to fetch content for {link}: {e}")

        entry = dict(meta)
        entry["body"] = body
        time.sleep(CONTENT_FETCH_DELAY_SECONDS)
        return entry

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
