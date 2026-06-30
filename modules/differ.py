import json
import subprocess
from loguru import logger

from modules._shared import BLOG_SOURCE, lookup_entry_by_id


class Differ:
    def compute(self, output_dir, sources, new_data, old_data):
        source_set = set(sources)
        result = {}
        for source in sources:
            result[source] = {"added": {}, "removed": {}, "updated": {}}
        result[BLOG_SOURCE] = {"added": {}, "removed": {}, "updated": {}}

        try:
            status_output = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=10
            ).stdout
        except Exception as e:
            logger.error(f"Failed to run git status in {output_dir}: {e}")
            return result

        skipped_lines = 0

        for line in status_output.splitlines():
            if not line.strip():
                continue

            status = line[:2]
            path = line[3:]

            if path == "state.json":
                skipped_lines += 1
                continue

            parts = path.split("/")
            if len(parts) < 2 or parts[0] not in source_set:
                skipped_lines += 1
                continue
            filename = parts[-1]
            if not filename.endswith(".md"):
                skipped_lines += 1
                continue

            source = parts[0]
            article_id = filename[:-3]

            if status == "??":
                bucket = "added"
                entry = lookup_entry_by_id(new_data, source, article_id)
            elif status[1] == "M":
                bucket = "updated"
                entry = lookup_entry_by_id(new_data, source, article_id)
            elif status[1] == "D":
                bucket = "removed"
                entry = lookup_entry_by_id(old_data, source, article_id)
            else:
                continue

            if entry is None:
                logger.warning(f"Diff: no metadata for {bucket} {source}/{article_id}")
                continue

            result[source][bucket][article_id] = entry

        if skipped_lines > 0:
            logger.debug(f"Skipped {skipped_lines} non-article line(s) from git status.")

        self._diff_blog(old_data, new_data, result)

        summary = ", ".join(
            f"{s}: {len(b['added'])}a/{len(b['updated'])}u/{len(b['removed'])}r"
            for s, b in result.items()
        )
        logger.info(f"Diff computed: {summary}")
        logger.debug(f"Full diff:\n{json.dumps(result, indent=2)}")
        return result

    def _diff_blog(self, old_data, new_data, result):
        old_posts = {}
        for post in old_data.get(BLOG_SOURCE, []):
            link = post.get("link")
            if link:
                old_posts[link] = post

        new_posts = {}
        for post in new_data.get(BLOG_SOURCE, []):
            link = post.get("link")
            if link:
                new_posts[link] = post

        for link, post in new_posts.items():
            if link not in old_posts:
                result[BLOG_SOURCE]["added"][link] = post
            elif old_posts[link] != post:
                result[BLOG_SOURCE]["updated"][link] = post

        for link, post in old_posts.items():
            if link not in new_posts:
                result[BLOG_SOURCE]["removed"][link] = post

        logger.info(
            f"Blog diff: {len(result[BLOG_SOURCE]['added'])} added, "
            f"{len(result[BLOG_SOURCE]['updated'])} updated, "
            f"{len(result[BLOG_SOURCE]['removed'])} removed"
        )
