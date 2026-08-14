# Transcription Bakeoff — Evaluation Follow-up

**Status: DIAGNOSTIC ONLY — NO PRODUCTION WINNER SELECTED**

This report validates the transcription bakeoff infrastructure and fixes the
piano_transcription zero-match bug. It deliberately does **not** select or
integrate a production transcription engine.

---

## 1. Zero-match root cause (fixed)

piano_transcription returned zero matches because the adapter fed 44.1 kHz
audio into a model trained at **16 kHz**.

- The model (`piano_transcription_inference`) is trained at `config.sample_rate
  = 16000`, `hop_size = 160` samples/frame, `frames_per_second = 100`,
  `fmax = 8000`.
- Feeding 44.1 kHz input time-stretches every onset/offset by
  `44100 / 16000 = 2.756x` (the post-processor assumes 100 frames/sec).
- Evidence on `babyslakh_01`: reference = 147 notes / 19.999s; buggy prediction
  = 763 notes / 59.719s; Basic Pitch (correct) = 187 notes / 19.865s.
- Prepared audio is native 16 kHz (320000 samples = 20.0s), so the stretch was
  purely an adapter bug.

**Fix:** `PianoTranscriptionAdapter.MODEL_SAMPLE_RATE = 16000`; `transcribe()`
now decodes at 16 kHz. Regression tests added:
`test_piano_transcription_model_sample_rate` and
`test_piano_transcription_output_time_aligned`.

**After fix** on `babyslakh_01`: 128 notes / 19.99s, onset F1 = 0.4945
(was 0.0044), note F1 = 0.160 (was 0.0). The model now produces *fewer* notes
than the reference (128 vs 147), not an excess — consistent with an alignment
fix rather than a threshold effect.

---

## 2. Full-mix transcription benchmark (BabySlakh, n=5)

**These results are NOT piano-transcription results.**

The 5 scored clips are BabySlakh `full_mix` excerpts: the audio is an
11-instrument mixture and the reference MIDI is the full mix with drums
excluded (10 non-drum instruments), **not** a solo-piano target. These numbers
measure how each engine behaves on dense polyphonic mixes.

### Per-clip

| clip | engine | onset P | onset R | onset F1 | note F1 | pred notes | ref notes | time (s) |
|------|--------|--------:|--------:|---------:|--------:|-----------:|----------:|---------:|
| babyslakh_01 | basic_pitch | 0.358 | 0.456 | 0.401 | 0.096 | 187 | 147 | 1.60 |
| babyslakh_02 | basic_pitch | 0.140 | 0.122 | 0.131 | 0.009 | 200 | 229 | 1.86 |
| babyslakh_03 | basic_pitch | 0.552 | 0.337 | 0.418 | 0.177 | 257 | 422 | 1.71 |
| babyslakh_04 | basic_pitch | 0.199 | 0.255 | 0.223 | 0.009 | 131 | 102 | 1.60 |
| babyslakh_05 | basic_pitch | 0.479 | 0.345 | 0.401 | 0.036 | 234 | 325 | 2.02 |
| babyslakh_01 | transkun | 0.714 | 0.374 | 0.491 | 0.143 | 77 | 147 | 7.18 |
| babyslakh_02 | transkun | 0.127 | 0.031 | 0.049 | 0.014 | 55 | 229 | 7.20 |
| babyslakh_03 | transkun | 0.806 | 0.474 | 0.597 | 0.307 | 248 | 422 | 7.40 |
| babyslakh_04 | transkun | 0.378 | 0.167 | 0.231 | 0.054 | 45 | 102 | 7.08 |
| babyslakh_05 | transkun | 0.862 | 0.443 | 0.585 | 0.398 | 167 | 325 | 6.80 |
| babyslakh_01 | piano_transcription | 0.531 | 0.463 | 0.494 | 0.160 | 128 | 147 | 12.03 |
| babyslakh_02 | piano_transcription | 0.407 | 0.162 | 0.231 | 0.056 | 91 | 229 | 10.81 |
| babyslakh_03 | piano_transcription | 0.659 | 0.595 | 0.625 | 0.257 | 381 | 422 | 9.55 |
| babyslakh_04 | piano_transcription | 0.318 | 0.069 | 0.113 | 0.048 | 22 | 102 | 9.19 |
| babyslakh_05 | piano_transcription | 0.540 | 0.394 | 0.456 | 0.192 | 237 | 325 | 9.44 |

