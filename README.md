# Blog Tracker

Automated scraper that tracks Discord's Zendesk help-center articles and blog posts, detects changes, and dispatches per-change notifications via Discord webhooks. Runs hourly on GitHub Actions.

![CI](https://github.com/Wumpus-Central/blog-tracker/actions/workflows/scraper_workflow.yaml/badge.svg?branch=source)
![Python](https://img.shields.io/badge/python-3.14-blue.svg)

## Architecture

This repository uses a **two-branch architecture** to separate code from generated data:

| Branch | Role | Contents |
|--------|------|----------|
| `source` (default) | Code | `main.py`, `modules/`, `.github/`, `.gitignore` |
| `data` | Output | `state.json`, `support/`, `support-dev/`, `support-apps/`, `creator-support/` |

The scraper runs on `source` (since GitHub Actions scheduled workflows only fire on the default branch), but writes its output into a checkout of `data`, then commits and pushes changes there. This keeps the data branch's history clean (only data commits) and the source branch's history focused on code.

```
GitHub Actions (source branch, cron 51 * * * *)
│
├── checkout source → ./code    (scraper code + workflow)
├── checkout data   → ./data    (state.json + .md files)
├── pip install from code/requirements.txt
│
├── python code/main.py --scrape    (OUTPUT_DIR=data, DIFF_FILE=./diff.json)
│   ├── scrape Zendesk → data/{source}/{id}.md + state.json
│   ├── scrape Blog    → state.json
│   └── differ         → diff.json (full entry objects, NOT notified yet)
│
├── commit & push data/ → data branch
│   └── capture COMMIT_SHA → $GITHUB_ENV
│
└── python code/main.py --notify --commit-sha $COMMIT_SHA    (if COMMIT_SHA set)
    └── per-change Discord embeds (color-coded, commit URL field, 2s delay)
```

## Module Structure

```
main.py                     ScraperEngine entrypoint (argparse: --scrape / --notify)
modules/
  differ.py                 Diff: git status (Zendesk) + state comparison (blog)
  providers/
    zendesk.py              Zendesk help-center API → .md files + state.json
    blog.py                 Discord blog RSS → state.json
  notifiers/
    discord.py              Orchestrator: iterates diff, dispatches embeds, 2s delay
    embeds/
      zendesk.py            create_zendesk_embed(action, entry, commit_url)
      blog.py               create_blog_embed(action, entry, commit_url)
```

## How It Works

1. **Scrape Zendesk** — paginates through the help-center API for each source (`support`, `support-dev`, `support-apps`, `creator-support`), writes each article's HTML body to `data/{source}/{id}.md`, and stores metadata + a SHA-256 hash of the body in `state.json`.
2. **Scrape Blog** — fetches the Discord blog RSS feed and stores post metadata in `state.json`.
3. **Diff** — runs `git status --porcelain` in the `data` checkout to detect added (`??`), updated (` M`), and removed (` D`) Zendesk article files. Blog posts are diffed by comparing old vs new `state.json` entries by `link` (since blog posts are not written as `.md` files). Each diff entry carries the **full object** from the new state (added/updated) or old state (removed), persisted to `diff.json`.
4. **Notify** — loads `diff.json` and dispatches one Discord embed per change (green = added, yellow = updated, red = removed). Zendesk embeds link the title to the article's `html_url`; blog embeds include the summary as description and the thumbnail as image. Each embed carries a clickable "View commit" field linking to the data-branch commit that captured the change. A 2-second delay separates sends to respect webhook rate limits.

## CI/CD

The workflow (`.github/workflows/scraper_workflow.yaml`) runs:
- **Hourly** via cron (`51 * * * *`)
- On **push** to `source`
- **Manually** via workflow dispatch

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
- [ ] Rich Zendesk embeds (url, labels, edited_at, thumbnail) — currently title-only
- [ ] Add blog posts scraping as `.md` files (currently only stored in `state.json`)
- [ ] Add newsroom posts scraping as `.md` files (currently only stored in `state.json`)
- [ ] Add `WUMPUSCENTRAL` Discord webhook for the official server
- [ ] Centralized API notifier for reporting changes to Wumpus Central services
- [ ] Implement diff-based commit messages (new/updated/removed counts)
