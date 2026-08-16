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
├── python code/main.py --scrape    (OUTPUT_DIR=data, DIFF_FILE=./diff.json, MONITOR_FILE=./monitor.json)
│   ├── fetch Zendesk   → 3x retry per source (backoff 1s/2s/4s), in-memory articles
│   ├── fetch Blog      → 3x retry, RSS + content extraction for new/changed posts (append-only)
│   ├── health gate     → if ANY source failed → save ./monitor.json, raise SystemExit(1)
│   ├── archiver        → move removed .md to data/archive/{source}/, update archive/state.json (Zendesk only)
│   ├── write Zendesk   → data/{source}/{id}.md + hash bodies
│   ├── write Blog      → data/blog/{slug}.md + hash bodies (new/changed posts only, never deletes)
│   └── differ          → diff.json (full entry objects, NOT notified yet)
│
├── commit & push data/ → data branch    (skipped if scrape aborted)
│   └── capture COMMIT_SHA → $GITHUB_ENV
│
└── python code/main.py --notify --commit-sha $COMMIT_SHA    (if: always(), OUTPUT_DIR=data)
    ├── if ./monitor.json exists → send health-failure error embed (per-source status table + Actions run link), return
    ├── git diff --numstat HEAD~1 HEAD → line stats (in-memory)
    └── per-change Discord embeds (color-coded, Changes, commit URL field, 2s delay)
```

## Module Structure

```
main.py                     ScraperEngine entrypoint (argparse: --scrape / --notify)
modules/
  __init__.py
  core/
    __init__.py
    constants.py              Shared constants (ZENDESK_SOURCES, BLOG_SOURCE) + lookup_entry_by_id()
    log_setup.py              Loguru sink configuration (setup_logging())
    monitor.py                HealthMonitor — per-source status tracking + circuit breaker
  processors/
    __init__.py
    archiver.py               Archive removed articles: move .md to archive/, update archive/state.json (Zendesk only)
    differ.py                 Diff: git status (Zendesk) + state comparison (blog)
    line_stats.py             Build line stats dict from git diff --numstat (in-process)
  providers/
    __init__.py
    zendesk.py                Zendesk help-center API — fetch() + write() split (raises on total failure)
    blog.py                   Discord blog RSS + per-post content extraction → blog/{slug}.md (append-only, raises on fetch/parse failure)
  notifiers/
    __init__.py
    discord.py                Orchestrator: iterates diff, dispatches embeds + send_error() health embed, 2s delay
    embeds/
      __init__.py
      zendesk.py              create_zendesk_embed(action, entry, commit_url, source, line_stats)
      blog.py                 create_blog_embed(action, entry, commit_url, source, line_stats)
