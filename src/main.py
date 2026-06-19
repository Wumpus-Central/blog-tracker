import json
import os
import sys
from loguru import logger
import modules.providers.articles as articles_provider 
import modules.providers.blog as blog_provider
import modules.differ as differ

logger.remove()
logger.add(
    sys.stderr, 
    level="INFO", 
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
)

class ScraperEngine:
    def __init__(self):
        # Output dir for scraped data + state.json. Defaults to cwd ("."),
        # but in CI we set OUTPUT_DIR=data so writes land in the `main` checkout.
        self.output_dir = os.environ.get("OUTPUT_DIR", ".")
        self.state_file = os.path.join(self.output_dir, "state.json")
        self.new_data = {}
        self.old_data = {}
        self.diff = {}
        self.article_sources = [
            'support',
            'support-dev',
            'support-apps',
            'creator-support'
        ]
        logger.debug("ScraperEngine initialized. State file: {file}", file=self.state_file)
    
    def _fetch_articles(self):
        articles = articles_provider.ArticleProvider()

        total_scraped = 0

        logger.info(f"Starting to walk through {len(self.article_sources)} sources.")

        for source in self.article_sources:
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
    
    def _fetch_blog(self):
        blog = blog_provider.BlogProvider()

        total_scraped = 0

        logger.info(f"Starting to walk throught Discord Blog.")

        scraped_batch = blog.walker()
        self.new_data.update(scraped_batch)
    
    def _get_diff(self):
        self.diff = differ.Differ().compute(
            self.output_dir, self.article_sources, self.new_data, self.old_data
        )


    def run(self):
        logger.info("Starting scraper...")

        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as old_data_file:
                self.old_data = json.load(old_data_file)
            logger.info("Loaded previous state for diffing.")
        else:
            logger.info("No previous state found — first run.")

        self._fetch_articles()
        self._fetch_blog()

        logger.info("Writing new state...")
        with open(self.state_file, "w") as old_data_file:
            json.dump(self.new_data, old_data_file, indent=4) 
            logger.success("New state.json written.")

        self._get_diff()

if __name__ == "__main__":
    @logger.catch
    def start():
        engine = ScraperEngine()
        engine.run()

    start()