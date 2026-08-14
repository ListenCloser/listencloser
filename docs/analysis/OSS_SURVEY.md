# OSS Survey — MIR / Symbolic Analysis Alternatives

> **Research date**: 2026-08-14 | **Focus**: Actively maintained OSS with usable Python APIs for production deployment on CPU (ARM)

---

## Evaluation Criteria

| Criterion | Weight | Notes |
|-----------|--------|-------|
| Maintenance status | Critical | Recent commits, issue response, Python version support |
| License | Critical | Must be compatible (MIT, BSD, Apache, LGPL — **NOT AGPL** for proprietary deployment) |
| Model availability | High | Pre-trained models included or easily downloadable |
| CPU/GPU requirements | High | Must run on Oracle Always-Free ARM (4 CPU, 24GB RAM, no GPU) |
| Expected runtime | Medium | <30s for 2-3 min audio |
| Python compatibility | High | Python 3.9+ |
| Input/Output format | High | WAV/MP3 in; JSON/dict out |
| Confidence availability | Medium | Calibrated probabilities preferred |
| Temporal output | High | Per-segment/per-beat timestamps required |
| Integration difficulty | Medium | Pure Python or simple C++ bindings |

---

## Candidate Matrix

### 1. Essentia (MTG/essentia)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/MTG/essentia |
| **License** | **AGPL-3.0** ⚠️ |
| **Maintenance** | Active (3,769 commits, recent releases) |
| **Python** | `pip install essentia` (Linux x86_64, i686); ARM wheels via cibuildwheel |
| **Models** | Built-in (no separate download) |
| **CPU/GPU** | CPU only, optimized C++ |
| **Runtime** | ~1-5s for 3-min track |
| **Key algorithms** | `RhythmExtractor2013`, `KeyExtractor`, `LoudnessEBUR128`, `Centroid`, `Melodia`, `PredominantPitchMelodia`, `Chordino` (via Vamp), `BeatTrackerMultiFeature` |
| **Confidence** | Key: `key_strength`; Rhythm: internal; Melody: salience |
| **Temporal output** | Beats, segments, frame-level (configurable) |
| **Integration** | Python bindings (pybind11); streaming API |
| **Blocking issue** | **AGPL-3.0** — viral license, requires source disclosure for network services. Current code uses it as optional fallback (OK for internal/tools), but cannot be hard dependency for SaaS. |

**Verdict**: **USE WITH CAUTION** — Current fallback usage is acceptable (optional, not linked). For production hard dependency, need license exception or alternative.

---

### 2. librosa
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/librosa/librosa |
| **License** | **ISC (MIT-like)** ✅ |
| **Maintenance** | Active (3,523 commits, v0.10+ 2023-2024) |
| **Python** | 3.8+ (pure Python + numba) |
| **Models** | None (algorithmic) |
| **CPU/GPU** | CPU (numba JIT) |
| **Runtime** | ~5-15s for 3-min track |
| **Key algorithms** | `beat_track`, `chroma_cqt/stft`, `mfcc`, `spectral_centroid`, `rms`, `harmonic/percussive separation`, `onset_detect`, `piptrack` (pitch), `f0` estimation |
| **Missing** | No key estimation (removed 0.10+), no chord recognition, no melody extraction, no structure segmentation |
| **Confidence** | None (algorithmic outputs) |
| **Temporal output** | Frame-level for all features |
| **Integration** | Pure Python, zero-dep beyond numpy/scipy/numba |

**Verdict**: **KEEP AS BASELINE** — Already in use for beat tracking, chroma, onsets. License-safe. Fill gaps with other OSS.

---

### 3. music21
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/cuthbertLab/music21 |
| **License** | **BSD-3-Clause** ✅ |
| **Maintenance** | Active (10,122 commits, v10+ 2024) |
| **Python** | 3.12+ (v9 on 3.10, v8 on 3.8/3.9) |
| **Models** | None (symbolic algorithms) |
| **CPU/GPU** | CPU |
| **Runtime** | ~1-3s for MIDI parse + analysis |
| **Key algorithms** | `analyze("key")`, `Chord` detection, `romanNumeralFromChord`, `voiceLeading`, `quantize`, `makeNotation` |
| **Missing** | No cadence detection, no modulation detection, no phrase detection, no melody extraction |
| **Confidence** | Key: `correlationCoefficient` (not calibrated) |
| **Temporal output** | Quarter-note offsets (symbolic) |
| **Integration** | Pure Python, mature API |

**Verdict**: **KEEP FOR SYMBOLIC** — Already production baseline for harmony. License-safe. Gap-fill for higher-level symbolic analysis.

---

