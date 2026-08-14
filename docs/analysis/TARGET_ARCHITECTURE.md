# Target Analysis Architecture — Design for Next Generation

> **Status**: Design document — NOT implementation. Grounded in audit findings.

---

## Design Principles (from Handoff)

1. **Mature OSS > Explicit routing > Thin gap-filler > Custom algorithm**
2. **Missing evidence > Invented evidence**
3. **Provenance on everything** — engine, model, parameters, confidence semantics
4. **Temporal mapping first-class** — seconds ↔ beats ↔ measures
5. **Profile-aware routing** — solo_piano, general tonal, rhythmic/electronic
6. **Normalized evidence layer** — typed, queryable, relationship-aware

---

## Target Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUDIO / SYMBOLIC ARTIFACTS                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ audio_original│  │ midi_perf    │  │ midi_corrected│  │ musicxml     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
└─────────│─────────────────│─────────────────│─────────────────│────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ENGINE REGISTRY (per capability)                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │Transcription│ │  Beat/Down- │ │  Structure  │ │  Notation   │           │
│  │  Engines    │ │  beat Eng.  │ │  Engines    │ │  Engines    │           │
│  ├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤           │
│  │ • basic_pitch│ │ • librosa   │ │ • allin1    │ │ • music21   │           │
│  │ • transkun   │ │ • beat_this │ │ • (future)  │ │ • (future)  │           │
│  │ • (profile)  │ │ • (profile) │ │             │ │             │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
└─────────│─────────────────│─────────────────│─────────────│────────────────┘
          │                 │                 │             │
          ▼                 ▼                 ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SIGNAL-LEVEL EVIDENCE (OSS)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ BeatGrid     │ │ KeyRegion    │ │ ChordEvent   │ │ MelodyEvent  │       │
│  │ (beats,      │ │ (audio+      │ │ (audio:      │ │ (audio:      │       │
│  │  downbeats,  │ │  symbolic)   │ │  chordia)    │ │  Melodia)    │       │
│  │  bpm, conf)  │ │              │ │ (symbolic:   │ │ (symbolic:   │       │
│  │              │ │              │ │  music21)    │ │  skyline)    │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ Section      │ │ Dynamics     │ │ Instrument   │ │ OnsetDensity │       │
│  │ (allin1)     │ │ (Essentia)   │ │ (Essentia)   │ │ (librosa)    │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
          │                 │                 │             │
          ▼                 ▼                 ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NORMALIZED MUSICAL EVIDENCE LAYER                        │
│  (Typed evidence objects with: id, kind, scope, value, confidence,        │
│   provenance, temporal_scope[seconds/beats/measures], relationships)       │
│                                                                             │
│  Evidence Types:                                                            │
│  • KeyRegion          • ChordEvent         • Beat / Downbeat               │
│  • Section            • MelodyEvent        • Phrase                        │
│  • Cadence            • Modulation         • Motif                         │
│  • TextureEvent       • DynamicsEvent      • RegisterRegion                │
│  • VoiceLeading       • RhythmicPattern    • InstrumentRegion              │
│                                                                             │
│  Relationships:                                                             │
│  • contains (section → phrases)                                           │
│  • follows (chord → chord)                                                │
│  • resolves (cadence → chord)                                             │
│  • modulates (key_region → key_region)                                    │
│  • repeats (motif → motif)                                                │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  RELATIONAL / HIGHER-LEVEL INTERPRETATION                   │
│  (Reasoning over evidence layer — thin orchestration, OSS where possible)  │
│                                                                             │
│  • HarmonicFunctionAnalyzer  → T/S/D labels from ChordEvent + KeyRegion   │
│  • PhraseBoundaryDetector    → from Cadence + MelodyEvent + Section       │
│  • ModulationConfirmer       → from KeyRegion sequence (run-length gating) │
│  • MotifFinder               → from NoteEntity sequences (symbolic)       │
│  • TensionCalculator         → from HarmonicFunction + Dynamics + Rhythm  │
│                                                                             │
│  Output: Enriched evidence with relational links                          │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONSUMER INTERFACES                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Inspector Timeline│  │ AskContext       │  │ Visualizations   │          │
│  │ (evidence cards,  │  (typed evidence   │  (piano roll,      │          │
│  │  filtering,       │  + relationships   │  score, waveform) │          │
│  │  provenance)      │  for grounding)    │                   │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer Breakdown

### Layer 1: Engine Registry (Orchestration)
**Responsibility**: Route artifacts to engines based on profile + capability
**Custom code**: Profile router, engine lifecycle, provenance capture
**OSS**: None (thin registry)

```python
# Conceptual interface
class AnalysisOrchestrator:
    def analyze(self, artifacts: ArtifactBundle, profile: AnalysisProfile) -> EvidenceBundle:
        # 1. Select engines per capability per profile
        # 2. Run in parallel where independent
        # 3. Collect normalized Evidence objects
        # 4. Return EvidenceBundle with full provenance
```

