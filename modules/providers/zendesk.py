import os
import re
import shutil
import requests
import hashlib
from loguru import logger
from pathlib import Path

IMG_TAG_RE = re.compile(r'<img[^>]*>', re.IGNORECASE)
SRC_RE = re.compile(r'src="([^"]*)"', re.IGNORECASE)
WIDTH_RE = re.compile(r'width="(\d+)"', re.IGNORECASE)


class ZendeskProvider:
    def fetch(self, source):
        domain = f"{source}.discord.com"
        page = 1
        articles = []
        processed_count = 0
        total_count = None

        logger.info(f"Fetching articles from '{source}'...")

        while True:
            logger.debug(f"Fetching page {page} for {source}...")

            try:
                response = requests.get(
                    f'https://{domain}/api/v2/help_center/en-us/articles.json?page={page}&per_page=100',
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Request failed for {source} page {page}: {e}")
                break

            if response.status_code != 200:
                if response.status_code == 404:
                    logger.debug(f"Pagination ended for {source} at page {page} (404).")
                else:
                    logger.error(f"Source {source} returned status {response.status_code} on page {page}")
                break

            data = response.json()

            if total_count is None:
                total_count = data.get('count', 0)
                logger.info(f"Source '{source}' reports {total_count} articles across {data.get('page_count')} pages.")

            batch = data.get('articles', [])
            if not batch:
                break

            for article in batch:
                processed_count += 1
                article_id = article['id']
                article_title = article.get('title', 'Unknown Title')

                logger.info(f"[{processed_count}/{total_count}] Processing article: {article_id} | {article_title[:40]}...")

                try:
                    article.pop('vote_sum', None)
                    article.pop('vote_count', None)
                    article.pop('updated_at', None)

                    body = article['body']
                    thumbnail_url = self._extract_thumbnail(body)
                    if thumbnail_url:
                        article['thumbnail_url'] = thumbnail_url
                        logger.debug(f"Extracted thumbnail for article {article_id}: {thumbnail_url}")
                    else:
                        logger.debug(f"No thumbnail found for article {article_id}")

                    articles.append(article)
                except Exception as e:
                    logger.error(f"Failed to process article {article_id}: {e}")

            page += 1

        logger.success(f"Fetched {len(articles)} articles from '{source}'.")
        return {source: articles}

    def write(self, source, articles):
        output_dir = os.environ.get("OUTPUT_DIR", ".")
        source_path = Path(output_dir) / source

        shutil.rmtree(source_path, ignore_errors=True)
        source_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory {source_path} is ready.")

        written = 0
        for article in articles:
            article_id = article['id']
            try:
                body = article['body']
                file_path = os.path.join(source_dir, f"{article_id}.md")
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(body)

                article['body'] = hashlib.sha256(body.encode('utf-8')).hexdigest()
                written += 1
            except Exception as e:
                logger.error(f"Failed to write article {article_id}: {e}")

        logger.success(f"Wrote {written}/{len(articles)} .md files for '{source}'.")
        return source

    def walker(self, source):
        fetched = self.fetch(source)
        self.write(source, fetched[source])
        return fetched

    @staticmethod
    def _extract_thumbnail(html):
        fallback = None
        for tag in IMG_TAG_RE.finditer(html):
            tag_text = tag.group(0)
            src_match = SRC_RE.search(tag_text)
            if not src_match:
                continue
            src = src_match.group(1)
            if fallback is None:
                fallback = src
            width_match = WIDTH_RE.search(tag_text)
            if width_match and int(width_match.group(1)) <= 32:
                continue
            return src
        return fallback