# Indie Dance Calibration - 2026-06-28

The user manually corrected a batch of `Indie Dance` tracks that were previously
mostly `Green`. These edits should be treated as taste calibration data.

## Observed Distribution After Manual Edits

- Total metadata `Indie Dance`: 359 tracks.
- Color distribution after edits:
  - Green: 328
  - Orange: 20
  - Red: 6
  - Blue: 2
  - Aqua: 1
  - Purple: 1
  - Yellow: 1
- Ratings are still mostly `3`, so color changes do not imply a broad energy
  increase.

## Lessons

- `Indie Dance` should not default to `Green` anymore.
- `Orange` is valid for atmospheric/instrumental Indie Dance, but usually as
  `rating 3 / JOURNEY`, not automatic `MAIN`.
- `Red` is valid for darker, acid, techno, bass, or faster Indie Dance cases.
- `Aqua` or `Blue` can be valid when the track leans toward breaks, acid, or
  deep/broken phrasing.
- `Yellow` can appear for special/classic-feeling material.

## Examples From The Manual Pass

| Track | User Signal |
| --- | --- |
| Time Modem - Werkzeuge Eines Fernen Willens (Adana Twins 2021 Edit) | Orange, rating 3, JOURNEY, Atmospheric/Instrumental |
| Tomy Wahl - Juno | Orange, rating 3, JOURNEY, Atmospheric/Instrumental |
| Whitesquare - Visual Distortion of Reality | Orange, rating 3, JOURNEY, Atmospheric/Instrumental |
| Trikk, Jimi Jules - Absolute Body Control | Red, rating 4, MAIN TIME, Driving/Instrumental |
| Vakabular - BRAAH | Red, rating 3, JOURNEY, Atmospheric/Instrumental |
| JORD, Dansyn - The Future | Red, rating 3, PEAK, Dark/Driving/Hypnotic, Bass/Techno-related tags |
| Yuzza - Pray (Rami Chami Remix) | Blue, rating 3, JOURNEY, Acid/Breaks/Atmospheric |
| AIKON, Kyozo - Dark Horse (Original Breaks Edition) | Aqua, rating 3, JOURNEY, Breaks/Dark |

## Implementation Notes

- Removed the broad `Indie Dance -> rating +1 -> MAIN` behavior.
- Baseline Indie Dance now leans `JOURNEY`.
- Baseline color can be Orange for atmospheric/instrumental Indie Dance.
- Red requires dark/driving/high-BPM signals.