### Layer 2: Signal-Level Evidence (OSS Engines)
**Responsibility**: Produce typed evidence from audio/MIDI
**Each engine produces ONE evidence type** with full provenance

| Capability | Engine(s) | Evidence Type | Temporal Scope |
|------------|-----------|---------------|----------------|
| Beat/Downbeat | librosa / Beat This! | `BeatGrid` | per-beat (seconds) |
| Key (audio) | Essentia / chordia | `KeyRegion` | per-window (seconds) |
| Chords (audio) | chordia | `ChordEvent` | per-segment (seconds) |
| Chords (symbolic) | music21 | `ChordEvent` | per-chord (beats) |
| Melody (audio) | Essentia Melodia / crepe | `MelodyEvent` | per-note (seconds) |
| Melody (symbolic) | skyline (gap-filler) | `MelodyEvent` | per-note (beats) |
| Structure | All-In-One | `Section` | per-segment (seconds) |
| Dynamics | Essentia | `DynamicsEvent` | per-frame (seconds) |
| Instrumentation | Essentia | `InstrumentRegion` | per-segment (seconds) |

### Layer 3: Normalized Musical Evidence Layer (Core Innovation)

**Schema Concept** — Single table, common envelope with discriminated union value:

```python
@dataclass
class MusicalEvidence:
    id: UUID
    kind: EvidenceKind  # Enum: "key_region" | "chord" | "beat" | "downbeat" | "section" | "melody" | "cadence" | "modulation" | "rhythm" | "dynamics" | ...
    
    # Temporal scope (at least one)
    time_range: TimeRange | None      # seconds (performance time)
    measure_range: MeasureRange | None # measures (notation time)
    beat_range: BeatRange | None      # beats (metrical time)
    note_ids: list[UUID] | None       # note entity refs (symbolic)
    
    value: EvidenceValue              # Discriminated union by kind
    confidence: Confidence | None     # Calibrated [0,1] or None
    provenance: EngineProvenance      # engine, model, version, params
    
    # Relationships (populated by Layer 4)
    relationships: list[EvidenceRelationship] = field(default_factory=list)

# EvidenceValue — discriminated union by kind:
type EvidenceValue =
  | { kind: "key_region"; tonic: string; mode: string; strength: float }
  | { kind: "chord"; root: string; quality: string; inversion: int | None }
  | { kind: "beat"; position: float; is_downbeat: bool; bpm: float }
  | { kind: "downbeat"; position: float; measure_number: int }
  | { kind: "section"; label: string; boundary_confidence: float }
  | { kind: "melody"; pitch: int; start: float; end: float; salience: float }
  | { kind: "cadence"; type: string; chords: list[string]; strength: float }
  | { kind: "modulation"; from_key: string; to_key: string; pivot_chord: string | None }
  | { kind: "rhythm"; density: float; syncopation: float | None }
  | { kind: "dynamics"; loudness_lufs: float }
  | ...
```

**Why envelope + discriminated union over generic Insight or separate tables?**
1. **Single query surface** — filter by `kind`, `time_range`, `confidence` without joins
2. **Typed payloads** — `value` structure enforced by `kind`; no string parsing
3. **Temporal mapping** — seconds ↔ beats ↔ measures ↔ note_ids in one row
3. **Confidence semantics** — per-kind calibration, not single float
4. **Provenance granularity** — engine per evidence, not per batch
5. **Migration-friendly** — `Insight` becomes a view over `MusicalEvidence` during dual-write phase

### Layer 4: Relational Interpretation (Thin Orchestration)

**Responsibility**: Compute relationships between evidence objects
**Custom code**: Relationship rules (deterministic, documented)
**OSS**: Where ML exists (e.g., motif finding)

| Relationship | Rule | Input Evidence | Output |
|--------------|------|----------------|--------|
| `harmonic_function` | Map RN/chord to T/S/D in key | `ChordEvent` + `KeyRegion` | `HarmonicFunction` on ChordEvent |
| `phrase_boundary` | Cadence + melodic closure + section boundary | `Cadence` + `MelodyEvent` + `Section` | `Phrase` |
| `modulation_confirmed` | Sustained key region change (≥3 windows) | `KeyRegion` sequence | `Modulation` (upgraded from tonicization) |
| `motif_repetition` | Note pattern matching (edit distance) | `NoteEntity` sequences | `Motif` + `repeats` links |
| `tension` | Harmonic distance + dynamics + density | `HarmonicFunction` + `DynamicsEvent` + `RhythmicPattern` | `TensionEvent` |

### Layer 5: Consumer Interfaces (Existing + Enhanced)

**Inspector**: Queries evidence by type, time range, confidence threshold. Shows provenance badges.
**AskContext**: Serializes relevant evidence (typed, with relationships) for LLM grounding.
**Visualizations**: Piano roll shows `NoteEntity` + `ChordEvent` + `BeatGrid`; Score shows `MeasureRange` evidence.

