import os
import json
import requests
from loguru import logger

class DiscordNotifier:
    WEBHOOK_LABELS = ["UNI"]

    def send(self, diff):
        if self._is_empty(diff):
            logger.info("Diff is empty — nothing to notify.")
            return

        content = f"```json\n{json.dumps(diff, indent=2)}\n```"

        for label in self.WEBHOOK_LABELS:
            webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{label}")
            if not webhook_url:
                logger.warning(f"DISCORD_WEBHOOK_{label} not set — skipping.")
                continue

            try:
                response = requests.post(
                    webhook_url,
                    json={"content": content},
                    timeout=10
                )
                if response.status_code in (200, 204):
                    logger.success(f"Dispatched diff to Discord ({label}).")
                else:
                    logger.error(f"Discord ({label}) returned {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Failed to dispatch to Discord ({label}): {e}")

    def _is_empty(self, diff):
        for source in diff.values():
            for bucket in source.values():
                if bucket:
                    return False
        return True