### 4. madmom
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/CPJKU/madmom |
| **License** | **MIT** ✅ |
| **Maintenance** | Low (last release 2021, commits sporadic) |
| **Python** | 3.6+ (C++ extensions via cython) |
| **Models** | Pre-trained (downloaded on first use) |
| **CPU/GPU** | CPU (TensorFlow 1.x backend — **deprecated**) |
| **Runtime** | ~10-30s for 3-min track |
| **Key algorithms** | `RNNBeatProcessor` + `DBNBeatTrackingProcessor` (beats/downbeats), `CNNKeyRecognitionProcessor` (key), `ChordDetectionProcessor` (chords), `Melodia` (melody) |
| **Confidence** | Beat: activation probabilities; Key: softmax; Chord: frame-level |
| **Temporal output** | Frame-level (10ms/50ms) |
| **Blocking issues** | **TensorFlow 1.x** — unmaintained, security issues, incompatible with modern Python/TF. Model downloads from Zenodo. |

**Verdict**: **AVOID** — TF1 backend is a dead end. No active maintenance since 2021.

---

### 5. Beat This! (beat_this)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/beatthis/beat_this |
| **License** | **MIT** ✅ |
| **Maintenance** | Active (recent 2023-2024) |
| **Python** | 3.8+ (PyTorch) |
| **Models** | Pre-trained (included in pip package ~150MB) |
| **CPU/GPU** | CPU (PyTorch) — **slow on CPU** |
| **Runtime** | ~10-30s on CPU for 3-min track |
| **Key algorithms** | Transformer-based beat/downbeat tracking |
| **Confidence** | Frame-level beat/downbeat probabilities |
| **Temporal output** | Beat/downbeat times (seconds) |
| **Integration** | `pip install beat-this` → `beat_this.run(audio_path)` |
| **Already in codebase** | `engines/beats/beat_this_engine.py` (optional, not default) |

**Verdict**: **EVALUATE FOR BEAT/DOWNBEAT** — Better accuracy than librosa, but heavier. Optional engine already wired. Good for "rhythmic/electronic" profile.

---

### 6. All-In-One (allin1)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/Harmonix-MIT/All-In-One |
| **License** | **MIT** ✅ |
| **Maintenance** | Active (2023-2024) |
| **Python** | 3.8+ (PyTorch + NATTEN) |
| **Models** | Pre-trained (~200MB) |
| **CPU/GPU** | CPU (NATTEN requires CUDA for full speed; CPU fallback slow) |
| **Runtime** | ~30-60s on CPU for 3-min track |
| **Key algorithms** | Joint beat/downbeat/structure segmentation (Harmonix model) |
| **Confidence** | Per-segment labels + boundaries |
| **Temporal output** | Beats, downbeats, segment boundaries (seconds) |
| **Already in codebase** | `engines/structure/allin1_engine.py` (disabled by default: `ALLIN1_ENABLED=false`) |

**Verdict**: **EVALUATE FOR STRUCTURE** — Only OSS joint beat+structure model. Heavy (NATTEN). Keep as optional profile-specific engine.

---

### 7. chordia (lv-chordia/chordia)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/lv-chordia/chordia |
| **License** | **MIT** ✅ |
| **Maintenance** | Active (2023-2024) |
| **Python** | 3.8+ (PyTorch) |
| **Models** | Pre-trained (CNN+CRF) |
| **CPU/GPU** | CPU (PyTorch) |
| **Runtime** | ~5-10s for 3-min track |
| **Key algorithms** | Chord recognition + key estimation from **audio directly** (no MIDI needed) |
| **Confidence** | Per-chord frame probabilities |
| **Temporal output** | Chord segments with timestamps |
| **Already in codebase** | `evaluation/engines/harmony.py:LVChordiaAdapter` (evaluation only) |

**Verdict**: **STRONG CANDIDATE FOR HARMONY** — Audio-native chord+key, MIT license, active. Could replace music21 symbolic path for audio-first analysis. Evaluation adapter exists.

---

### 8. Transkun (qiuqiangkong/transkun)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/qiuqiangkong/transkun |
| **License** | **MIT** ✅ |
| **Maintenance** | Active (2023-2024) |
| **Python** | 3.9+ (PyTorch + moduleconf + soxr) |
| **Models** | Included (~150MB) |
| **CPU/GPU** | CPU |
| **Runtime** | ~10-20s for 3-min piano |
| **Key algorithms** | Transformer-based piano transcription (EfficientNet + Transformer) |
| **Already in codebase** | `engines/transcription/transkun.py` — **production for solo_piano profile** |
| **Bakeoff result** | Macro F1 0.8034 vs Basic Pitch 0.1083 |

**Verdict**: **KEEP FOR SOLO PIANO** — Already production-routed. Best-in-class for piano.

---

### 9. Basic Pitch (spotify/basic-pitch)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/spotify/basic-pitch |
| **License** | **MIT** ✅ |
| **Maintenance** | Active (2023-2024) |
| **Python** | 3.7+ (TensorFlow 2.x / TFLite / ONNX) |
| **Models** | Included (~30MB) |
| **CPU/GPU** | CPU (TFLite/ONNX fast) |
| **Runtime** | ~5-10s for 3-min track |
| **Key algorithms** | Onset/frame CNN for multi-instrument transcription |
| **Already in codebase** | `engines/transcription/basic_pitch.py` — **production default** |

