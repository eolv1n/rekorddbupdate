# rekordbox-set-agent

Agentic classification tools for a rekordbox library.

The goal is not to fill tags mechanically. The agent classifies the role of each
track in a DJ set: energy, set role, vibe, color, priority, and nearby reference
tracks from the existing library.

## What It Does

- Reads a local rekordbox `master.db`.
- Detects fresh or unclassified tracks.
- Collects web evidence from MusicBrainz and iTunes.
- Optionally uses Discogs when `DISCOGS_TOKEN` is set.
- Optionally calls local Codex CLI as a reasoning reviewer.
- Produces JSON/CSV dry-run reports.
- Can apply safe fields back to rekordbox:
  - `Rating`
  - `Color`
  - MyTag `Genre`
  - MyTag `Situation`
  - MyTag `Components`
  - MyTag `Priority`

By default, it does not overwrite title, artist, label, year, or the metadata
genre field.

## Files

- `rekordbox_set_agent.py` - agentic pipeline with web evidence and optional Codex review.
- `rekordbox_fresh_track_agent.py` - simpler rule-based baseline.
- `excel_verified_update.py` - verified Excel-table updater used for bulk Rating/Color/MyTag updates.
- `agent_rules.json` - editable library rules.
- `codex_track_decision.schema.json` - strict schema for Codex review output.
- `examples/rekordbox_update_template.xlsx` - safe example workbook.

## Setup

Install dependencies into your Python environment:

```powershell
pip install -r requirements.txt
```

The scripts expect access to the local rekordbox database:

```text
C:\Users\Admin\AppData\Roaming\Pioneer\rekordbox\master.db
```

## Reproducible Environment

The project has two supported runtime paths: a normal Windows virtual
environment and an optional Docker environment. Use the Windows venv for direct
rekordbox work on the host. Use Docker when you want a reproducible dependency
set and do not want to depend on whatever `python` happens to mean in the
current PowerShell session.

### Windows venv

Create `.env`, create `.venv`, and install dependencies:

```powershell
.\scripts\setup_windows.ps1
```

Run a dry-run through the pinned venv Python:

```powershell
.\scripts\run_agent.ps1 -Days 1 -Limit 20
```

Run a manually reviewed small batch:

```powershell
.\scripts\run_agent.ps1 -Days 1 -Limit 15 -Apply -ForceApply
```

The scripts read `REKORDBOX_DB_PATH` from `.env`. Copy `.env.example` to `.env`
and edit paths/tokens there. `.env` is ignored by git.

### Docker

Build the image:

```powershell
docker compose build
```

Run a dry-run:

```powershell
docker compose run --rm agent
```

Run custom arguments:

```powershell
docker compose run --rm agent --db /rekordbox-db/master.db --days 1 --limit 20 --no-web
```

By default, `docker-compose.yml` mounts the rekordbox directory from
`REKORDBOX_DB_DIR` into `/rekordbox-db`. On Windows this should point to the
folder containing `master.db`, for example:

```text
REKORDBOX_DB_DIR=C:\Users\Admin\AppData\Roaming\Pioneer\rekordbox
```

Forward slashes are also valid on Windows and are safer in `.env` files:

```text
REKORDBOX_DB_DIR=C:/Users/Admin/AppData/Roaming/Pioneer/rekordbox
```

Close rekordbox before any Docker or Windows venv `--apply` run.

## Dry Run

Create a review report for recent tracks:

```powershell
python rekordbox_set_agent.py --days 30 --limit 20
```

Reports are written to `reports/` inside the project.

Use Codex CLI as a reasoning reviewer:

```powershell
python rekordbox_set_agent.py --days 30 --limit 20 --codex-review
```

Let Codex use web search too:

```powershell
python rekordbox_set_agent.py --days 30 --limit 20 --codex-review --codex-search
```

## Discogs API

Discogs is optional but useful for release-level metadata: year, label, country,
genre, style, master release, and remix/version context.

For a personal local workflow, use a Discogs personal access token:

1. Open `https://www.discogs.com/settings/developers`.
2. Generate a personal access token.
3. Put it in local `.env`:

```env
DISCOGS_TOKEN=your_token_here
```

The token is read from the environment and must never be committed. `.env` is
ignored by git.

The agent queries Discogs in two steps:

- search `/database/search` for likely releases;
- fetch `/releases/{id}` for fuller metadata.

Discogs matches are filtered by artist/title token overlap before they are used.
This prevents unrelated first search results from polluting genre normalization.
Discogs should support metadata and context; it should not be the final authority
for `Rating`, `Color`, or set dramaturgy.

## Apply To rekordbox

Close rekordbox first, then run:

```powershell
python rekordbox_set_agent.py --days 30 --codex-review --apply
```

For a small manually reviewed batch, bypass the confidence gate:

```powershell
python rekordbox_set_agent.py --days 1 --limit 15 --apply --force-apply
```

The apply summary reports how many rows were actually written and how many were
skipped by the confidence threshold.

The script creates a backup before writing.

## Sync Date Added From File

`sync_date_added_from_file.py` synchronizes rekordbox `DateCreated` from the
file creation date on disk (`FolderPath`). It does not change the internal
database `created_at` timestamp. `StockDate` is also left unchanged by default
because many tracks have harmless one-day `StockDate` differences.

Dry-run:

```powershell
python sync_date_added_from_file.py
```

Apply after closing rekordbox:

```powershell
python sync_date_added_from_file.py --apply
```

The script creates a backup before writing. Use `--include-stock` only if you
explicitly want to synchronize `StockDate` too.

## Verified Excel Update Flow

This is the saved version of the Excel workflow used to update the library from
a workbook with fields like `Rating`, `Color`, `Genre_Normalized`,
`Energy_Label`, `Elements`, and `Mood`.

