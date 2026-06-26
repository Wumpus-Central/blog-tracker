ZENDESK_SOURCES = ["support", "support-dev", "support-apps", "creator-support"]
BLOG_SOURCE = "blog"


def lookup_entry_by_id(data, source, article_id):
    for entry in data.get(source, []):
        if str(entry.get("id")) == str(article_id):
            return entry
    return None