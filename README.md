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

## Apply To rekordbox

Close rekordbox first, then run:

```powershell
python rekordbox_set_agent.py --days 30 --codex-review --apply
```

The script creates a backup before writing.

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

- Orange is the default main-time lane for `Indie Dance`, club-focused `Breaks`,
  and `Bass House`.
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

## Optional Environment Variables

- `DISCOGS_TOKEN` - enables Discogs lookup.
- `CODEX_MODEL` - overrides the Codex CLI model, default is `gpt-5.5`.
- `OPENAI_API_KEY` - enables the alternate OpenAI API review path when `--llm` is used.
- `OPENAI_MODEL` - model for `--llm`, default is `gpt-4.1-mini`.

## Safety Notes

- Never commit `master.db`, backups, reports, API keys, or exported library data.
- Run `--apply` only when rekordbox is closed.
- Review JSON/CSV reports before applying broad changes.
