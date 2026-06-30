# Blog Tracker

Automated scraper that tracks Discord's Zendesk help-center articles and blog posts, detects changes, and dispatches per-change notifications via Discord webhooks. Runs hourly on GitHub Actions.

![CI](https://github.com/Wumpus-Central/blog-tracker/actions/workflows/scraper_workflow.yaml/badge.svg?branch=source)
![Python](https://img.shields.io/badge/python-3.14-blue.svg)

## Architecture

This repository uses a **two-branch architecture** to separate code from generated data:

| Branch | Role | Contents |
|--------|------|----------|
| `source` (default) | Code | `main.py`, `modules/`, `.github/`, `.gitignore` |
| `data` | Output | `state.json`, `support/`, `support-dev/`, `support-apps/`, `creator-support/`, `archive/` |

The scraper runs on `source` (since GitHub Actions scheduled workflows only fire on the default branch), but writes its output into a checkout of `data`, then commits and pushes changes there. This keeps the data branch's history clean (only data commits) and the source branch's history focused on code.

```
GitHub Actions (source branch, cron 0 * * * *)
│
├── checkout source → ./code    (scraper code + workflow)
├── checkout data   → ./data    (state.json + .md files)
├── pip install from code/requirements.txt
│
├── python code/main.py --scrape    (OUTPUT_DIR=data, DIFF_FILE=./diff.json)
│   ├── fetch Zendesk   → in-memory articles (no file ops yet)
│   ├── fetch Blog      → in-memory posts (RSS)
│   ├── archiver        → move removed .md to data/archive/{source}/, update archive/state.json
│   ├── write Zendesk   → data/{source}/{id}.md + hash bodies
│   └── differ          → diff.json (full entry objects, NOT notified yet)
│
├── commit & push data/ → data branch
│   └── capture COMMIT_SHA → $GITHUB_ENV
│
├── git diff --numstat HEAD~1 HEAD → line_stats.json    (if COMMIT_SHA set)
│
└── python code/main.py --notify --commit-sha $COMMIT_SHA    (if COMMIT_SHA set)
    └── per-change Discord embeds (color-coded, Changes, commit URL field, 2s delay)
```

## Module Structure

```
main.py                     ScraperEngine entrypoint (argparse: --scrape / --notify)
modules/
  _shared.py                Shared constants (ZENDESK_SOURCES, BLOG_SOURCE) + lookup_entry_by_id()
  log_setup.py              Loguru sink configuration (setup_logging())
  line_stats.py             Build/load line_stats.json from git diff --numstat
  archiver.py               Archive removed articles: move .md to archive/, update archive/state.json
  differ.py                 Diff: git status (Zendesk) + state comparison (blog)
  providers/
    zendesk.py              Zendesk help-center API — fetch() + write() split
    blog.py                 Discord blog RSS → state.json
  notifiers/
    discord.py              Orchestrator: iterates diff, dispatches embeds, 2s delay
    embeds/
      zendesk.py            create_zendesk_embed(action, entry, commit_url, source, line_stats)
      blog.py               create_blog_embed(action, entry, commit_url, source, line_stats)
```

## How It Works

1. **Scrape Zendesk** — paginates through the help-center API for each source (`support`, `support-dev`, `support-apps`, `creator-support`), writes each article's HTML body to `data/{source}/{id}.md`, and stores metadata + a SHA-256 hash of the body in `state.json`.
2. **Scrape Blog** — fetches the Discord blog RSS feed and stores post metadata in `state.json`.
3. **Diff** — runs `git status --porcelain` in the `data` checkout to detect added (`??`), updated (` M`), and removed (` D`) Zendesk article files. Blog posts are diffed by comparing old vs new `state.json` entries by `link` (since blog posts are not written as `.md` files). Each diff entry carries the **full object** from the new state (added/updated) or old state (removed), persisted to `diff.json`.
4. **Line stats** — runs `git diff --numstat HEAD~1 HEAD` in the `data` checkout to count added/removed lines per `.md` file, persists results to `line_stats.json` in the workspace root. Used by the notify step to show a `+N ~M -K` Changes field in Zendesk embeds.
5. **Notify** — loads `diff.json` and dispatches one Discord embed per change (green = added, yellow = updated, red = removed). Zendesk embeds show a 2×3 grid of inline fields (Source, Article ID, Changes, Created, Promoted, Commit) plus a full-width Labels field; the Changes field (`+N ~M -K`) comes from `line_stats.json`. Blog embeds link the title to the post, include the summary as description and the thumbnail as image. Each embed carries a clickable "View commit" field linking to the data-branch commit that captured the change. A 2-second delay separates sends to respect webhook rate limits.

## Archiving

When Discord removes an article from Zendesk, the scraper preserves it instead of discarding it. Before each scrape overwrites the source directories, the **archiver** (`modules/archiver.py`) identifies articles present in the previous `state.json` but missing from the fresh API response and:

- **Moves** `data/{source}/{id}.md` → `data/archive/{source}/{id}.md` (preserving the last-known HTML body).
- **Appends** the article's entry (metadata + body hash) to `data/archive/state.json` under the matching source key.

Blog posts are archived as **JSON-only** entries in `archive/state.json["blog"]` (no `.md` files, since blog posts are not written to disk today). If Discord later re-publishes an archived article or blog post, the archive copy is **removed** and fresh content lives at `data/{source}/{id}.md` again — the archive keeps only the most recent removed snapshot, not historical versions.

`archive/state.json` entries are pristine copies of the old `state.json` entry (no extra metadata). The differ needs no changes: `git status` still flags the moved `.md` as ` D` (removed from `data/{source}/`) and ignores `archive/` paths (not a tracked source).

## CI/CD

The workflow (`.github/workflows/scraper_workflow.yaml`) runs:
- **Hourly** via cron (`0 * * * *`)
- On **push** to `source`
- **Manually** via workflow dispatch or repository dispatch

## Manual Dispatch

The workflow can be triggered on demand via the GitHub API. This is useful for running the scraper from an external scheduler (e.g. Termux cron on a phone).

### Repository dispatch (external webhook)

Sends a `repository_dispatch` event with a custom `event_type` — ideal for scheduling from a phone or external service:

```bash
curl -s -o /dev/null \
  --connect-timeout 10 \
  --max-time 30 \
  -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/Wumpus-Central/blog-tracker/dispatches \
  -d '{"event_type": "trigger-scraping"}'
```

### Workflow dispatch (API)

Alternatively, trigger the workflow directly by filename:

```bash
curl -s -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_PAT" \
  https://api.github.com/repos/Wumpus-Central/blog-tracker/actions/workflows/scraper_workflow.yaml/dispatches \
  -d '{"ref":"source"}'
```

Both methods require a Personal Access Token with **Actions: Write** (fine-grained) or **repo** (classic) scope on this repository. Store the token as an environment variable (e.g. `GITHUB_PAT`) and schedule the curl via cron on your device.

It performs three stages:

1. **Scrape** — runs `python code/main.py --scrape` with `OUTPUT_DIR=data` and `DIFF_FILE=./diff.json`. Scrapes all sources, writes `state.json` + `.md` files into the `data` checkout, computes the diff, and persists it to `diff.json` in the workspace root (outside `data/`, so it is not committed).
2. **Commit & Push** — commits changes in `data/` as `github-actions[bot]` and pushes to the `data` branch. On success, captures the commit SHA into `$GITHUB_ENV` as `COMMIT_SHA`. Skipped if there are no changes.
3. **Notify** — runs only if `COMMIT_SHA` is set. Invokes `python code/main.py --notify --commit-sha $COMMIT_SHA` to load `diff.json` and dispatch per-change Discord embeds with a link to the commit.

## Local Development

```bash
git clone -b source https://github.com/Wumpus-Central/blog-tracker.git
cd blog-tracker

python -m venv venv
./venv/bin/pip install -r requirements.txt

# Show available modes
./venv/bin/python main.py

# Scrape into a data branch checkout (writes state.json + .md + diff.json)
OUTPUT_DIR=./data ./venv/bin/python main.py --scrape

# Dispatch notifications from a previously generated diff.json
DIFF_FILE=./diff.json ./venv/bin/python main.py --notify --commit-sha <SHA>
```

> **Note:** The Zendesk differ relies on `git status` in the output directory, so for meaningful Zendesk diffs run `--scrape` against a checkout of the `data` branch. Running locally with `OUTPUT_DIR=.` will report all Zendesk files as new (untracked). The blog differ compares `state.json` entries directly, so blog diffs work locally regardless of the output directory.

## Configuration

### Environment Variables

| Variable | Default | Mode | Description |
|----------|---------|------|-------------|
| `OUTPUT_DIR` | `.` | scrape | Directory where `state.json` and per-source `.md` files are written |
| `DIFF_FILE` | `./diff.json` | both | Path to `diff.json` (written by `--scrape`, read by `--notify`) |
| `LINE_STATS_FILE` | `./line_stats.json` | notify | Path to `line_stats.json` (written by the workflow's numstat step, read by `--notify`) |
| `DISCORD_WEBHOOK_UNI` | — | notify | Discord webhook URL for the UNI server |

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DISCORD_WEBHOOK_UNI` | Discord webhook URL for the UNI server |

To add the official Wumpus Central server in the future, I will add a `DISCORD_WEBHOOK_WUMPUSCENTRAL` secret and append `"WUMPUSCENTRAL"` to `WEBHOOK_LABELS` in `modules/notifiers/discord.py`.

## Data Format

`state.json` contains all scraped data with top-level keys per source:

- **Article sources** (`support`, `support-dev`, `support-apps`, `creator-support`): arrays of article objects from the Zendesk API. The `body` field is replaced with a SHA-256 hash of the HTML content; the full HTML lives in `data/{source}/{id}.md`.
- **`blog`**: array of post objects from the RSS feed, containing `title`, `link`, `summary`, `published`, and `media_thumbnail_url`.

`diff.json` is written by `--scrape` and read by `--notify`. It mirrors the diff structure with top-level keys per source, each containing `added`, `updated`, and `removed` buckets. Every entry maps its key (article `id` for Zendesk, post `link` for blog) to the **full object** captured at diff time — added/updated entries come from the new state, removed entries from the old state.

## Roadmap

- [x] Build good looking embeds for webhooks
- [x] Rich Zendesk embeds (url, labels, created, promoted, thumbnail)
- [x] Archive removed articles and blog posts to `data/archive/`
- [ ] Add blog posts scraping as `.md` files (currently only stored in `state.json`; archived as JSON-only)
- [ ] Add newsroom posts scraping as `.md` files (currently only stored in `state.json`)
- [ ] Add `WUMPUSCENTRAL` Discord webhook for the official server
- [ ] Centralized API notifier for reporting changes to Wumpus Central services
- [ ] Implement diff-based commit messages (new/updated/removed counts)
