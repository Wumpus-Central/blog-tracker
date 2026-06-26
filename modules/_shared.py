"""Shared constants and helpers used across modules.

Keeping the source list and the blog key in one place avoids two copies
of the same truth (main.py vs discord.py) and replaces the repeated
"blog" magic string with a named constant.
"""

ZENDESK_SOURCES = ["support", "support-dev", "support-apps", "creator-support"]
BLOG_SOURCE = "blog"


def lookup_entry_by_id(data, source, article_id):
    """Linear search for an entry by its 'id' field. Returns the entry or None.

    Used by the differ (removed entries come from old_data, added/updated
    from new_data) and by the archiver (looking up metadata for a removed
    article before moving it). str() comparison handles the API returning
    integer ids while git status / archive keys are strings.
    """
    for entry in data.get(source, []):
        if str(entry.get("id")) == str(article_id):
            return entry
    return None