```

## How It Works

1. **Scrape Zendesk** — paginates through the help-center API for each source (`support`, `support-dev`, `support-apps`, `creator-support`), writes each article's HTML body to `data/{source}/{id}.md`, and stores metadata + a SHA-256 hash of the body in `state.json`. Each per-source fetch is wrapped in **3 retry attempts** with exponential backoff (`1s → 2s → 4s`) and honors the HTTP `429 Retry-After` header. A source that fails all attempts raises and is marked `FAILED` in the health monitor.
2. **Scrape Blog** — fetches the Discord blog RSS feed (same 3-attempt retry wrapper). For each post not yet in `state.json` (or whose title/summary/published/thumbnail changed), fetches the post page and extracts the article body from the `<article class="w-richtext">` element. The RSS window covers the ~100 latest posts (Webflow CMS cap); posts that fall out of the window are **kept forever** (append-only — the blog diff never reports removals). On failure, marked `FAILED` in the health monitor.
3. **Health gate (circuit breaker)** — after all sources are fetched, `HealthMonitor.is_healthy()` is checked. If **any** source is `FAILED`, the scrape is aborted **before** archiving, writing, or diffing: `monitor.json` is written to the workspace root and `SystemExit(1)` is raised. This prevents the false-deletion cascade that occurs when a transient API outage makes the archiver treat all articles as removed.
4. **Diff** — runs `git status --porcelain` in the `data` checkout to detect added (`??`), updated (` M`), and removed (` D`) Zendesk article files. Blog posts are diffed by comparing old vs new `state.json` entries by `link` (in-memory; the blog `removed` bucket is always empty because of the append-only policy). Each diff entry carries the **full object** from the new state (added/updated) or old state (removed), persisted to `diff.json`.
5. **Line stats** — runs `git diff --numstat HEAD~1 HEAD` in the `data` checkout to count added/removed lines per `.md` file. Computed in-process by the notify step (no intermediate file).
6. **Notify** — if `monitor.json` exists (aborted scrape), dispatches a single health-failure error embed to Discord listing every source's status (`OK`/`FAILED`), article count, attempts, and error message, with a clickable link to the Actions run. Otherwise loads `diff.json` and dispatches one Discord embed per change (green = added, yellow = updated, red = removed). Zendesk embeds show a 2×3 grid of inline fields (Source, Article ID, Changes, Created, Promoted, Commit) plus a full-width Labels field; the Changes field (`+N ~M -K`) comes from the in-process line stats. Blog embeds link the title to the post, include the summary as description and the thumbnail as image. Each embed carries a clickable "View commit" field linking to the data-branch commit that captured the change. A 2-second delay separates sends to respect webhook rate limits.

## Archiving

When Discord removes an article from Zendesk, the scraper preserves it instead of discarding it. Before each scrape overwrites the source directories, the **archiver** (`modules/processors/archiver.py`) identifies articles present in the previous `state.json` but missing from the fresh API response and:

- **Moves** `data/{source}/{id}.md` → `data/archive/{source}/{id}.md` (preserving the last-known HTML body).
- **Appends** the article's entry (metadata + body hash) to `data/archive/state.json` under the matching source key.

If Discord later re-publishes an archived article, the archive copy is **removed** and fresh content lives at `data/{source}/{id}.md` again — the archive keeps only the most recent removed snapshot, not historical versions.

**Blog posts are exempt from archiving.** The RSS feed only exposes the ~100 latest posts (Webflow CMS cap), so falling out of the RSS window does not mean a post was deleted. Blog posts are append-only: once tracked, they stay in `state.json` and `data/blog/{slug}.md` forever. Existing `archive/state.json["blog"]` entries from before this policy are left untouched.

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

1. **Scrape** — runs `python code/main.py --scrape` with `OUTPUT_DIR=data`, `DIFF_FILE=./diff.json`, and `MONITOR_FILE=./monitor.json`. Fetches all sources (3 retries each), runs the health gate, then — if healthy — writes `state.json` + `.md` files into the `data` checkout, computes the diff, and persists it to `diff.json` in the workspace root (outside `data/`, so it is not committed). If any source failed, writes `monitor.json` and aborts with a non-zero exit before touching data.
2. **Commit & Push** — runs `if: success()` only. Commits changes in `data/` as `github-actions[bot]` and pushes to the `data` branch. On success, captures the commit SHA into `$GITHUB_ENV` as `COMMIT_SHA`. Skipped automatically when the scrape aborted (non-zero exit). Also skipped if there are no changes.
3. **Notify** — runs `if: always()` (so it fires even after a failed scrape). Invokes `python code/main.py --notify --commit-sha $COMMIT_SHA` (commit-sha omitted when no commit was produced). If `monitor.json` exists, dispatches a health-failure error embed (per-source status table + link to the Actions run) and returns; otherwise loads `diff.json` and dispatches per-change Discord embeds with a link to the commit.

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
| `OUTPUT_DIR` | `.` | both | Directory where `state.json` and per-source `.md` files are written (scrape) / where `git diff --numstat` runs (notify) |
| `DIFF_FILE` | `./diff.json` | both | Path to `diff.json` (written by `--scrape`, read by `--notify`) |
| `MONITOR_FILE` | `./monitor.json` | both | Path to `monitor.json` (written by `--scrape` on abort, read by `--notify` to send error embed). Lives outside `data/`, never committed. |
| `ACTIONS_RUN_URL` | — | notify | Optional URL to the GitHub Actions run; embedded as a clickable "View run logs" field in health-failure error embeds. Set automatically by the workflow. |
| `DISCORD_WEBHOOK_UNI` | — | notify | Discord webhook URL for the UNI server |

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DISCORD_WEBHOOK_UNI` | Discord webhook URL for the UNI server |

To add the official Wumpus Central server in the future, I will add a `DISCORD_WEBHOOK_WUMPUSCENTRAL` secret and append `"WUMPUSCENTRAL"` to `WEBHOOK_LABELS` in `modules/notifiers/discord.py`.

## Data Format

`state.json` contains all scraped data with top-level keys per source:

- **Article sources** (`support`, `support-dev`, `support-apps`, `creator-support`): arrays of article objects from the Zendesk API. The `body` field is replaced with a SHA-256 hash of the HTML content; the full HTML lives in `data/{source}/{id}.md`.
- **`blog`**: array of post objects built from the RSS feed + per-post page content, containing `title`, `link`, `summary`, `published`, `media_thumbnail_url`, and a `body` SHA-256 hash. The full HTML lives in `data/blog/{slug}.md`. Append-only: posts are never removed, even when they fall out of the RSS window.

`diff.json` is written by `--scrape` and read by `--notify`. It mirrors the diff structure with top-level keys per source, each containing `added`, `updated`, and `removed` buckets. Every entry maps its key (article `id` for Zendesk, post `link` for blog) to the **full object** captured at diff time — added/updated entries come from the new state, removed entries from the old state.

## Roadmap

- [x] Build good looking embeds for webhooks
- [x] Rich Zendesk embeds (url, labels, created, promoted, thumbnail)
- [x] Archive removed articles to `data/archive/` (Zendesk only; blog is append-only)
- [x] Blog posts scraped as `.md` files with per-post content extraction
- [ ] Add newsroom posts scraping as `.md` files
- [ ] Add `WUMPUSCENTRAL` Discord webhook for the official server
- [ ] Centralized API notifier for reporting changes to Wumpus Central services
- [ ] Implement diff-based commit messages (new/updated/removed counts)
