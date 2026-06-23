from loguru import logger

COLORS = {
    "ADDED": 0x57F287,
    "UPDATED": 0xFEE75C,
    "REMOVED": 0xED4245,
}


def create_blog_embed(action, post, title):
    if not title:
        logger.warning(f"Blog embed: empty title for action={action}, skipping.")
        return None

    color = COLORS.get(action)
    if color is None:
        logger.warning(f"Blog embed: unknown action '{action}', skipping.")
        return None

    embed = {"title": title, "color": color}

    if post is not None:
        link = post.get("link")
        if link:
            embed["url"] = link

        summary = post.get("summary")
        if summary:
            embed["description"] = summary

        media_thumbnail_url = post.get("media_thumbnail_url")
        if media_thumbnail_url:
            embed["image"] = {"url": media_thumbnail_url}

    return {"embeds": [embed]}
