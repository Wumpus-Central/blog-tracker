import argparse
import json
import os
import sys
from loguru import logger
import modules.providers.zendesk as zendesk_provider
import modules.providers.blog as blog_provider
import modules.differ as differ
import modules.notifiers.discord as discord_notifier

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
)

REPO_URL = "https://github.com/Wumpus-Central/blog-tracker"


class ScraperEngine:
    def __init__(self):
        self.output_dir = os.environ.get("OUTPUT_DIR", ".")
        self.state_file = os.path.join(self.output_dir, "state.json")
        self.diff_file = os.environ.get("DIFF_FILE", "./diff.json")
        self.new_data = {}
        self.old_data = {}
        self.diff = {}
        self.zendesk_sources = [
            'support',
            'support-dev',
            'support-apps',
            'creator-support'
        ]
        logger.debug(f"ScraperEngine initialized. State file: {self.state_file}")

    def _fetch_zendesk(self):
        zendesk = zendesk_provider.ZendeskProvider()

        total_scraped = 0

        logger.info(f"Starting to walk through {len(self.zendesk_sources)} sources.")

        for source in self.zendesk_sources:
            logger.info(f"Processing source: {source}")
            try:
                scraped_batch = zendesk.walker(source)

                current_articles = scraped_batch.get(source, [])
                batch_size = len(current_articles)

                self.new_data.update(scraped_batch)
                total_scraped += batch_size

                logger.success(f"Successfully scraped {batch_size} articles from '{source}'")
            except Exception as e:
                logger.exception(f"Failed to process source '{source}'")

        if total_scraped > 0:
            logger.success(f"Finished! Total articles collected from all sources: {total_scraped}")
        else:
            logger.warning("Empty run: No articles were scraped.")

    def _fetch_blog(self):
        blog = blog_provider.BlogProvider()

        logger.info("Starting to walk through Discord Blog.")

        try:
            scraped_batch = blog.walker()
            self.new_data.update(scraped_batch)
        except Exception as e:
            logger.exception(f"Failed to process Discord Blog")

    def _get_diff(self):
        self.diff = differ.Differ().compute(
            self.output_dir, self.zendesk_sources, self.new_data, self.old_data
        )

    def _save_diff(self):
        try:
            with open(self.diff_file, "w", encoding="utf-8") as f:
                json.dump(self.diff, f, indent=4)
            logger.success(f"Diff written to {self.diff_file}")
        except Exception as e:
            logger.error(f"Failed to write diff to {self.diff_file}: {e}")
            raise

    def _load_diff(self):
        try:
            with open(self.diff_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load diff from {self.diff_file}: {e}")
            raise

    def _notify_discord(self, commit_url=None):
        discord_notifier.DiscordNotifier().send(self.diff, commit_url)

    def scrape(self):
        logger.info("Starting scraper...")

        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as old_data_file:
                self.old_data = json.load(old_data_file)
            logger.info("Loaded previous state for diffing.")
        else:
            logger.info("No previous state found — first run.")

        self._fetch_zendesk()
        self._fetch_blog()

        logger.info("Writing new state...")
        with open(self.state_file, "w", encoding="utf-8") as old_data_file:
            json.dump(self.new_data, old_data_file, indent=4)
            logger.success("New state.json written.")

        self._get_diff()
        self._save_diff()

    def notify(self, commit_sha):
        logger.info("Starting notify...")
        commit_url = f"{REPO_URL}/commit/{commit_sha}" if commit_sha else None
        logger.info(f"Commit URL: {commit_url or 'none'}")
        self.diff = self._load_diff()
        logger.info(f"Loaded diff.json ({len(self.diff)} sources)")
        self._notify_discord(commit_url)


def print_help():
    print(f"""Blog Tracker — Discord content scraper & notifier

Usage:
  python main.py --scrape              Scrape sources, write state.json + diff.json (no notifications)
  python main.py --notify --commit-sha <SHA>
                                       Load diff.json and dispatch Discord embeds with commit URL
  python main.py                       Show this help message

Modes:
  --scrape        Fetch Zendesk articles + blog posts, write state.json and .md files to
                  OUTPUT_DIR (default: .), compute diff against previous state, and persist
                  it to DIFF_FILE (default: ./diff.json). Does NOT send notifications.
                  Requires OUTPUT_DIR to point at a checkout of the `data` branch for
                  meaningful diffs (git status based for Zendesk, state-based for blog).

  --notify        Load diff.json and dispatch per-change Discord embeds. Requires --commit-sha
                  to embed a clickable "View commit" link in each message. Webhook URLs are
                  read from DISCORD_WEBHOOK_* environment variables.

Environment variables:
  OUTPUT_DIR              Directory for state.json + .md files (default: .)
  DIFF_FILE               Path to diff.json (default: ./diff.json)
  DISCORD_WEBHOOK_UNI     Discord webhook URL for the UNI server (notify mode)
""")


@logger.catch
def start():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--scrape", action="store_true")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--commit-sha", default=None)
    args = parser.parse_args()

    if not args.scrape and not args.notify:
        print_help()
        return

    engine = ScraperEngine()

    if args.scrape:
        logger.info("Running in scrape mode")
        engine.scrape()

    if args.notify:
        logger.info("Running in notify mode")
        engine.notify(args.commit_sha)


if __name__ == "__main__":
    start()
