# Taste Calibration - 2026-06-28 Batch

This note records the first manual correction pass where the user's rekordbox
edits were compared against the agent dry-run report
`reports/set_agent_report_20260628_215404.json`.

## Main Lessons

- The agent was too genre-driven. Local library taste and manual corrections
  must be stronger than Beatport/iTunes/Discogs metadata.
- `Melodic House & Techno` must not automatically become `PEAK / Red`.
  Deep melodic remixes can be warm, aqua/blue/purple, and rating 2-3.
- Low/mid BPM `Breaks` around 122 BPM should usually stay `Aqua` and rating 2,
  not `Orange / MAIN`.
- `Progressive House` is often a journey lane. Purple is often better than Blue
  for atmospheric/driving progressive material.
- `Organic House` is not always `OPEN` or rating 1. It may become
  `Organic / Downtempo`, `Electronica`, or `Progressive House` depending on the
  track's function.
- `House`, `Tech House`, and classic vocal club remixes need special handling.
  Do not fall back to `Dance / Pop` just because web metadata says pop.
- Priority tags are not stable yet and should not drive learning.

## Manual Examples

| Track | Agent | User Correction |
| --- | --- | --- |
| Chris Lake, The Chemical Brothers - Galvanize | Dance / Pop, rating 3, Purple, JOURNEY | Techno, rating 4, Yellow, MAIN TIME, Driving/Vocal/Emotional |
| Audiojack, Kevin Knapp - This Frequency | Dance / Pop, rating 3, Purple, JOURNEY | House, rating 3, Yellow, PEAK, Vocal/Driving/Deep |
| Durante, Ezequiel Arias - Logical | Progressive House, rating 2, Blue, WARM | Progressive House, rating 4, Purple, PEAK, Atmospheric/Driving |
| Marc Romboy, Stephan Bodzin - Callisto (Ben Bohmer Remix) | Melodic Techno, rating 5, Red, PEAK | Melodic Techno, rating 2, Aqua, warm/deep/instrumental journey |
| JORD, Dansyn - The Future | Indie Dance, rating 4, Orange, MAIN | Bass House/Techno/Melodic Techno area, rating 3, Red, PEAK, Dark/Driving/Hypnotic |
| PROFF, Volen Sentir - Violet | Progressive House, rating 3, Blue, JOURNEY | Breaks, rating 2, Aqua, Atmospheric/Deep |
| Avoure, Chris Orell - Chasing Voices | Breaks, rating 4, Orange, MAIN | Breaks, rating 2, Aqua, open/warm, Atmospheric/Deep/Emotional |

## Implementation Changes

- Added `taste_profile` and `manual_examples` to `agent_rules.json`.
- Added `Tech House` and `House` as normalized tags before `Dance / Pop`.
- Reduced automatic peak bias for `Melodic Techno`.
- Reduced automatic main-time bias for low/mid BPM `Breaks`.
- Updated Codex/LLM review instructions to treat manual examples and local taste
  as high-priority calibration data.

