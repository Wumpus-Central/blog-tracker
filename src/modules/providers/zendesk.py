import json
import os
import requests
import hashlib
import subprocess
from loguru import logger

class ZendeskProvider:
    def walker(self, source):
        domain = f"{source}.discord.com"
        page = 1
        articles = []
        processed_count = 0
        total_count = None

        # Output dir for per-source article files. Defaults to cwd ("."),
        # but in CI we set OUTPUT_DIR=data so writes land in the `main` checkout.
        output_dir = os.environ.get("OUTPUT_DIR", ".")
        source_dir = os.path.join(output_dir, source)

        subprocess.run(f"rm -rf {source_dir}/*", shell=True)
        subprocess.run(f"mkdir -p {source_dir}", shell=True)
        logger.debug(f"Directory {source_dir} is ready.")

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
                logger.warning(f"Finished or error: Source {source} returned status {response.status_code} on page {page}")
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

                del article['vote_sum'], article['vote_count'], article['updated_at']

                logger.info(f"[{processed_count}/{total_count}] Processing article: {article_id} | {article_title[:40]}...")

                try:
                    file_path = os.path.join(source_dir, f"{article_id}.md")
                    with open(file_path, "w", encoding="utf-8") as file:
                        file.write(article['body'])
                    
                    article['body'] = hashlib.sha256(article['body'].encode('utf-8')).hexdigest()
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Failed to save article {article_id}: {e}")

            page += 1
        
        return {source: articles}