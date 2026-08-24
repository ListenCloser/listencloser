# MELODY V2 OSS FINAL REPORT

## DATASETS

| Dataset | Type | Melody Labels | Size | Status |
|---------|------|---------------|------|--------|
| POP909 | Symbolic MIDI | MELODY track | 909 songs | ✅ Available, 31 processed |
| ASAP | Symbolic MIDI | Staff labels only | 218 pieces | ✅ Available |
| DCML | Symbolic | Voice annotations | Unknown | Not downloaded |
| MAESTRO | Symbolic MIDI | No melody labels | 1000+ pieces | Not useful |
| BiMMuDa | Unknown | Unknown | Unknown | Not found |
| MedleyDB | Audio | F0 contours | 100+ songs | Audio-only |
| MIREX AME | Audio | F0 contours | Unknown | Audio-only |

**Key finding:** POP909 is the only dataset with explicit symbolic melody labels (MELODY track in MIDI).

---

## SKYLINE

### Proper POP909 Baseline (30 songs)

| Metric | Value |
|--------|-------|
| Precision | 0.282 ± 0.090 |
| Recall | 0.645 ± 0.121 |
| F1 | 0.390 ± 0.105 |
| Quality Score | 0.091 ± 0.017 |

**Characteristics:**
- Very high recall (catches most melody notes)
- Very low precision (picks up many accompaniment notes)
- Duration-weighted scoring causes bass/accompaniment contamination
- Range includes bass notes (pitch 39+)

**Verdict:** Poor melody extraction. Legacy heuristic only.

---

## LSTOM

### Environment
- Repository: bytedance/midi_melody_extraction
- License: MIT
- Dependencies: torch, miditoolkit, music21, mir_eval
- Architecture: BiLSTM (6 input features, 128 hidden, 2 layers)

### Training
- Dataset: POP909 (31 songs processed, 5 used for quick training)
- Training time: ~2 minutes on CPU (10 epochs)
- Best validation loss: 0.0249

### Held-out Evaluation
- **Not completed** — only trained on 5 songs, not full dataset
- Validation Melody F: 0.598 (on small validation set)
- Full training on 909 songs would take ~30-60 minutes on CPU

### Runtime
- Inference: ~100ms per song on CPU
- Model size: ~500KB

### Verdict
**Promising but not production-ready.** Requires:
1. Full POP909 training (909 songs)
2. Held-out evaluation on separate test set
3. Cross-dataset evaluation (POP909 → ASAP generalization)

---

## PIANO_SVSEP

### Installation
- Repository: CPJKU/piano_svsep
- License: MIT
- Dependencies: torch, torch_geometric, partitura, pytorch_lightning
- **Blocked:** torch_geometric compatibility issue with current torch version

### Pretrained Artifacts
- `pretrained_models/model.ckpt` — PyTorch Lightning checkpoint
- Architecture: GNN (SageConv, 23 input features, 256 hidden, 3 layers)
- Trained on: DCML + jpop datasets

### Actual Task
- **Voice and staff separation** (NOT melody extraction)
- Input: MusicXML/MEI (quantized symbolic music)
- Output: Voice and staff assignments per note

### Staff Results
- Cannot run due to torch_geometric compatibility issue

### Voice Results
- Cannot run due to torch_geometric compatibility issue

### Runtime
- Unknown (blocked by installation)

### Verdict
**Potentially valuable for voice/staff separation, but installation blocked.** Requires:
1. Fix torch_geometric compatibility
2. Evaluate on ASAP for staff assignment
3. Does NOT solve melody extraction (only voice/staff separation)

---

## PARTITURA

### Corrected Voice-Assignment Results (ASAP, 30 pieces)

| Metric | Value | Meaning |
|--------|-------|---------|
| Precision | 0.516 | When Partitura says same-staff, correct 52% of time |
| Recall | 0.334 | Catches 33% of true same-staff pairs |
| F1 | 0.404 | Overall staff-assignment quality |
| Fragmentation | 2.2x | Creates 2.2x more voices than staves |

**Note:** This measures staff separation, NOT voice separation or melody extraction.

### Verdict
**Poor for piano.** Over-fragments. Low recall.

---

## OTHER SYMBOLIC OSS

| Candidate | Type | Status | Verdict |
|-----------|------|--------|---------|
| music21 voice streams | Symbolic | Only reads pre-defined voices | Not suitable |
| pretty_midi | Symbolic | No voice separation | Not applicable |
| LStoM | Symbolic melody | Trained on POP909, F=0.598 (small eval) | Promising |

---

## AUDIO-NATIVE OSS

| Candidate | Type | Status | Verdict |
|-----------|------|--------|---------|
| librosa pyin | Audio | Pitch detection, not melody | Not applicable |
| madmom | Audio | Onset detection, not melody | Not applicable |
| essentia | Audio | Predominant melody extraction | Not evaluated |

**Note:** Audio-native approaches could bypass MIDI voice separation entirely, but require separate evaluation.

---

## REPRESENTATION SENSITIVITY

| Input | Score Voices | Perf Voices |
|-------|--------------|-------------|
| Bach Fugue | 5 | 11 |
| Chopin Etude | 13 | 21 |
| Mozart Sonata | 8 | 13 |

Performance MIDI produces more voices than score MIDI (sustain pedal, timing variations).

---

## MELODY IDENTIFICATION

**Not evaluated.** No validated melody-identification strategy exists.

POP909 provides melody ground truth, but:
- LStoM not fully trained
- Piano_SVSep blocked
- No other candidate evaluated

---

## PRODUCT TRUTHFULNESS

**Current claims:** "Range: MIDI X-Y · Z% stepwise motion" with quality score.

**Assessment:** Adequate. Code already notes "greedy-skyline candidate-margin score, not a calibrated probability."

**No additional softening needed.**

---

## BEST ENGINE PER PROFILE

| Profile | Best Engine | Status |
|---------|-------------|--------|
| Pop/arranged symbolic | LStoM (when trained) | Needs full training |
| Score-like solo piano | Piano_SVSep (when working) | Blocked by installation |
| General audio | Not evaluated | Future work |
| Unsupported | Skyline (legacy) | Current fallback |

---

## CAN SKYLINE BE DELETED?

**NO**

**Exact blockers:**
1. LStoM not fully trained (only 5/909 songs)
2. Piano_SVSep installation blocked
3. No validated melody-identification strategy
4. No cross-dataset evaluation

---

## SHOULD MELODY CLAIMS BE EXPOSED?

**Yes, with current truthfulness level.** The existing code comment already notes "greedy-skyline candidate-margin score, not a calibrated probability."

---

## PRODUCTION DECISION

**MORE EVALUATION**

**Reason:** Two promising candidates exist (LStoM, Piano_SVSep) but neither is production-ready:
- LStoM needs full training on POP909
- Piano_SVSep needs installation fix

---

## PR

**None recommended yet.** Evidence insufficient for replacement.

---

## NEXT 3 TASKS

1. **Train LStoM on full POP909** — most promising path for direct melody extraction
2. **Fix Piano_SVSep installation** — resolve torch_geometric compatibility
3. **Evaluate audio-native** — essentia predominant melody as alternative

---

## BLOCKERS

1. LStoM requires full POP909 training (909 songs, ~30-60 min CPU)
2. Piano_SVSep blocked by torch_geometric compatibility
3. No melody-labeled ground truth for ASAP evaluation
4. No validated melody-identification strategy
