# Blog Tracker

Automated scraper that tracks Discord's Zendesk help-center articles and blog posts, detects changes, and dispatches notifications via Discord webhooks. Runs hourly on GitHub Actions.

![CI](https://github.com/Wumpus-Central/blog-tracker/actions/workflows/scraper_workflow.yaml/badge.svg?branch=source)
![Python](https://img.shields.io/badge/python-3.14-blue.svg)

## Architecture

This repository uses a **two-branch architecture** to separate code from generated data:

| Branch | Role | Contents |
|--------|------|----------|
| `source` (default) | Code | `src/`, `.github/`, `.gitignore` |
| `data` | Output | `state.json`, `support/`, `support-dev/`, `support-apps/`, `creator-support/` |

The scraper runs on `source` (since GitHub Actions scheduled workflows only fire on the default branch), but writes its output into a checkout of `data`, then commits and pushes changes there. This keeps the data branch's history clean (only data commits) and the source branch's history focused on code.

```
GitHub Actions (source branch, hourly cron)
│
├── checkout source → ./code    (scraper code + workflow)
├── checkout data   → ./data    (state.json + .md files)
│
├── pip install from code/src/requirements.txt
├── python code/src/main.py     (OUTPUT_DIR=data)
│   ├── scrape Zendesk → data/{source}/{id}.md + state.json
│   ├── scrape Blog    → state.json
│   ├── differ         → git status in data/ → A/M/D
│   └── notify Discord → webhook POST
│
└── commit & push data/ → data branch
```

## How It Works

1. **Scrape Zendesk** — paginates through the help-center API for each source (`support`, `support-dev`, `support-apps`, `creator-support`), writes each article's HTML body to `data/{source}/{id}.md`, and stores metadata + a SHA-256 hash of the body in `state.json`.
2. **Scrape Blog** — fetches the Discord blog RSS feed and stores post metadata in `state.json`.
3. **Diff** — runs `git status --porcelain` in the `data` checkout to detect added (`??`), updated (` M`), and removed (` D`) article files. Enriches each entry with its title from the new or old state.
4. **Notify** — if the diff is non-empty, posts the JSON payload to each configured Discord webhook.

## CI/CD

The workflow (`.github/workflows/scraper_workflow.yaml`) runs:
- **Hourly** via cron (`0 * * * *`)
- On **push** to `source`
- **Manually** via workflow dispatch

It performs the two-checkout dance described above, runs the scraper with `OUTPUT_DIR=data`, then commits and pushes any changes to the `data` branch as `github-actions[bot]`.

## Local Development

```bash
git clone -b source https://github.com/Wumpus-Central/blog-tracker.git
cd blog-tracker

python -m venv venv
./venv/bin/pip install -r src/requirements.txt

# Run with output to current directory (creates ./support/, ./state.json, etc.)
./venv/bin/python src/main.py

# Or run against a data branch checkout
OUTPUT_DIR=./data ./venv/bin/python src/main.py
```

> **Note:** The differ relies on `git status` in the output directory. For meaningful diffs, run against a checkout of the `data` branch. Running locally with `OUTPUT_DIR=.` will report all files as new (untracked).

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_DIR` | `.` | Directory where scraped data and `state.json` are written |
| `DISCORD_WEBHOOK_UNI` | — | Discord webhook URL for the UNI server |

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DISCORD_WEBHOOK_UNI` | Discord webhook URL for the UNI server |

To add the official Wumpus Central server in the future, I will add a `DISCORD_WEBHOOK_WUMPUSCENTRAL` secret and append `"WUMPUSCENTRAL"` to `WEBHOOK_LABELS` in `src/modules/notifiers/discord.py`.

## Data Format

`state.json` contains all scraped data with top-level keys per source:

- **Article sources** (`support`, `support-dev`, `support-apps`, `creator-support`): arrays of article objects from the Zendesk API. The `body` field is replaced with a SHA-256 hash of the HTML content; the full HTML lives in `data/{source}/{id}.md`.
- **`blog`**: array of post objects from the RSS feed, containing `title`, `link`, `summary`, `published`, and `media_thumbnail_url`.

## Roadmap

- [ ] Add blog posts scraping as `.md` files (currently only stored in `state.json`)
- [ ] Add newsroom posts scraping as `.md` files (currently only stored in `state.json`)
- [ ] Build good looking embeds for webhooks
- [ ] Add `WUMPUSCENTRAL` Discord webhook for the official server
- [ ] Centralized API notifier for reporting changes to Wumpus Central services
- [ ] Implement diff-based commit messages (new/updated/removed counts)
