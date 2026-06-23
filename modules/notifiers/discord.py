import os
import json
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
    SOURCE_CONFIG = {
        "blog": (blog_embeds.create_blog_embed, "link"),
        "support": (zendesk_embeds.create_zendesk_embed, "id"),
        "support-dev": (zendesk_embeds.create_zendesk_embed, "id"),
        "support-apps": (zendesk_embeds.create_zendesk_embed, "id"),
        "creator-support": (zendesk_embeds.create_zendesk_embed, "id"),
    }

    def send(self, diff):
        if self._is_empty(diff):
            logger.info("Diff is empty — nothing to notify.")
            return

        state = self._load_state()

        for source, buckets in diff.items():
            config = self.SOURCE_CONFIG.get(source)
            if config is None:
                logger.warning(f"No embed handler for source '{source}' — skipping.")
                continue

            creator, key_field = config

            for bucket, action in self.BUCKET_ACTIONS:
                entries = buckets.get(bucket, {})
                for entry_key, title in entries.items():
                    entry = self._lookup_entry(state, source, key_field, entry_key)
                    message = creator(action, entry, title)
                    if message is None:
                        continue
                    self._dispatch(message, source, action, entry_key)
                    time.sleep(self.SEND_DELAY_SECONDS)

    def _load_state(self):
        output_dir = os.environ.get("OUTPUT_DIR", ".")
        state_file = os.path.join(output_dir, "state.json")
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"state.json not found at {state_file} — embeds will be title-only.")
            return {}
        except Exception as e:
            logger.error(f"Failed to load state.json: {e}")
            return {}

    @staticmethod
    def _lookup_entry(state, source, key_field, key_value):
        for entry in state.get(source, []):
            if str(entry.get(key_field)) == str(key_value):
                return entry
        return None

    def _dispatch(self, message, source, action, article_id):
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
                        f"Dispatched {action} embed for {source}/{article_id} to Discord ({label})."
                    )
                else:
                    logger.error(
                        f"Discord ({label}) returned {response.status_code} for "
                        f"{source}/{article_id}: {response.text}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to dispatch {action} embed for {source}/{article_id} "
                    f"to Discord ({label}): {e}"
                )

    @staticmethod
    def _is_empty(diff):
        for source, buckets in diff.items():
            for bucket in buckets.values():
                if bucket:
                    return False
        return True
