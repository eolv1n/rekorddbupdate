# Taste calibration: 2026-09-17

## Scope

- Audited every audio file created in `E:\Music\My Library` since 2026-09-01.
- Found 22 files: 10 were already complete and 12 were new to rekordbox.
- Imported all 12 new tracks, added them to `пул`, and preserved the 10 existing decisions.
- Final pool size after import: 89 tracks.
- Verified that every one of the 22 files is in the database and pool with Rating, Color, and Situation MyTag.

## Reviewed decisions

- Khen - Babylon (Volen Sentir Remix): Purple, rating 3, JOURNEY, Progressive House.
- Juan Deminicis, Casnik - Inner Glow: Blue, rating 2, WARM, Progressive House.
- Bob Sinclar, Steve Edwards, Vintage Culture, Dubdogz - World Hold On: Blue, rating 3, JOURNEY, Melodic Techno + House.
- M.O.S. - Falling: Purple, rating 3, JOURNEY, Progressive House.
- Hot Since 82, Lydia Kaye - Another Life: Aqua, rating 3, JOURNEY, Breaks + House.
- Nicolas Rada - Entropy: Purple, rating 3, JOURNEY, Progressive House.
- Hessian, Courtney Storm - Heartbeat (Estiva Remix): Blue, rating 3, JOURNEY, Progressive House.
- Rezident, Romain Garcia - Ghost In Paris: Blue, rating 2, WARM, Melodic Techno.
- Supacooks - Floating Around (Paul AR Remix): Purple, rating 3, JOURNEY, Progressive House.
- Klur - Roots (il:lo Remix): Blue, rating 3, JOURNEY, Progressive House.
- Tribal Saints - Perfect Love (Framewerk Full-On Vocal Remix): Aqua, rating 2, JOURNEY, Breaks.
- Avoure - XXI: Aqua, rating 1, OPEN / INTRO, Electronica.

## Learned patterns

- Do not make atmospheric Progressive House Blue by default. Established artist neighbors remain strong evidence for Purple when the track is still a classic progressive journey.
- Supacooks, M.O.S., Khen, Juan Deminicis, and Nicolas Rada generally anchor the Purple progressive lane unless track-level deep or vocal evidence says otherwise.
- A verified emotional vocal can justify Blue even for an artist with many Purple neighbors, as with the Estiva remix of Heartbeat.
- Breaks intensity is independent from its broken rhythm. Another Life belongs at rating 3 / JOURNEY, while the Tribal Saints remix remains rating 2 / JOURNEY.
- Low-energy Electronica and ambient-adjacent opening material can be Aqua rather than generic Blue.
- Credited and verified vocalists should survive as Vocal/Female Vocal component tags.

## Agent changes

- Codex web search now uses the current CLI argument order.
- Agent decisions preserve one to three genre MyTags and up to six component MyTags.
- Internal roles map to existing rekordbox names such as `OPEN / INTRO`, `WARM UP`, and `MAIN TIME`.
- Priority A/B/C remains experimental and is not written unless explicitly enabled.
- Completed fresh tracks are excluded from later candidate runs, preventing repeated classification.
