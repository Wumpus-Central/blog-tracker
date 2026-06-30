import subprocess
from loguru import logger

from modules._shared import ZENDESK_SOURCES


def build_line_stats(data_dir):
    logger.info(f"Computing line stats in {data_dir}...")
    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", "HEAD~1", "HEAD"],
            cwd=data_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Failed to run git diff --numstat: {e}")
        return {}

    if result.returncode != 0:
        logger.warning(f"git diff --numstat exited {result.returncode}: {result.stderr.strip()}")
        return {}

    source_set = set(ZENDESK_SOURCES)
    stats = {}

    for line in result.stdout.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue

        added_s, removed_s, path = parts[0], parts[1], parts[2]

        if added_s == "-" or removed_s == "-":
            continue

        p = path.split("/")
        if len(p) < 2 or p[0] not in source_set:
            continue

        filename = p[-1]
        if not filename.endswith(".md"):
            continue

        source = p[0]
        article_id = filename[:-3]
        key = f"{source}/{article_id}"

        stats[key] = {"added": int(added_s), "removed": int(removed_s)}

    logger.success(f"Line stats: {len(stats)} entries")
    logger.debug(f"Line stats:\n{stats}")
    return stats