# Taste Calibration - 2026-06-30

This note records the broader manual edits made on 2026-06-30. These edits are
separate from the date-added synchronization task.

## Summary

Tracks updated on 2026-06-30 show that the user's taste model is more nuanced
than genre-to-color mapping:

- 33 tracks were updated today.
- Colors used: Purple, Blue, Aqua, Red, Orange, Green, Pink, Yellow.
- Ratings are mostly 2-3, with selected 4s and very few 5s.
- The strongest signals are set function and mood tags, not metadata genre.

## Lessons

### Breaks

- Fast acid/driving/hypnotic Breaks can be Orange and MAIN TIME.
- Vocal/atmospheric Breaks can be Blue/JOURNEY.
- Deep or lower-BPM Breaks can stay Aqua/WARM or Aqua/JOURNEY.
- Therefore: BPM alone is not enough; acid, driving, vocal, and deep tags matter.

Examples:

- Perfect Kombo - Revo: Orange, rating 4, MAIN TIME, Acid/Driving/Hypnotic.
- Dylan Dylan - Do You Need Me?: Blue, rating 3, JOURNEY, Female Vocal/Atmospheric.
- Pete K - Belong: Aqua, rating 2, WARM UP, Deep/Female Vocal.
- Maze 28 - The Way: Aqua, rating 2, JOURNEY.

### Drum & Bass

- Drum & Bass is not automatic Red.
- Vocal/emotional DnB can be Pink and MAIN TIME.
- Deep/atmospheric/vocal DnB can be Aqua and WARM/JOURNEY.
- Dark/driving DnB can be Purple/MAIN TIME.

Examples:

- Karen Harding, Dimension - Guardian Angel: Pink, rating 3, MAIN TIME.
- Wilkinson, Mougleta - Eternity: Pink, rating 3, MAIN TIME/PEAK.
- Rafau Etamski - So Sweet: Aqua, rating 2, WARM UP.
- Aydn, ES.Kay - Through the Dark: Aqua, rating 2, JOURNEY.
- A-Cray - Keep Hiding: Purple, MAIN TIME, Acid/Dark/Driving.

### Progressive House

- Purple is a major journey/energy lane for Progressive House.
- Blue means deep/warm.
- Green can appear for organic/hypnotic journey material.
- Purple can carry peak/main-time flavor without forcing Red.

Examples:

- Kasper Koman - Biome: Purple, rating 4, dark/hypnotic/progressive with peak flavor.
- Plecta, Rossie - Matala: Purple, rating 4, MAIN TIME/PEAK, Acid/Driving/Hypnotic.
- Nick Muir, John Digweed, Franky Wah - Tripchain: Blue, rating 2, WARM UP.
- Guy J - Against the Wall: Green, rating 2, hypnotic journey.

### Melodic Techno / Melodic House & Techno

- Dark/driving Drumcode/Massano-style melodic material can be Red/PEAK.
- PIAS/Marsh/vocal/deep melodic material can be Blue or Aqua.
- Rating can be 2-3 even when the track has PEAK or Journey tags.

Examples:

- Adam Beyer, Bart Skils, Massano, Doriann - Your Mind: Red, rating 3, PEAK.
- Ae:ther - N59: Red, rating 3, PEAK/OPEN INTRO tags.
- Marsh - Mercy: Aqua, rating 2, WARM UP.
- Tinlicker - I Want My Freedom: Blue, rating 3, Female Vocal/Emotional.

### House / Deep House / Club Vocal

- House and Deep House can be Yellow when they read as classic, piano, vocal, or
  main-time club material.
- Do not collapse these into generic Dance / Pop.

Examples:

- Trilucid - See Through You: Yellow, rating 3, MAIN TIME, Piano/Female Vocal.
- Dusky - Next Life: Yellow, rating 3, Driving/Emotional/Female Vocal.

## Implementation Notes

- Added broader 2026-06-30 examples to `agent_rules.json`.
- Reduced automatic Red/PEAK bias for Drum & Bass in the baseline classifier.
- Added mood-based DnB color handling:
  - Emotional/Vocal -> Pink
  - Deep/Atmospheric -> Aqua
  - otherwise -> Purple