**Verdict**: **KEEP AS GENERAL DEFAULT** — Already production. Good general-purpose.

---

### 10. piano_transcription (qiuqiangkong/piano_transcription)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/qiuqiangkong/piano_transcription |
| **License** | **MIT** ✅ |
| **Maintenance** | Low (older, superseded by Transkun) |
| **Python** | 3.7+ |
| **Models** | Auto-downloaded (~200MB) |
| **Bakeoff result** | Macro F1 0.4014 (between Basic Pitch and Transkun) |

**Verdict**: **DEPRECATED** — Superseded by Transkun. Keep in evaluation for comparison only.

---

### 11. MSAF (music_structure_analysis)
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/urinieto/msaf |
| **License** | **GPL-3.0** ⚠️ |
| **Maintenance** | Low (last commit 2020) |
| **Algorithms** | Structure segmentation (multiple algorithms: SF, CNMF, Old, etc.) |
| **Runtime** | Slow (Python loops) |

**Verdict**: **AVOID** — GPL license, unmaintained.

---

### 12. crepe / pitch-estimation
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/marl/crepe |
| **License** | **MIT** ✅ |
| **Maintenance** | Moderate |
| **Algorithms** | Deep pitch estimation (CNN) |
| **Use case** | Melody/f0 extraction from audio |

**Verdict**: **CANDIDATE FOR MELODY** — If audio-based melody needed. Requires TF.

---

### 13. mir_eval
| Attribute | Value |
|-----------|-------|
| **Repository** | https://github.com/craffel/mir_eval |
| **License** | **BSD-3-Clause** ✅ |
| **Purpose** | **Evaluation metrics only** (not analysis) |
| **Algorithms** | Beat F1, chord symbol metrics, key accuracy, structure boundary F1, melody precision/recall |

**Verdict**: **USE FOR EVALUATION** — Already in evaluation infrastructure.

---

## Recommended OSS Stack by Capability

| Capability | Primary OSS | Fallback | License | Status |
|------------|-------------|----------|---------|--------|
| **Transcription (general)** | Basic Pitch | — | MIT | ✅ Production |
| **Transcription (solo piano)** | Transkun | Basic Pitch | MIT | ✅ Production |
| **Beat tracking** | librosa | Beat This! | ISC / MIT | ✅ Production / Optional |
| **Downbeat tracking** | Beat This! | All-In-One | MIT | ⚠️ Optional |
| **Structure segmentation** | All-In-One | — | MIT | ⚠️ Disabled (heavy) |
| **Key (audio)** | Essentia | chordia | AGPL / MIT | ⚠️ Fallback only |
| **Chords (audio)** | chordia | Essentia | MIT / AGPL | 🔬 Evaluation |
| **Chords (symbolic)** | music21 | — | BSD | ✅ Production |
| **Roman Numerals** | music21 | — | BSD | ✅ Production |
| **Cadence detection** | — | custom (gap) | — | ❌ Missing |
| **Modulation detection** | — | custom (gap) | — | ❌ Missing |
| **Melody (audio)** | Essentia Melodia / crepe | — | AGPL / MIT | ⚠️ Gap |
| **Melody (symbolic)** | — | skyline (gap) | — | ❌ Gap |
| **Phrase detection** | — | — | — | ❌ Missing |
| **Voice leading** | music21 | — | BSD | ✅ Conditional |

---

## License Risk Summary

| Package | License | Risk | Mitigation |
|---------|---------|------|------------|
| Essentia | AGPL-3.0 | **High** — viral for network services | Use only as optional fallback; never hard dependency |
| MSAF | GPL-3.0 | **High** | Avoid |
| All others | MIT/BSD/ISC | **Low** | Safe for production |

---

## Integration Priority for Next Architecture

### P0 (Immediate — fills critical gaps)
1. **chordia** — Audio-native chord+key (MIT, active, replaces custom symbolic-only path)
2. **Essentia Melodia** (if license resolved) or **crepe** — Audio melody extraction
3. **Beat This!** — Enable as default beat engine (better downbeats)

### P1 (Profile-specific routing)
1. **All-In-One** — Enable for "rhythmic/electronic" profile (structure+beats joint)
2. **madmom key** — If TF1 dependency resolved (unlikely)

### P2 (Research/Advanced)
1. **Modulation detection** — No mature OSS; monitor literature
2. **Cadence detection** — No mature OSS; consider training on Bach chorales
3. **Phrase detection** — No mature OSS; requires symbolic corpus

---

## Not Recommended (with reasons)

| Package | Reason |
|---------|--------|
| madmom | TensorFlow 1.x backend (dead) |
| MSAF | GPL-3.0, unmaintained |
| piano_transcription | Superseded by Transkun |
| Custom KS (librosa path) | Unvalidated, replace with Essentia/chordia |
| Custom modulation detection | High false positive, delete |
| Custom cadence detection | Weak heuristic, keep only as labeled candidate |