### Aggregate (macro over 5 scored clips)

| engine | macro note F1 | macro precision | macro recall | scored / ineligible | avg runtime |
|--------|--------------:|----------------:|-------------:|--------------------:|------------:|
| basic_pitch | 0.0652 | 0.0759 | 0.0601 | 5 / 5 | 1.8s |
| transkun | 0.1835 | 0.2670 | 0.1405 | 5 / 5 | 7.1s |
| piano_transcription | 0.1427 | 0.1811 | 0.1257 | 5 / 5 | 10.2s |

Interpretation caveats:

- GuitarSet clips (5) are ineligible for transcription (no reference MIDI) and
  are correctly reported as `ineligible`, not as failures.
- On this full-mix set, transkun has the best macro note F1 (0.1835) and is
  faster than piano_transcription (7.1s vs 10.2s). Basic Pitch under-transcribes
  on mix (`babyslakh_02` note F1 = 0.009).
- **Do not use these numbers to choose between Basic Pitch and a
  piano-specialist engine** — the target is not piano.

---

## 3. Solo-piano quantitative benchmark — NOT AVAILABLE

**No solo-piano quantitative benchmark is currently available.** The true
solo_piano clips (MAESTRO 5, ASAP 5) are `status = manual`: their audio
requires manual acquisition (MAESTRO archive ~101 GB). Until scored
solo-piano ground truth exists:

- the production piano-engine decision is **blocked**;
- no piano production winner should be recommended.

---

## 4. Qualitative solo-piano diagnostic (real-piano.m4a)

Solo-piano qualitative evidence only — **no F1, no quantitative comparison**.
Kept separate so qualitative and quantitative evidence are never compared as
if they were the same metric.

All three engines run successfully on the solo-piano fixture (2/2 OK). The clips
are reported `ineligible` for transcription scoring (no reference MIDI) — this
is correct behavior, not a failure.

### Canonical artifacts — real-piano.m4a (54.5s solo piano)

Generated with identical synthesis/viz settings across engines (`.mid`,
rendered `.wav`, piano-roll `.png`). See `evaluation/results/qualitative_v2/
artifacts/real-piano/`.

| engine | notes | pitch range | notes ≥ MIDI 86 | short (<150ms) | max polyphony | runtime |
|--------|------:|------------:|----------------:|---------------:|--------------:|--------:|
| basic_pitch | 234 | 29–93 | 18 | 7 | 6 | 2.1s |
| transkun | 102 | 48–93 | 16 | 5 | 6 | 14.3s |
| piano_transcription | 188 | 31–93 | 25 | 13 | 16 | 31.9s |

Observations (visual/auditory inspection only — **no F1**):

- All three engines are time-aligned to the 54.5s fixture (pred spans
  54.2–59.6s), confirming the sample-rate fix holds on real solo-piano audio.
- basic_pitch emits the most notes (234); transkun the fewest (102) with a
  narrower pitch range (48–93).
- piano_transcription reports the most high notes (≥ MIDI 86) and highest
  polyphony (16), consistent with its chord/sustain modeling.
- These differences are diagnostic observations, **not** a comparison metric.

---

## 5. Beat-tracking benchmark (BabySlakh, n=5)

Same full-mix caveat as transcription: these 5 scored clips are `full_mix`, so
beat metrics measure tracking on dense mixes, not piano-specific behavior.

### Per-clip

