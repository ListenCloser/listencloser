# Transcription Bakeoff — Scored Solo-Piano Decision

**Status: DECISION MADE — PRODUCTION PIANO ENGINE = TRANSKUN**

Supersedes the earlier diagnostic-only blocked state before scored solo-piano ground truth was available.
Scored solo-piano ground truth (MAESTRO v3.0.0 test split, 15 clips) is now
available and the three candidate engines were evaluated on those exact clips.

---

## 1. Scored solo-piano acquisition (MAESTRO, n=15)

The solo-piano benchmark that was previously blocked is now prepared:

- **Source:** MAESTRO v3.0.0 `test` split, 15 clips across 13+ composers
  (Chopin, Rachmaninoff, Scriabin, Scarlatti, Liszt, Bach, Haydn, Mozart,
  Debussy, Beethoven, Schubert, Schumann, Wagner/Liszt).
- **Audio acquisition:** bounded HTTP range extraction from the remote 101 GB
  `maestro-v3.0.0.zip` (ZIP64). Only the target WAVs' byte ranges are fetched —
  the full archive is never downloaded. Central directory parsed once, members
  streamed per clip. See `evaluation/datasets/_remote_zip.py`.
- **Adapter:** `MaestroAdapter.resolve()` now acquires audio automatically via
  range extraction instead of requiring manual placement
  (`evaluation/datasets/maestro.py`).
- **Excerpts:** 25 s windows per clip, sliced from audio + aligned reference
  MIDI into `evaluation/.cache/prepared/real_world_v1/`.
- **Note counts** (reference): 70–399 per excerpt (median ~243), all `solo_piano`.

`prepare` is idempotent; re-runs skip already-prepared clips.

## 2. Results (note F1, onset F1, macro over 15 scored clips)

| engine | macro note F1 | macro onset F1 | avg runtime |
|--------|--------------:|---------------:|------------:|
| basic_pitch | 0.1083 | 0.7112 | 1.1s |
| transkun | **0.8034** | **0.9848** | 9.1s |
| piano_transcription | 0.4014 | 0.9687 | 12.6s |

Per-clip detail: `evaluation/reports/solo_piano/solo_piano_bakeoff.md`.

### Per-clip note F1

| clip | basic_pitch | transkun | piano_transcription |
|------|------------:|---------:|--------------------:|
| maestro_test_01 | 0.029 | **0.877** | 0.160 |
| maestro_test_02 | 0.031 | **0.932** | 0.684 |
| maestro_test_03 | 0.094 | **0.916** | 0.738 |
| maestro_test_04 | 0.086 | **0.482** | 0.065 |
| maestro_test_05 | 0.097 | **0.922** | 0.399 |
| maestro_test_06 | 0.062 | **0.852** | 0.155 |
| maestro_test_07 | 0.042 | **0.642** | 0.041 |
| maestro_test_08 | 0.044 | **0.550** | 0.060 |
| maestro_test_09 | 0.172 | **0.662** | 0.128 |
| maestro_test_10 | 0.117 | **0.814** | 0.223 |
| maestro_test_11 | 0.275 | **0.993** | 0.945 |
| maestro_test_12 | 0.366 | **0.950** | 0.807 |
| maestro_test_13 | 0.117 | **0.938** | 0.769 |
| maestro_test_14 | 0.025 | **0.561** | 0.000 |
| maestro_test_15 | 0.067 | **0.960** | 0.848 |

Transkun wins every single clip on note F1.

## 3. Analysis

- **transkun dominates:** note F1 = 0.8034 vs 0.4014 (piano_transcription) and
  0.1083 (basic_pitch). It wins on all 15/15 clips. Onset F1 is also highest
  (0.9848). Its weaknesses are the fast/dense excerpts (maestro_test_04,
  _07, _08: note F1 0.48–0.64) but it still leads those clips.
- **basic_pitch under-segments:** note F1 collapses on real piano (0.1083)
  despite decent onset F1 (0.7112). Its frame-based onsets match but its note
  grouping/offsets do not align with piano ground truth. This confirms the
  earlier qualitative observation that Basic Pitch is not a piano-specialist
  engine and should not be the piano production engine.
- **piano_transcription offsets:** onset F1 is high (0.9687) but note F1 is
  dragged down by offset/segmentation mismatches (e.g. maestro_test_14 note
  F1 = 0.000, maestro_test_01 = 0.160). It trails transkun on 15/15 clips.

## 4. Current product consequence

The later production-faithful held-out validation in #609/#512 confirmed the
same bounded conclusion through the exact product profiles.

1. Keep the explicit `solo_piano → Transkun 2.0.1` route.
2. Keep Basic Pitch for generic `auto` / non-piano material; this result does
   not justify applying piano assumptions to mixed audio.
3. Do not rerun the BabySlakh full-mix comparison to choose a piano engine —
   those clips are not piano material.
4. Reopen engine comparison only for a materially different model/domain
   hypothesis; current #512 work is product routing/UX and evidence-backed
   cleanup ablation, not another generic piano bakeoff.