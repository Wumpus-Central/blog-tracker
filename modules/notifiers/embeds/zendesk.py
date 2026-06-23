from loguru import logger

COLORS = {
    "ADDED": 0x57F287,
    "UPDATED": 0xFEE75C,
    "REMOVED": 0xED4245,
}


def create_zendesk_embed(action, article, title):
    if not title:
        logger.warning(f"Zendesk embed: empty title for action={action}, skipping.")
        return None

    color = COLORS.get(action)
    if color is None:
        logger.warning(f"Zendesk embed: unknown action '{action}', skipping.")
        return None

    embed = {"title": title, "color": color}

    return {"embeds": [embed]}