| clip | engine | beat F1 | downbeat F1 | bpm abs err | time (s) |
|------|--------|--------:|------------:|------------:|---------:|
| babyslakh_01 | librosa | 0.2133 | — | 72.8 | 0.12 |
| babyslakh_02 | librosa | 0.3276 | — | 129.9 | 0.11 |
| babyslakh_03 | librosa | 0.3802 | — | 90.7 | 0.13 |
| babyslakh_04 | librosa | 0.3269 | — | 90.9 | 0.11 |
| babyslakh_05 | librosa | 0.2963 | — | 120.6 | 0.10 |
| babyslakh_01 | beat_this | 0.2308 | 0.1000 | 82.5 | 0.38 |
| babyslakh_02 | beat_this | 0.3590 | 0.0645 | 230.9 | 0.39 |
| babyslakh_03 | beat_this | 0.4531 | 0.3636 | 80.4 | 0.40 |
| babyslakh_04 | beat_this | 0.3238 | 0.1481 | 169.2 | 0.40 |
| babyslakh_05 | beat_this | 0.3091 | 0.1481 | 132.4 | 0.39 |

### Aggregate (macro over 5 scored clips)

| engine | macro beat F1 | scored / ineligible | avg runtime |
|--------|--------------:|--------------------:|------------:|
| librosa | 0.3089 | 5 / 5 | 0.12s |
| beat_this | 0.3352 | 5 / 5 | 0.39s |

Notes:

- Reference beats/BPM were derived from the BabySlakh reference MIDI
  (`estimate_tempo` + fixed grid), not from a human beat annotation — bpm
  absolute error is therefore noisy and not authoritative.
- beat_this supports downbeats (librosa does not) and edges out librosa on
  macro beat F1, but both are weak on full-mix material.
- GuitarSet clips are ineligible for beat scoring (no reference beats) and are
  reported `ineligible`, not failed.

### BeatNet classification

**INCOMPATIBLE on this environment.** `beat-this` and librosa are RUNNABLE.
BeatNet requires `madmom`, which has **no arm64 macOS wheel** and fails to
build from source (compile error `'longintrepr.h' file not found` — a known
madmom / Python 3.11 incompatibility). BeatNet is not scorable here.

---

## 6. Engine installability

| engine | status |
|--------|--------|
| basic_pitch | RUNNABLE (baseline, in production) |
| piano_transcription | RUNNABLE (CPU, checkpoint auto-download) |
| transkun | RUNNABLE (CPU; ~7s/clip; earlier 600s timeout was first-run checkpoint download, not steady-state) |
| librosa / beat_this / music21_symbolic | RUNNABLE |
| beatnet | INCOMPATIBLE (requires madmom; no arm64 wheel, source build fails) |

---

## 7. Pre-existing test failure note (test_beat_this.py)

`test_beat_this_not_installed_fails_at_runtime` fails **both on this branch and
on clean `main`** when `beat-this==1.1.0` is installed in the venv.

- The test asserts `engine.analyze()` raises `RuntimeError`/`ImportError`,
  which is only true when `beat_this` is **absent**.
- The bakeoff installed `beat-this==1.1.0` (it is not in `requirements.txt`),
  so `import beat_this` now succeeds.
- The production `BeatThisEngine` calls `beat_this.run(...)`, but the installed
  package exposes `run` under `beat_this.cli`, not at the top level — so the
  call raises `AttributeError`, which the test's exception tuple does not
  include.

This is an environment-sensitive test + a production-engine API drift, both
pre-existing and unrelated to the sample-rate fix in this PR. It is **not**
caused by the evaluation work; it surfaces because the bakeoff environment
installed the optional dependency.

---

## Recommendations

1. **Piano-engine decision: blocked** until scored solo-piano ground truth
   (MAESTRO/ASAP) is acquired.
2. Evaluate piano-specialist engines (piano_transcription, transkun) only on
   solo-piano reference material.
3. Re-run the full-mix table on a larger scored set before drawing any
   mix-transcription conclusions.