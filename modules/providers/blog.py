import json
import requests
import hashlib
import subprocess
import feedparser
from loguru import logger

class BlogProvider:
    def walker(self):
        processed_count = 0
        posts = []

        url_rss = "https://discord.com/blog/rss.xml"

        try:
            rss_response = requests.get(url_rss, timeout=15).text
            logger.success(f"Successfully fetched RSS feed from {url_rss}")
        except Exception as e:
            logger.error(f"Unexpected error while fetching RSS: {e}")
        
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

        return {"blog": posts}