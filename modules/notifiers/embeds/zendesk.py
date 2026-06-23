from loguru import logger

COLORS = {
    "ADDED": 0x57F287,
    "UPDATED": 0xFEE75C,
    "REMOVED": 0xED4245,
}


def create_zendesk_embed(action, entry, commit_url=None):
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

    if commit_url:
        embed["fields"] = [{"name": "Commit", "value": f"[View commit]({commit_url})", "inline": True}]

    return {"embeds": [embed]}
