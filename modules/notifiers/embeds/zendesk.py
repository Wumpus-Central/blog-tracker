from datetime import datetime
from loguru import logger

COLORS = {
    "ADDED": 0x57F287,
    "UPDATED": 0xFEE75C,
    "REMOVED": 0xED4245,
}

SOURCE_LABELS = {
    "support": "Discord Support",
    "support-dev": "Discord Developer Support",
    "support-apps": "Discord Apps Support",
    "creator-support": "Creator Support",
}


def create_zendesk_embed(action, entry, commit_url=None, source=None, line_stats=None):
    if not entry:
        logger.warning(f"Zendesk embed: empty entry for action={action}, skipping.")
        return None

    title = entry.get("title")
    if not title:
        logger.warning(f"Zendesk embed: empty title for action={action}, skipping.")
        return None

    color = COLORS.get(action)
    if color is None:
        logger.warning(f"Zendesk embed: unknown action '{action}', skipping.")
        return None

    embed = {"title": title, "color": color}

    html_url = entry.get("html_url")
    if html_url:
        embed["url"] = html_url

    thumbnail_url = entry.get("thumbnail_url")
    if thumbnail_url and action == "ADDED":
        embed["image"] = {"url": thumbnail_url}

    fields = []

    source_label = SOURCE_LABELS.get(source, source or "Unknown")
    fields.append({"name": "Source", "value": source_label, "inline": True})

    article_id = entry.get("id")
    if article_id is not None:
        fields.append({"name": "Article ID", "value": str(article_id), "inline": True})

    changes = _format_changes(source, entry, line_stats)
    if changes:
        fields.append({"name": "Changes", "value": changes, "inline": True})

    created_at = entry.get("created_at")
    if created_at:
        epoch = _iso_to_epoch(created_at)
        if epoch:
            fields.append({"name": "Created", "value": f"<t:{epoch}:R>", "inline": True})

    promoted = entry.get("promoted")
    if promoted is not None:
        fields.append({"name": "Promoted", "value": "Yes" if promoted else "No", "inline": True})

    if commit_url:
        fields.append({"name": "Commit", "value": f"[View commit]({commit_url})", "inline": True})

    label_names = entry.get("label_names")
    if label_names:
        fields.append({"name": "Labels", "value": ", ".join(label_names), "inline": False})

    if fields:
        embed["fields"] = fields

    return {"embeds": [embed]}


def _format_changes(source, entry, line_stats):
    if not line_stats:
        return "N/A"

    article_id = entry.get("id")
    if article_id is None:
        return "N/A"

    key = f"{source}/{article_id}"
    stats = line_stats.get(key)
    if stats is None:
        return "N/A"

    added = stats.get("added", 0)
    removed = stats.get("removed", 0)
    edited = min(added, removed)
    pure_added = added - edited
    pure_removed = removed - edited
    return f"+{pure_added} ~{edited} -{pure_removed}"


def _iso_to_epoch(iso_str):
    try:
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_str)
        return int(dt.timestamp())
    except Exception as e:
        logger.warning(f"Failed to parse ISO timestamp '{iso_str}': {e}")
        return None