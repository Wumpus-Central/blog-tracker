import os
import time
import requests
from loguru import logger

import modules.notifiers.embeds.zendesk as zendesk_embeds
import modules.notifiers.embeds.blog as blog_embeds


class DiscordNotifier:
    WEBHOOK_LABELS = ["UNI"]
    SEND_DELAY_SECONDS = 2
    BUCKET_ACTIONS = [
        ("added", "ADDED"),
        ("updated", "UPDATED"),
        ("removed", "REMOVED"),
    ]
    SOURCE_CREATORS = {
        "blog": blog_embeds.create_blog_embed,
        "support": zendesk_embeds.create_zendesk_embed,
        "support-dev": zendesk_embeds.create_zendesk_embed,
        "support-apps": zendesk_embeds.create_zendesk_embed,
        "creator-support": zendesk_embeds.create_zendesk_embed,
    }

    def send(self, diff, commit_url=None):
        if self._is_empty(diff):
            logger.info("Diff is empty — nothing to notify.")
            return

        for source, buckets in diff.items():
            creator = self.SOURCE_CREATORS.get(source)
            if creator is None:
                logger.warning(f"No embed handler for source '{source}' — skipping.")
                continue

            for bucket, action in self.BUCKET_ACTIONS:
                entries = buckets.get(bucket, {})
                for entry_key, entry in entries.items():
                    message = creator(action, entry, commit_url)
                    if message is None:
                        continue
                    self._dispatch(message, source, action, entry_key)
                    time.sleep(self.SEND_DELAY_SECONDS)

    def _dispatch(self, message, source, action, entry_key):
        for label in self.WEBHOOK_LABELS:
            webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{label}")
            if not webhook_url:
                logger.warning(f"DISCORD_WEBHOOK_{label} not set — skipping.")
                continue

            try:
                response = requests.post(
                    webhook_url,
                    json=message,
                    timeout=10,
                )
                if response.status_code in (200, 204):
                    logger.success(
                        f"Dispatched {action} embed for {source}/{entry_key} to Discord ({label})."
                    )
                else:
                    logger.error(
                        f"Discord ({label}) returned {response.status_code} for "
                        f"{source}/{entry_key}: {response.text}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to dispatch {action} embed for {source}/{entry_key} "
                    f"to Discord ({label}): {e}"
                )

    @staticmethod
    def _is_empty(diff):
        for source, buckets in diff.items():
            for bucket in buckets.values():
                if bucket:
                    return False
        return True
