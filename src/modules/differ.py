import json
import subprocess
from loguru import logger

class Differ:
    def compute(self, output_dir, sources, new_data, old_data):
        source_set = set(sources)
        result = {}
        for source in sources:
            result[source] = {"added": {}, "removed": {}, "updated": {}}
        result["blog"] = {"added": {}, "removed": {}, "updated": {}}

        # git status --porcelain runs in the data checkout (output_dir).
        # The workflow does `git add .` only AFTER main.py exits, so during
        # this run all changes are unstaged: ?? = new, " M" = modified, " D" = deleted.
        # Note: with OUTPUT_DIR="." on a non-data checkout everything reads as
        # untracked (??) — this differ is a CI feature against the data branch.
        try:
            status_output = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=10
            ).stdout
        except Exception as e:
            logger.error(f"Failed to run git status in {output_dir}: {e}")
            return result

        for line in status_output.splitlines():
            if not line.strip():
                continue

            status = line[:2]
            path = line[3:]

            # state.json lives at output_dir root; skip it.
            if path == "state.json":
                continue

            # Parse "{source}/{id}.md"
            parts = path.split("/")
            if len(parts) < 2 or parts[0] not in source_set:
                continue
            filename = parts[-1]
            if not filename.endswith(".md"):
                continue

            source = parts[0]
            article_id = filename[:-3]

            if status == "??":
                bucket = "added"
                title = self._lookup_title(new_data, source, article_id)
            elif status[1] == "M":
                bucket = "updated"
                title = self._lookup_title(new_data, source, article_id)
            elif status[1] == "D":
                bucket = "removed"
                title = self._lookup_title(old_data, source, article_id)
            else:
                continue

            if title is None:
                logger.warning(f"Diff: no metadata for {bucket} {source}/{article_id}")
                continue

            result[source][bucket][article_id] = title

        logger.info(f"Diff computed:\n{json.dumps(result, indent=2)}")
        return result

    def _lookup_title(self, data, source, article_id):
        for entry in data.get(source, []):
            if str(entry.get("id")) == article_id:
                return entry.get("title", "Unknown Title")
        return None