---

## Profile-Aware Routing

| Profile | Transcription | Beat/Downbeat | Harmony | Melody | Structure | Notation |
|---------|---------------|---------------|---------|--------|-----------|----------|
| `solo_piano` | Transkun | Beat This! | music21 (symbolic) | Melodia (audio) | All-In-One | music21 grand staff |
| `general_tonal` | Basic Pitch | Beat This! | chordia (audio) | Melodia (audio) | All-In-One | music21 |
| `rhythmic_electronic` | Basic Pitch | Beat This! | chordia (audio) | — (skip) | All-In-One | — (skip) |
| `unknown` | Basic Pitch | librosa | chordia (audio) | Melodia (audio) | — | music21 |

**Routing logic**: Explicit capability matrix per profile, not genre classifier.

---

## Provenance & Confidence Architecture

### Provenance (on every evidence object)
```python
@dataclass
class EngineProvenance:
    engine: str                    # "chordia", "music21", "beat_this"
    library_version: str           # "1.2.3"
    model: str | None              # "harmonix-all", "melodia_v2"
    parameters: dict               # {"threshold": 0.5, "window": 2.0}
    timestamp: datetime            # when produced
```

### Confidence Semantics (per evidence kind)
| Evidence Kind | Confidence Type | Calibration |
|---------------|-----------------|-------------|
| `BeatGrid` | per-beat probability | Model output (sigmoid) |
| `KeyRegion` | key_strength [0,1] | Essentia/chordia internal |
| `ChordEvent` | frame probability [0,1] | chordia CRF marginal |
| `MelodyEvent` | salience [0,1] | Melodia/crepe output |
| `Section` | boundary probability | All-In-One output |
| `Cadence` | pattern strength [0,1] | Heuristic (explicit) |
| `Phrase` | closure strength [0,1] | Heuristic (explicit) |
| `Modulation` | run-length probability | Statistical (explicit) |

**Rule**: No hardcoded confidences. `None` = unavailable, not "low confidence".

---

## Temporal Mapping (Critical for Cross-Domain Sync)

| Domain | Unit | Conversion |
|--------|------|------------|
| Performance (audio) | seconds | Ground truth |
| Metrical (beats) | beat number | `beat_time = beat_grid[beat]` |
| Notation (measures) | measure number | `measure_time = measure_starts[measure]` |
| Symbolic (MIDI) | quarter notes | `qn_time = qn * 60 / bpm(qn)` |

**Evidence stores ALL applicable scopes** — enables "select in piano roll → highlight in score → query Ask".

---

## Migration Path from Current Insight Schema

| Current Insight | Target Evidence (kind) | Migration |
|-----------------|------------------------|-----------|
| `key` | `key_region` (global) | 1:1, add temporal scope |
| `tempo` | `beat` (bpm extracted) | Extract from beat grid |
| `time_signature` | `downbeat` (meter inferred) | From downbeat pattern |
| `chord` | `chord` | 1:1, add beat_range |
| `roman_numeral` | `chord.harmonic_function` | Compute in Layer 4 |
| `cadence_candidate` | `cadence` | Upgrade if confirmed |
| `modulation` | `modulation` | Filter false positives |
| `rhythm` | `rhythm` | Decompose |
| `melody` | `melody` sequence | 1:many |
| `voice_motion_candidate` | (deferred) | Conditional |
| `section` | `section` | 1:1 |

---

## Files to Create/Modify (Architecture Scope)

| File | Layer | Status |
|------|-------|--------|
| `engines/registry.py` | 1 | Extend with profile router |
| `engines/base.py` | 1-2 | Add evidence-type protocols |
| `engines/harmony/chordia_engine.py` | 2 | NEW — audio chord engine |
| `engines/melody/melodia_engine.py` | 2 | NEW — audio melody engine |
| `engines/structure/allin1_engine.py` | 2 | Enable by default for profiles |
| `analyze.py` | 1-2 | Refactor to orchestrator |
| `domain/capabilities.py` | 1,5 | New `handle_analyze_v2` |
| `schemas/export/MusicalEvidence.schema.json` | 3 | NEW — envelope + discriminated union schema |
| `domain/models.py` | 3 | Add `MusicalEvidence` table (single, JSONB value) |
| `lib/inspector/evidence.ts` | 5 | NEW — typed evidence client |
| `hello-ai-worktrees/ask-ui/lib/ask/context.ts` | 5 | Enhance with relationships |

---

## Non-Goals for This Architecture

- ❌ Genre classifier (use explicit profile override)
- ❌ Custom ML models (use OSS)
- ❌ RAG/vector DB for evidence (SQL + typed schema sufficient)
- ❌ Agent framework (Ask is grounded LLM, not agent)
- ❌ Real-time streaming (batch analysis first)
- ❌ Universal representation (piano roll/score are views, not assumptions)