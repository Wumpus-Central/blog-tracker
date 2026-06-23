from loguru import logger

COLORS = {
    "ADDED": 0x57F287,
    "UPDATED": 0xFEE75C,
    "REMOVED": 0xED4245,
}


def create_blog_embed(action, entry, commit_url=None):
    if not entry:
        logger.warning(f"Blog embed: empty entry for action={action}, skipping.")
        return None

    title = entry.get("title")
    if not title:
        logger.warning(f"Blog embed: empty title for action={action}, skipping.")
        return None

    color = COLORS.get(action)
    if color is None:
        logger.warning(f"Blog embed: unknown action '{action}', skipping.")
        return None

    embed = {"title": title, "color": color}

    link = entry.get("link")
    if link:
        embed["url"] = link

    summary = entry.get("summary")
    if summary:
        embed["description"] = summary

    media_thumbnail_url = entry.get("media_thumbnail_url")
    if media_thumbnail_url:
        embed["image"] = {"url": media_thumbnail_url}

    if commit_url:
        embed["fields"] = [{"name": "Commit", "value": f"[View commit]({commit_url})", "inline": True}]

    return {"embeds": [embed]}
