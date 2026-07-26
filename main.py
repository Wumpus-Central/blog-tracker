import argparse
import json
import os
import time
import requests
from loguru import logger
import modules.providers.zendesk as zendesk_provider
import modules.providers.blog as blog_provider
import modules.differ as differ
import modules.archiver as archiver
import modules.notifiers.discord as discord_notifier
import modules.line_stats as line_stats_module
import modules.log_setup
from modules._shared import ZENDESK_SOURCES, BLOG_SOURCE
from modules.monitor import HealthMonitor, SourceStatus

REPO_URL = "https://github.com/Wumpus-Central/blog-tracker"
MAX_FETCH_ATTEMPTS = 3


class ScraperEngine:
    def __init__(self):
        self.output_dir = os.environ.get("OUTPUT_DIR", ".")
        self.state_file = os.path.join(self.output_dir, "state.json")
        self.diff_file = os.environ.get("DIFF_FILE", "./diff.json")
        self.monitor_file = os.environ.get("MONITOR_FILE", "./monitor.json")
        self.new_data = {}
        self.old_data = {}
        self.diff = {}
        self.monitor = HealthMonitor()
        self.zendesk_sources = ZENDESK_SOURCES
        self._attempt_counts = {}
        logger.debug(f"ScraperEngine initialized. State file: {self.state_file}")

    def _fetch_with_retry(self, source_name, fetch_fn):
        last_error = None
        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
            try:
                result = fetch_fn()
                self._attempt_counts[source_name] = attempt
                return result
            except requests.HTTPError as e:
                last_error = e
                if (
                    e.response is not None
                    and e.response.status_code == 429
                    and "Retry-After" in e.response.headers
                ):
                    delay = int(e.response.headers["Retry-After"])
                else:
                    delay = 2 ** (attempt - 1)
            except Exception as e:
                last_error = e
                delay = 2 ** (attempt - 1)
            if attempt < MAX_FETCH_ATTEMPTS:
                logger.warning(
                    f"[{source_name}] attempt {attempt}/{MAX_FETCH_ATTEMPTS} failed: {last_error} "
                    f"— retrying in {delay}s..."
                )
                time.sleep(delay)
        self._attempt_counts[source_name] = MAX_FETCH_ATTEMPTS
        raise last_error

    def _fetch_zendesk(self):
        self._zendesk = zendesk_provider.ZendeskProvider()
        total_scraped = 0
        logger.info(f"Starting to walk through {len(self.zendesk_sources)} sources.")

        for source in self.zendesk_sources:
            logger.info(f"Processing source: {source}")
            self.monitor.register(source)
            try:
                scraped_batch = self._fetch_with_retry(
                    source, lambda s=source: self._zendesk.fetch(s)
                )
                current_articles = scraped_batch.get(source, [])
                batch_size = len(current_articles)
                self.new_data.update(scraped_batch)
                total_scraped += batch_size
                self.monitor.report(
                    source, SourceStatus.OK, batch_size,
                    attempts=self._attempt_counts.get(source, 1),
                )
                logger.success(f"Successfully scraped {batch_size} articles from '{source}'")
            except Exception as e:
                self.monitor.report(
                    source, SourceStatus.FAILED, 0, str(e),
                    attempts=MAX_FETCH_ATTEMPTS,
                )

        if total_scraped > 0:
            logger.success(f"Finished! Total articles collected from all sources: {total_scraped}")
        else:
            logger.warning("Empty run: No articles were scraped.")

    def _write_zendesk(self):
        for source in self.zendesk_sources:
            articles = self.new_data.get(source, [])
            try:
                self._zendesk.write(source, articles)
            except Exception as e:
                logger.exception(f"Failed to write source '{source}'")

    def _archive_removed(self):
        logger.info("Archiving removed articles...")
        try:
            archiver.Archiver().process(
                self.old_data, self.new_data, self.zendesk_sources, self.output_dir
            )
        except Exception as e:
            logger.exception("Archiver failed")

    def _fetch_blog(self):
        blog = blog_provider.BlogProvider()
        logger.info("Starting to walk through Discord Blog.")
        self.monitor.register(BLOG_SOURCE)
        try:
            scraped_batch = self._fetch_with_retry(
                BLOG_SOURCE, lambda: blog.walker()
            )
            self.new_data.update(scraped_batch)
            self.monitor.report(
                BLOG_SOURCE, SourceStatus.OK, len(scraped_batch.get(BLOG_SOURCE, [])),
                attempts=self._attempt_counts.get(BLOG_SOURCE, 1),
            )
        except Exception as e:
            self.monitor.report(
                BLOG_SOURCE, SourceStatus.FAILED, 0, str(e),
                attempts=MAX_FETCH_ATTEMPTS,
            )

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

    def _notify_discord(self, commit_url=None, line_stats=None):
        discord_notifier.DiscordNotifier().send(self.diff, commit_url, line_stats)

    def scrape(self):
        logger.info("Starting scraper...")

        if os.path.exists(self.monitor_file):
            os.remove(self.monitor_file)
            logger.info(f"Removed stale {self.monitor_file} from previous failed run.")

        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as old_data_file:
                self.old_data = json.load(old_data_file)
            logger.info("Loaded previous state for diffing.")
        else:
            logger.info("No previous state found — first run.")

        self._fetch_zendesk()
        self._fetch_blog()

        if not self.monitor.is_healthy():
            failed = self.monitor.failed_sources()
            logger.error(
                f"Health check FAILED — {len(failed)} source(s) unhealthy: {failed}. "
                f"Aborting scrape before archival/write to prevent false removals."
            )
            self.monitor.save(self.monitor_file)
            raise SystemExit(1)

        logger.success("All sources healthy — proceeding with archival, write, and diff.")

        self._archive_removed()
        self._write_zendesk()

        logger.info("Writing new state...")
        with open(self.state_file, "w", encoding="utf-8") as old_data_file:
            json.dump(self.new_data, old_data_file, indent=4)
            logger.success("New state.json written.")

        self._get_diff()
        self._save_diff()

    def notify(self, commit_sha):
        logger.info("Starting notify...")

        if os.path.exists(self.monitor_file):
            logger.warning(
                f"Health monitor file found at {self.monitor_file} — "
                f"previous scrape was aborted. Sending error embed."
            )
            monitor = HealthMonitor.load(self.monitor_file)
            run_url = os.environ.get("ACTIONS_RUN_URL")
            discord_notifier.DiscordNotifier().send_error(monitor, run_url)
            return

        commit_url = f"{REPO_URL}/commit/{commit_sha}" if commit_sha else None
        logger.info(f"Commit URL: {commit_url or 'none'}")
        self.diff = self._load_diff()
        logger.info(f"Loaded diff.json ({len(self.diff)} sources)")
        line_stats = line_stats_module.build_line_stats(self.output_dir)
        self._notify_discord(commit_url, line_stats)


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
    modules.log_setup.setup_logging()
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
