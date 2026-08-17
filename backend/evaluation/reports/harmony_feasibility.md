# Harmony Feasibility Audit — GuitarSet baseline + OSS candidate landscape

> **Status:** FEASIBILITY AUDIT ONLY — no production change, no candidate integration.
> **Audit date:** 2026-08-17

## 1. Purpose

Determine whether the current production harmony engine (music21 symbolic)
has a **scorable real-audio baseline** and whether a realistic **OSS audio-native
alternative** exists that we could evaluate against it. This audit does not
install TensorFlow or any candidate, does not alter production music21 behavior,
and does not integrate anything.

## 2. GuitarSet reference repair

GuitarSet (Zenodo 3371780, CC BY 4.0) ships **JAMS annotations** that were
previously **unconsumable** by the harmony evaluation path: the corpus clips had
`reference: null` and no reference MIDI, so the harness refused harmony scoring
("Harmony evaluation requires reference MIDI") and every existing
`music21_symbolic` harmony result is `metrics: null`.

The data path is now repaired (evaluation-only):

- **`evaluation/datasets/parsers.py`** adds `parse_guitarset_harmony` (chords +
  key/mode) and `build_guitarset_reference_midi` (reference MIDI from the JAMS
  `note_midi` annotations, since GuitarSet ships no reference MIDI).
- Chord labels are the first `chord` annotation (compact `Root:quality`, e.g.
  `D#:maj`), normalized to the flat spelling GuitarSet's `key_mode` uses
  (`D#:maj` → root `Eb`) so chord-root comparisons against keys are consistent.
- `key_mode` gives tonic+mode (e.g. `Eb:major`, `D:minor`).

| GuitarSet clip | key (ref) | chord annotations | chord obs | note_midi obs |
|---|---|---|---|---|
| 00_BN1-129-Eb_comp | Eb major | 2 | 6 | 133 |
| 00_Funk1-114-Ab_comp | Ab major | 2 | 6 | 307 |
| 00_Jazz1-130-D_comp | D major | 2 | 6 | 206 |
| 00_Rock2-142-D_comp | D minor | 2 | 14 | 547 |
| 00_SS3-84-Bb_solo | Bb major | 2 | 16 | 123 |

The second `chord` annotation adds slash-bass / extension syntax
(`D#:sus2(7)/1`); it is documented but not used for scoring.

## 3. music21 symbolic baseline (production path, unaltered)

Scored via `evaluation/harmony_feasibility.py` on the reference MIDI built from
JAMS notes, using the shared `compute_analysis_metrics` (chord F1 = root match
within ±0.5 s window; key = string match).

| clip | music21 key | key match | production chords | reference chords | diag chords* |
|---|---|---|---|---|---|
| 00_BN1-129-Eb_comp | E- major (→Eb) | ✅ | 0 | 6 | 36 |
| 00_Funk1-114-Ab_comp | A- major (→Ab) | ✅ | 0 | 6 | 92 |
| 00_Jazz1-130-D_comp | D major | ✅ | 0 | 6 | 61 |
| 00_Rock2-142-D_comp | D minor | ✅ | 0 | 14 | 156 |
| 00_SS3-84-Bb_solo | G minor | ❌ (ref Bb major) | 0 | 16 | 21 |

\* `diag chords` = a diagnostic-only extraction using music21's always-available
`Chord.quality`; it is NOT production behavior (see below).

**Scored summary:**

- **Key accuracy: 0.8** (4/5). One genuine error (SS3_solo → music21 hears G
  minor, reference is Bb major). The other "miss" was purely a spelling issue
  (music21 `E-`/`A-` vs reference `Eb`/`Ab`), fixed by normalization.
- **Chord precision/recall/F1: 0.0 / 0.0 / 0.0** — the honest worst-case
  baseline. With reference chords present but **zero** predictions, recall and
  F1 are `0`, not "not computable" (this was an artifact of the shared metric
  only scoring when `predicted_chords` was non-empty; fixed so reference-present
  + zero-predictions scores `0`). Precision is undefined-equivalent to `0` here
  (no predictions to be precise about).

**Evaluation semantics (fixed):**
- **Time domain:** GuitarSet chord annotations are in **seconds**; music21
  reports symbolic quarter-length offsets. `evaluation/harmony_feasibility.py`
  now converts music21 symbolic offsets to seconds via the score tempo map
  (using the seconds-per-quarter from the MIDI) so predicted and reference
  chords share one time domain before the ±0.5 s root match. This is applied to
  both the (currently zero) production adapter output and the diagnostic path.
- **Zero-prediction baseline:** the shared `compute_analysis_metrics` now scores
  `recall=0, F1=0` when reference chords exist but no predictions are produced.
