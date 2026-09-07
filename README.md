# Prospect Box Scores

Daily MLB and MiLB box-score lines for a fantasy prospect league, as a CLI and a
web app. Data comes from the public [MLB Stats API](https://statsapi.mlb.com)
(no key required); a GitHub Action refreshes it every morning and redeploys the
site.

## How it fits together

```
  browser (Pages)  ──PUT contents API──►  data/rosters.json  ──┐
        ▲                                                      │ push triggers
        │ fetch static JSON                                     ▼
  web/dist/api/*.json ◄── export ── data/milb.sqlite ◄── ingest ── statsapi.mlb.com
        ▲                                                      ▲
        └──────────────── GitHub Action (daily cron) ──────────┘
```

**Git is the write path for human-authored data. SQLite is the store for
machine-scraped data.**

Rosters live in `data/rosters.json`, so editing a roster is a commit — free
versioning, audit trail, and rollback, and no server needed to accept the write.
`data/milb.sqlite` accumulates scraped game logs and is written *only* by the
ingest process, so there is exactly one writer and no concurrency to manage.

## Quick start

```bash
uv sync --all-groups

uv run milb ingest      # fetch game logs into data/milb.sqlite  (~15s, 723 requests)
uv run milb export      # write static JSON into web/public/api/
uv run milb 7           # render the last 7 days in the terminal

cd web && npm install && npm run dev
```

## CLI

Every flag from the original single-file script still works.

```bash
milb 7                        # last 7 days (default)
milb 3 --team Zebras          # one fantasy roster
milb 7 --format csv --out lines.csv
milb 7 --format json --out lines.json
milb 7 --plain                # no colour
milb --season 2025 30         # a past season
milb --lookup "Ethan Salas"   # find a personId by name
milb --lookup-id 829045       # confirm a personId is the right player
```

Subcommands separate fetching from rendering, which is what lets the Action
refresh data without rendering anything:

| Command | Does |
|---|---|
| `milb ingest` | Resolve rosters, fetch game logs, upsert into SQLite |
| `milb export` | Turn SQLite into the static JSON the web app reads |
| `milb report` | Render a report (the default when no subcommand is given) |
| `milb migrate-cache` | Seed SQLite from a legacy `milb_cache.json` |

## Managing rosters

Either edit `data/rosters.json` directly and push, or use the web app's **Admin**
page, which commits the same file for you.

The Admin page needs a
[fine-grained personal access token](https://github.com/settings/personal-access-tokens/new)
scoped to **only this repository** with **Contents: read and write**. It is kept
in your browser's localStorage, never committed, and revocable at any time.
Visitors without a token get a read-only site.

`person_id` is a first-class field on each roster entry. Once a player is
resolved the id is written back, so the name lookup never runs for them again.
When resolution does fail, the Admin page's search-and-pin flow replaces the old
`--lookup` → edit-the-source → commit loop.

## Scouting reports

Grades and notes live in `data/scouting.json`, written through the same
commit-as-save path as rosters. Edit them from a player's page (not the roster
admin) so the stat line that motivated a grade is on screen while you write it.

Reports are keyed by MLBAM `person_id`, not roster name, so they follow the real
player through fantasy trades and roster churn.

- **Tools** use the standard 20-80 scale, where 50 is major-league average and
  10 points is about a standard deviation. Each tool takes an optional present
  grade alongside the future one -- the `45/55` a real report would show, since
  for a prospect the gap between the two is most of the information.
- **FV** (Future Value) is the headline number, rendered with its plain-language
  equivalent (55 = above-average regular, 60 = All-Star, and so on).
- **Risk** and **ETA** qualify the FV.
- **Notes** are a dated log rather than one overwritten field, so you can see how
  your read on a player moved over a season.

Hitters and pitchers get different tool sets (`hit/game power/raw power/run/
field/arm` versus `fastball/slider/curveball/changeup/command`), chosen from the
player's roster position.

## Deploying

1. Make the repo public (GitHub Pages needs this on the free plan).
2. **Settings → Pages → Source: GitHub Actions.**
3. Push. `.github/workflows/update.yml` handles the rest.

It runs daily at 11:00 UTC, on any push that touches rosters or code, on
`workflow_dispatch`, and on the `refresh` repository dispatch that the Admin
page's "Refresh data now" button sends.

If the repo is not named `milb-boxscores`, update `base` in `web/vite.config.ts`
to match, or set `BASE_PATH` in the workflow.

## Data model

`game_log` is keyed on `(person_id, game_pk, group_type)`. Keying on date would
collapse doubleheaders — that bug cost 193 games in the 2026 season alone.

Every stat the API returns is preserved in `game_log.raw_stat`, well beyond the
columns the UI currently shows (`avg`/`obp`/`slg`/`ops`/`babip`, batted-ball
splits, pitch counts). Adding an advanced stat later is a migration plus a
backfill from data already on disk, not a re-scrape.

## Extending it

- **A new stat**: add a column in `db.py`, populate it in `derive.py`/`export.py`
  by backfilling from `raw_stat`, and render it in `web/src/`.
- **More scouting fields**: extend the schema in `src/milb/scouting.py`; it is
  validated on load, so a bad browser write fails the Action rather than landing
  silently.
- **Different highlight thresholds**: `web/src/lib/highlight.ts` and
  `src/milb/render.py` hold them, one place each.

## Tests

```bash
uv run pytest          # no network; API payloads are fixtures
cd web && npm run build
```
