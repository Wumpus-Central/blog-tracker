import requests
import feedparser
from loguru import logger

class BlogProvider:
    def walker(self):
        posts = []
        url_rss = "https://discord.com/blog/rss.xml"

        try:
            rss_response = requests.get(url_rss, timeout=15).text
            logger.success(f"Successfully fetched RSS feed from {url_rss}")
        except Exception as e:
            raise RuntimeError(f"Blog RSS fetch failed: {e}") from e

        try:
            rss_content = feedparser.parse(rss_response)
            batch = rss_content['entries']
            logger.info(f"Found {len(batch)} items in Discord Blog RSS")

            for post in batch:
                posts.append({
                    "title": post["title"],
                    "link": post["link"],
                    "summary": post["summary"],
                    "published": post["published"],
                    "media_thumbnail_url": post["media_thumbnail"][0]["url"]
                })
        except Exception as e:
            raise RuntimeError(f"Blog RSS parse failed: {e}") from e

        logger.success(f"Processed {len(posts)} blog posts.")
        return {"blog": posts}