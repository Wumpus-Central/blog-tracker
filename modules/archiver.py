import json
import os
import shutil
from loguru import logger

from modules._shared import BLOG_SOURCE, lookup_entry_by_id


class Archiver:
    def process(self, old_data, new_data, sources, output_dir):
        archive_dir = os.path.join(output_dir, "archive")
        archive_state_file = os.path.join(archive_dir, "state.json")

        archive_state = self._load_state(archive_state_file)
        for source in sources:
            archive_state.setdefault(source, [])

        archived_count = 0
        restored_count = 0

        for source in sources:
            archive_subdir = os.path.join(archive_dir, source)
            os.makedirs(archive_subdir, exist_ok=True)

            old_ids = {str(a.get("id")) for a in old_data.get(source, [])}
            new_ids = {str(a.get("id")) for a in new_data.get(source, [])}
            archived_ids = {str(a.get("id")) for a in archive_state[source]}

            for aid in (archived_ids & new_ids):
                archive_path = os.path.join(archive_subdir, f"{aid}.md")
                if os.path.exists(archive_path):
                    os.remove(archive_path)
                    logger.info(f"Restored {source}/{aid} from archive (re-published by Discord)")
                archive_state[source] = [
                    a for a in archive_state[source] if str(a.get("id")) != aid
                ]
                restored_count += 1

            for aid in (old_ids - new_ids):
                entry = lookup_entry_by_id(old_data, source, aid)
                if entry is None:
                    logger.warning(f"Archive: no metadata for removed {source}/{aid}")
                    continue

                src_path = os.path.join(output_dir, source, f"{aid}.md")
                dst_path = os.path.join(archive_subdir, f"{aid}.md")
                if os.path.exists(src_path):
                    shutil.move(src_path, dst_path)
                    logger.info(f"Archived article {source}/{aid}")
                else:
                    logger.warning(f"Source .md not found for {source}/{aid} — entry archived only")

                archive_state[source].append(entry)
                archived_count += 1

        archive_state.setdefault(BLOG_SOURCE, [])
        blog_archived, blog_restored = self._archive_blog(old_data, new_data, archive_state)
        archived_count += blog_archived
        restored_count += blog_restored

        self._save_state(archive_state, archive_state_file)

        logger.success(
            f"Archive complete: {archived_count} archived, {restored_count} restored "
            f"across {len(sources)} Zendesk sources + blog"
        )

    @staticmethod
    def _archive_blog(old_data, new_data, archive_state):
        old_links = {p.get("link"): p for p in old_data.get(BLOG_SOURCE, []) if p.get("link")}
        new_links = {p.get("link") for p in new_data.get(BLOG_SOURCE, []) if p.get("link")}
        archived_links = {p.get("link") for p in archive_state[BLOG_SOURCE] if p.get("link")}

        restored = 0
        for link in (archived_links & new_links):
            archive_state[BLOG_SOURCE] = [
                p for p in archive_state[BLOG_SOURCE] if p.get("link") != link
            ]
            logger.info(f"Restored blog post from archive (re-published): {link}")
            restored += 1

        archived = 0
        for link, post in old_links.items():
            if link not in new_links:
                archive_state[BLOG_SOURCE].append(post)
                logger.info(f"Archived blog post: {link}")
                archived += 1

        return archived, restored

    @staticmethod
    def _load_state(archive_state_file):
        try:
            with open(archive_state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("No archive state found — first archive run.")
            return {}
        except Exception as e:
            logger.error(f"Failed to load archive state: {e}")
            return {}

    @staticmethod
    def _save_state(archive_state, archive_state_file):
        archive_dir = os.path.dirname(archive_state_file)
        os.makedirs(archive_dir, exist_ok=True)
        with open(archive_state_file, "w", encoding="utf-8") as f:
            json.dump(archive_state, f, indent=4)
        logger.success(f"Archive state written to {archive_state_file}")