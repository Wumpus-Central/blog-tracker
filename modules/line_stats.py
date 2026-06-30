import json
import subprocess
import sys
from loguru import logger

from modules._shared import ZENDESK_SOURCES


def build_line_stats(data_dir, output_file):
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
        _save({}, output_file)
        return

    if result.returncode != 0:
        logger.warning(f"git diff --numstat exited {result.returncode}: {result.stderr.strip()}")
        _save({}, output_file)
        return

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

    _save(stats, output_file)
    logger.success(f"Line stats: {len(stats)} entries → {output_file}")


def load_line_stats(stats_file):
    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"line_stats.json not found at {stats_file} — embeds will show N/A.")
        return {}
    except Exception as e:
        logger.error(f"Failed to load line_stats.json: {e}")
        return {}


def _save(stats, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)
    logger.debug(f"Line stats written to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--output", default="./line_stats.json")
    args = parser.parse_args()

    import modules.log_setup
    modules.log_setup.setup_logging()

    build_line_stats(args.data_dir, args.output)