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
- `agent_rules.json` - editable library rules.
- `codex_track_decision.schema.json` - strict schema for Codex review output.

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

## Optional Environment Variables

- `DISCOGS_TOKEN` - enables Discogs lookup.
- `CODEX_MODEL` - overrides the Codex CLI model, default is `gpt-5.5`.
- `OPENAI_API_KEY` - enables the alternate OpenAI API review path when `--llm` is used.
- `OPENAI_MODEL` - model for `--llm`, default is `gpt-4.1-mini`.

## Safety Notes

- Never commit `master.db`, backups, reports, API keys, or exported library data.
- Run `--apply` only when rekordbox is closed.
- Review JSON/CSV reports before applying broad changes.