- **Parser tests:** `parse_guitarset_harmony` has deterministic tests for
  major/minor qualities, enharmonic (D#→Eb) normalization, `N`/no-chord
  skipping, `key_mode`, timestamps/duration, and unknown-quality fallback.

**Root cause of zero chords (real production finding):**
`Music21HarmonyAdapter.analyze_harmony` (`evaluation/engines/harmony.py`)
extracts chords only when `ch.impliedQuality` is non-empty, then maps it through
`_QUALITY_MAP`. On **MIDI-derived chords** `impliedQuality` is absent (the
attribute only materializes with a harmony/RN context), so every chord is
dropped by the `if not quality ... continue` guard. The library can produce 21–156
chords per clip when using `Chord.quality` (the diagnostic column). This is the
single most actionable fix if we want a scorable symbolic baseline: changing the
quality source (or keying it on `Chord.quality`/`pitchedCommonName`) would turn a
0-chord baseline into a measurable one — **but that is a production behavior
change and is explicitly out of scope for this audit.**

## 4. OSS audio-native candidate landscape

Requirements: actually obtainable today; known license; maintained enough to
evaluate; CPU-capable; Python-compatible; ARM-preferred; reasonable dependency
footprint; accepts real audio; produces chord/key output.

| | **autochord** | **chordia (lv-chordia)** | **madmom** | **audioflux** |
|---|---|---|---|---|
| repository/project | github.com/cjbayron/autochord | github.com/lv-chordia/chordia (**404**) | github.com/CPJKU/madmom | github.com/audioflux/audioflux |
| installation | `pip install autochord` | **not on PyPI** | `pip install madmom` (builds from sdist) | `pip install audioflux` |
| PyPI / status | 0.1.4 (Oct 2021, **dormant ~5y**) | **not obtainable** | 0.16.1 (2019, **dormant ~7y**) | 0.1.9 (active-ish) |
| license | MIT | (claimed MIT) | BSD-3 | MIT |
| framework/deps | tensorflow/keras, librosa, vamp, gdown, lazycats | — | numpy, scipy, Cython (compiled) | numpy, scipy, soundfile, matplotlib |
| model size | downloads ~100 MB+ from **Google Drive at import** | — | small HMM/CRF models bundled | no chord model |
| CPU support | yes (slow) | — | yes | yes |
| ARM likelihood | **low** — precompiled `nnls-chroma.so` VAMP plugin (x86) | n/a | **low** — Cython compile on ARM/Py3.11 often fails (verified: pip wheel build failed) | **high** — pure-python wheel (`py3-none-any`) |
| output semantics | `(start, end, "Root:quality")` incl. no-chord `N`; 25 classes (12 maj+12 min+N); reported 67.33% test acc | — | chord detection via `madmom.features.chords` | **no chord module** (feature extraction only) |
| maintenance/activity | dormant since 2021 | dead | dormant since 2019 | active |
| integration effort | low API (`recognize()`); needs TF runtime + VAMP + GDrive model download | n/a | moderate (Cython) | not a chord engine |

**autochord is the only genuinely audio-native OSS chord recognizer on PyPI**
that is CPU-capable and produces chord labels we can consume. It is, however:
dormant (2021), pulls TensorFlow into a torch-based worker, downloads its model
from an unversioned Google Drive URL at import (supply-chain concern), and ships
a precompiled x86 VAMP `.so` (ARM risk). Installing TensorFlow purely to test it
is not justified unless it emerges as clearly the best candidate; the audit
recommends deferring that decision (see §6).

**chordia** (the adapter currently in the registry) is **dead**: not on PyPI,
repo 404s, `is_available()` always False.

## 5. Evaluation-cleanup change

Because `LVChordiaAdapter` is an unquestionably unusable "fake runnable option"
that appears in the adapter registry but can never run, it is **removed** in a
small evaluation-cleanup change (`backend/evaluation/engines/harmony.py`) with a
regression test asserting the harmony registry no longer lists `lv_chordia` and
that the music21 adapter remains available. The audit itself does not integrate
any candidate.

## 6. Recommendation

**NO_VIABLE_CANDIDATE** for a production audio-native chord engine today:

- The only installable OSS audio chord recognizer (autochord) is dormant, pulls
  TensorFlow + a Google-Drive model, and is ARM-risky — a poor fit for the
  always-free ARM CPU worker.
- madmom fails to build on this platform; audioflux has no chord module.
- Meanwhile the **symbolic baseline has a concrete, low-cost improvement path**:
  the zero-chord result is an adapter extraction bug (`impliedQuality` absent on
  MIDI-derived chords), not a fundamental model limit. Fixing the quality source
  (a bounded production change) would make music21 harmony scorable
  (diagnostic shows 21–156 chords/clip) and give us a real baseline to compare
  any future OSS candidate against.

Suggested next step if harmony quality becomes a priority: a small PR that
changes the music21 adapter's chord-quality source (e.g. `Chord.quality` with a
root-aware fallback) and re-runs `evaluation/harmony_feasibility.py` to obtain a
scored chord baseline. Only after a scored symbolic baseline exists would an
autochord evaluation (with a contained TF venv, version-pinned model) be worth
the dependency cost.

## Files referenced

| File | Role |
|---|---|
| `backend/evaluation/datasets/parsers.py` | `parse_guitarset_harmony`, `build_guitarset_reference_midi` (new) |
| `backend/evaluation/harmony_feasibility.py` | baseline scorer (new); converts symbolic→seconds, zero-prediction baseline |
| `backend/evaluation/analysis_metrics.py` | shared chord/key metric computation (zero-prediction baseline fixed) |
| `backend/evaluation/engines/harmony.py` | music21 adapter (unaltered) + removed dead `lv_chordia` adapter |
| `backend/tests/test_real_audio_parsers.py` | deterministic `parse_guitarset_harmony` tests (new) |
| `backend/tests/test_evaluation.py` | chord-metric zero-prediction + time-domain tests (new) |
| `backend/evaluation/.cache/guitarset/annotation/*.jams` | GuitarSet ground truth |