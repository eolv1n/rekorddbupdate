# Taste Calibration - 2026-09-01

This pass compares the agent-applied fresh-track classifications with the
user's immediate listening corrections. The baseline is the database backup
created after import and before playlist `102` was rebuilt. Five tracks changed.

## Main Lessons

- Track-level rhythm overrides artist, label, and release-genre priors.
- Color remains independent from Rating and Set Role.
- Multiple genre MyTags are valid for real crossover tracks.
- A dub or remix suffix is not evidence that a track is instrumental.
- Metadata Genre and normalized genre MyTags are separate decisions. The user
  corrected two metadata genres after listening; those corrections are not an
  error in the tag-writing mechanism.

## Manual Corrections

| Track | Agent | User correction |
| --- | --- | --- |
| My Friend, Darla Jade - Flash (Jesabel Extended Remix) | Red; Trance | Blue; Trance + Progressive House; rating 4 MAIN TIME unchanged |
| Boxer - Verde (Jerome Isma-Ae Extended Remix) | Purple; Instrumental | Blue; Vocal; rating 3 JOURNEY unchanged |
| Tribal Saints - Perfect Love (Framewerk Dub Remix) | metadata House; Purple; generic Vocal | metadata Breaks; Aqua; Female Vocal; rating 2 JOURNEY unchanged |
| Glowal - Believe In Your Body | Red; Melodic Techno | Orange; Melodic Techno + Indie Dance; added Piano; rating 3 MAIN TIME unchanged |
| Massane - Shadows | metadata Progressive House; Purple; rating 3; Instrumental/Emotional | metadata Breaks; Aqua; rating 1; Breaks/Female Vocal; JOURNEY unchanged |

## Agent Policy

Use these as track-level and feature-level examples, not broad artist
overrides. In particular, other Massane and Glowal tracks already demonstrate
different valid lanes in this library. For uncertain fresh tracks, the agent
should lower confidence and request review instead of applying an artist-wide
color or energy rule.

The Codex decision contract now supports `genre_tags` with one to three values.
`genre_normalized` remains the primary tag for backward compatibility, while
apply mode writes every returned genre tag as a real Rekordbox MyTag link.
