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
            logger.error(f"Unexpected error while fetching RSS: {e}")
            return {"blog": posts}

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
            logger.error(f"Failed to parse RSS feed: {e}")
            return {"blog": posts}

        logger.success(f"Processed {len(posts)} blog posts.")
        return {"blog": posts}