Example table:

```text
examples/rekordbox_update_template.xlsx
```

Supported columns:

| Column | Meaning |
| --- | --- |
| `Artist` / `Исполнитель` | Match track artist |
| `Title` / `Название дорожки` | Match track title |
| `Rating` / `Рейтинг` | rekordbox star rating, accepts `****` or `4` |
| `Color` | rekordbox color name |
| `Genre_Normalized` | MyTag under `Genre`, not metadata Genre |
| `Energy_Label` / `Set Role` | MyTag under `Situation` |
| `Elements` | MyTag(s) under `Components` |
| `Mood` | MyTag(s) under `Components` |

Dry-run:

```powershell
python excel_verified_update.py examples\rekordbox_update_template.xlsx
```

Apply to the real rekordbox database:

```powershell
python excel_verified_update.py path\to\your_table.xlsx --apply
```

This updater does not change the metadata `Genre` field.

## Current Color Logic

- Current color logic is experimental and must not be treated as final library
  truth.
- Orange is a candidate main-time lane for `Indie Dance`, club-focused `Breaks`,
  and `Bass House`, but it should not be applied broadly until enough local
  library examples are manually confirmed.
- `Future House` is kept separate from `Bass House` and may be classified as
  peak material.
- `Afro House` and `Organic House` are separate normalized genre tags.
- `Electronica`, `Ambient`, `Deep House`, and `Minimal` are explicit normalized
  genre tags instead of being folded into broad catch-all groups.
- Aqua is kept for more broken or leftfield breaks, not every Beatport `Breaks`
  track.
- Yellow is reserved for classics and should not be assigned to `Future House`
  just because the track reads brighter than techno.
- Metadata `Genre` is preserved. `Genre_Normalized` is written only as a MyTag
  until the normalized genre map is explicitly approved.
- `agent_rules.json` has a `library_calibration` section for user feedback such
  as artist/label-specific energy corrections.

## What We Learned From The First Live Run

The first real `--apply --force-apply` batch updated 14 recent tracks
successfully, but it also exposed an important design problem: the classifier was
still too rule-driven. It used the local library for similar-track suggestions
and confidence, but the final `Rating` and `Color` decisions were mostly driven
by explicit genre rules plus web evidence.

That is not enough for this library. The library already has a strong internal
language, and the agent must learn from it before writing broad changes.

Important observations:

- The existing database had almost no `Orange` usage before the test batch.
- Assigning `Orange` from genre alone is unsafe.
- `Indie Dance` in the current library is mostly `Green` with rating `3`.
- `Breaks / Breakbeat / UK Bass` is mostly `Aqua` with rating `3`.
- `Melodic House & Techno` is often not enough information to decide peak
  energy. For example, Boris Brejcha / FCKNG SERIOUS should not be automatic
  `Red / PEAK` in this library.
- Metadata `Genre` and MyTag `Genre_Normalized` are separate concepts and
  should remain separate until the normalized genre map is approved.

Near-term rule: do not auto-apply broad genre/color changes unless the decision
agrees with the local database prior or has been manually reviewed.

## Next Technical Steps

- Build a real database prior:
  - color distribution by metadata genre, normalized genre, artist, label, BPM,
    key, rating, and existing MyTags;
  - nearest-neighbor examples that actually influence `Rating`, `Color`, and
    `Set Role`;
  - conflict detection when rules disagree with the local prior.
- Change the classifier flow:
  - local DB prior first;
  - web evidence second;
  - hand-written rules as corrections, not the main source of truth;
  - Codex/LLM review only for disputed or low-confidence tracks.
- Add safer apply behavior:
  - never force broad updates by default;
  - require review when the suggested color is rare for that genre/artist/label;
  - report exact field changes before writing;
  - keep rollback backups for every write.
- Improve the feedback loop:
  - store user corrections as training examples;
  - update `agent_rules.json` only when a correction is reusable;
  - keep one-off track decisions separate from general rules.

## Future App Plan

A dedicated local app would be more useful than running scripts directly. The
app should act as a review and training interface for the agent.

Core screens:

- Fresh tracks from rekordbox.
- Current database values: metadata genre, rating, color, MyTags, label, BPM,
  key, and date added.
- Agent suggestions: normalized genre, energy/rating, set role, mood, color,
  priority, similar tracks, and explanation.
- Review actions: accept, edit, reject, defer.
- A conflict queue for cases where rules, web evidence, and DB prior disagree.
- A calibration view for artist/label-specific corrections.
- A rollback/backup view.

Table workflow inside the UI:

- Import selected tracks from rekordbox into an editable table.
- Let the user edit normalized genre, rating, color, set role, mood, priority,
  and notes in a spreadsheet-like grid.
- Export the reviewed table back through the verified Excel update workflow.
- Optionally export a normal `.xlsx` for manual editing outside the app.
- Re-import a reviewed `.xlsx` and preview exact database changes before apply.

Longer-term agent behavior:

- Learn from accepted/rejected suggestions.
- Prefer the user's historical library decisions over generic Beatport genres.
- Treat color as a library-specific signal, not a universal genre mapping.
- Use internet lookup for metadata and context, but not as the final authority
  for set dramaturgy.

## Optional Environment Variables

- `DISCOGS_TOKEN` - enables Discogs lookup.
- `CODEX_MODEL` - overrides the Codex CLI model, default is `gpt-5.5`.
- `OPENAI_API_KEY` - enables the alternate OpenAI API review path when `--llm` is used.
- `OPENAI_MODEL` - model for `--llm`, default is `gpt-4.1-mini`.

## Safety Notes

- Never commit `master.db`, backups, reports, API keys, or exported library data.
- Run `--apply` only when rekordbox is closed.
- Review JSON/CSV reports before applying broad changes.
