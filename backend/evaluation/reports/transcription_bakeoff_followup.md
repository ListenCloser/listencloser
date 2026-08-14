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
| babyslakh_01 | piano_transcription | 0.531 | 0.463 | 0.494 | 0.160 | 128 | 147 | 12.03 |
| babyslakh_02 | piano_transcription | 0.407 | 0.162 | 0.231 | 0.056 | 91 | 229 | 10.81 |
| babyslakh_03 | piano_transcription | 0.659 | 0.595 | 0.625 | 0.257 | 381 | 422 | 9.55 |
| babyslakh_04 | piano_transcription | 0.318 | 0.069 | 0.113 | 0.048 | 22 | 102 | 9.19 |
| babyslakh_05 | piano_transcription | 0.540 | 0.394 | 0.456 | 0.192 | 237 | 325 | 9.44 |

### Aggregate (macro over 5 scored clips)

| engine | macro note F1 | macro precision | macro recall | scored / ineligible | avg runtime |
|--------|--------------:|----------------:|-------------:|--------------------:|------------:|
| basic_pitch | 0.0652 | 0.0759 | 0.0601 | 5 / 5 | 1.8s |
| piano_transcription | 0.1427 | 0.1811 | 0.1257 | 5 / 5 | 10.2s |

Interpretation caveats:

- GuitarSet clips (5) are ineligible for transcription (no reference MIDI) and
  are correctly reported as `ineligible`, not as failures.
- Basic Pitch under-transcribes on mix (`babyslakh_02` note F1 = 0.009);
  piano_transcription is better but not decisively so, and it is ~6x slower.
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

Both engines run successfully on the solo-piano fixture (2/2 OK). The clips
are reported `ineligible` for transcription scoring (no reference MIDI) — this
is correct behavior, not a failure.

| engine | real-piano.m4a | piano-simple.m4a | runtime (real-piano) |
|--------|----------------|------------------|---------------------:|
| basic_pitch | OK | OK | 2.0s |
| piano_transcription | OK | OK | 13.6s |

Canonical artifacts (`.mid`, rendered `.wav`, piano-roll `.png`) for
real-piano.m4a are produced separately in the qualitative run directory.

---

## 5. Engine installability

| engine | status |
|--------|--------|
| basic_pitch | RUNNABLE (baseline, in production) |
| piano_transcription | RUNNABLE (CPU, checkpoint auto-download) |
| transkun | **TBD** — see follow-up (installable, isolated-env runtime check pending) |
| beat_this / librosa / music21_symbolic | RUNNABLE |

---

## Recommendations

1. **Piano-engine decision: blocked** until scored solo-piano ground truth
   (MAESTRO/ASAP) is acquired.
2. Evaluate piano-specialist engines (piano_transcription, transkun) only on
   solo-piano reference material.
3. Re-run the full-mix table on a larger scored set before drawing any
   mix-transcription conclusions.