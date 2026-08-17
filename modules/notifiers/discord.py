import os
import time
import requests
from loguru import logger

import modules.notifiers.embeds.zendesk as zendesk_embeds
import modules.notifiers.embeds.blog as blog_embeds
from modules.core.constants import ZENDESK_SOURCES, BLOG_SOURCE


class DiscordNotifier:
    WEBHOOK_LABELS = ["UNI", "WUMPUSCENTRAL"]
    ERROR_LABELS = ["UNI"]
    PING_ROLES = {
        "WUMPUSCENTRAL": "1106559083391238276",
    }
    SEND_DELAY_SECONDS = 2
    BUCKET_ACTIONS = [
        ("added", "ADDED"),
        ("updated", "UPDATED"),
        ("removed", "REMOVED"),
    ]
    SOURCE_CREATORS = {
        BLOG_SOURCE: blog_embeds.create_blog_embed,
        **{source: zendesk_embeds.create_zendesk_embed for source in ZENDESK_SOURCES},
    }
    EMBED_COLOR_FAIL = 0xED4245

    def send(self, diff, commit_url=None, line_stats=None):
        if self._is_empty(diff):
            logger.info("Diff is empty — nothing to notify.")
            return

        logger.info(f"Dispatching changes to {len(self.WEBHOOK_LABELS)} webhook target(s)...")

        sent = 0
        ping_remaining = True

        for source, buckets in diff.items():
            creator = self.SOURCE_CREATORS.get(source)
            if creator is None:
                logger.warning(f"No embed handler for source '{source}' — skipping.")
                continue

            for bucket, action in self.BUCKET_ACTIONS:
                entries = buckets.get(bucket, {})
                for entry_key, entry in entries.items():
                    message = creator(action, entry, commit_url, source, line_stats)
                    if message is None:
                        continue
                    self._dispatch(message, source, action, entry_key, ping=ping_remaining)
                    ping_remaining = False
                    sent += 1
                    time.sleep(self.SEND_DELAY_SECONDS)

        logger.success(f"Notify complete: dispatched {sent} embed(s).")

    def send_error(self, monitor, run_url=None):
        status = monitor.to_dict() if hasattr(monitor, "to_dict") else monitor
        failed = [
            name for name, s in status.items() if s.get("status") != "ok"
        ]
        total = len(status)
        embed = {
            "title": "Scrape aborted — source health failure",
            "color": self.EMBED_COLOR_FAIL,
            "description": (
                f"{len(failed)}/{total} source(s) failed. "
                f"Run aborted to protect data integrity."
            ),
            "fields": [],
        }
        for name, info in status.items():
            is_ok = info.get("status") == "ok"
            marker = "OK" if is_ok else "FAIL"
            value = (
                f"**{marker}**  `{info.get('status', '?')}`\n"
                f"articles: `{info.get('articles', 0)}`  attempts: `{info.get('attempts', 0)}`"
            )
            if info.get("error"):
                err = info["error"]
                if len(err) > 200:
                    err = err[:197] + "..."
                value += f"\nerror: `{err}`"
            embed["fields"].append({
                "name": name,
                "value": value,
                "inline": True,
            })
        if run_url:
            embed["fields"].append({
                "name": "Actions Run",
                "value": f"[View run logs]({run_url})",
                "inline": False,
            })
        message = {"embeds": [embed]}
        for label in self.ERROR_LABELS:
            webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{label}")
            if not webhook_url:
                logger.warning(f"DISCORD_WEBHOOK_{label} not set — skipping error embed.")
                continue
            try:
                response = requests.post(webhook_url, json=message, timeout=10)
                if response.status_code in (200, 204):
                    logger.success(
                        f"Dispatched health-failure error embed to Discord ({label})."
                    )
                else:
                    logger.error(
                        f"Discord ({label}) returned {response.status_code} "
                        f"for error embed: {response.text}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to dispatch error embed to Discord ({label}): {e}"
                )

    def _dispatch(self, message, source, action, entry_key, ping=False):
        for label in self.WEBHOOK_LABELS:
            webhook_url = os.environ.get(f"DISCORD_WEBHOOK_{label}")
            if not webhook_url:
                logger.warning(f"DISCORD_WEBHOOK_{label} not set — skipping.")
                continue

            payload = message
            role_id = self.PING_ROLES.get(label)
            if ping and role_id:
                payload = {"content": f"<@&{role_id}>", **message}

            try:
                response = requests.post(
                    webhook_url,
                    json=payload,
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
