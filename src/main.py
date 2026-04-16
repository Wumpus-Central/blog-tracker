import json
import sys
from loguru import logger
import modules.providers.articles as articles_provider 
import modules.providers.blog as blog_provider

logger.remove()
logger.add(
    sys.stderr, 
    level="INFO", 
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
)

class ScraperEngine:
    def __init__(self):
        self.state_file = "data/state.json"
        self.new_data = {}
        self.old_data = {}
        logger.debug("ScraperEngine initialized. State file: {file}", file=self.state_file)

    def run(self):
        logger.info("Starting scraper...")
        
        # TODO: state_load
        logger.info("Loading previous state...")

        articles = articles_provider.ArticleProvider()

        article_sources = [
            'support',
            'support-dev',
            'support-apps',
            'creator-support'
        ]

        logger.info(f"Starting to walk through {len(article_sources)} sources.")
        
        total_scraped = 0

        for source in article_sources:
            logger.info(f"Processing source: {source}")
            try:
                scraped_batch = articles.walker(source)
                
                current_articles = scraped_batch.get(source, [])
                batch_size = len(current_articles)
                
                self.new_data.update(scraped_batch)
                total_scraped += batch_size
                
                logger.success(f"Successfully scraped {batch_size} articles from '{source}'")
            except Exception as e:
                logger.exception(f"Failed to process source '{source}': {e}")

        if total_scraped > 0:
            logger.success(f"Finished! Total articles collected from all sources: {total_scraped}")
        else:
            logger.warning("Empty run: No articles were scraped.")

        # TODO: blog_provider
        # TODO: diff_logic

if __name__ == "__main__":
    @logger.catch
    def start():
        engine = ScraperEngine()
        engine.run()

    start()