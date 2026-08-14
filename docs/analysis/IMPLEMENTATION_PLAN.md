# Implementation Plan — Next 5 PRs (Revised, Evidence-Driven)

> **Principle**: Small, independently reviewable PRs. Each ships value. No 30-PR wishlist.
> **Revision**: Incorporates owner feedback — evidence-driven sequencing, Transkun routing owned by #229, evidence schema as common envelope.

---

## Priority Classification

| Priority | Definition |
|----------|------------|
| **P0** | Blocks genuine usefulness of Analysis; high user-visible impact |
| **P1** | Enables broader genres / richer understanding; significant but not blocking |
| **P2** | Advanced research / product ideas; defer until P0/P1 stable |

---

## Revised PR Order

| Order | PR | Priority | Objective |
|-------|-----|----------|-----------|
| **A** | **Analysis Truthfulness Cleanup** | P0 | Delete known-bad modulation claims; suppress analysis lacking defensible evidence |
| **B** | **Evaluated Audio Pulse Evidence** | P0 | Benchmark/select beat/downbeat engine; feed real tempo/beat into Analysis |
| **C** | **Post-Transkun Analysis Diagnostic** | P0 | Quantify which symbolic analyses improve purely from better transcription |
| **D** | **Harmony OSS Bakeoff** | P1 | Audio-native vs symbolic harmony on scored datasets; no production integration until evidence |
| **E** | **Normalized MusicalEvidence Contract + Dual Migration** | P1 | Common envelope with discriminated union values; dual-read/dual-write path |

**Removed**: "Verify Transkun Routing" — owned by #229. PR C uses #229's output as input.

---

## PR A — Analysis Truthfulness Cleanup (P0)

### Objective
Delete known-bad modulation claims and suppress analysis that lacks defensible evidence. No new capabilities.

### Files Touched
- `backend/engines/harmony/music21_engine.py` — Remove `_detect_modulations()`, `_key_from_pc_vector()`, KS constants
- `backend/engines/harmony/music21_engine.py` — Update `component_provenance()` to remove modulations entry
- `backend/analyze.py` — Remove `ModulationResult` TypedDict, remove `modulations` from `AnalysisResult`
- `backend/domain/capabilities.py` — Remove modulation insight creation (L945-960)
- `backend/schemas/export/Insight.schema.json` — No change (kind="modulation" simply not produced)

### Additional Truthfulness Fixes
- Suppress Roman numeral insights when `chords` is empty (no defensible chord evidence)
- Ensure every persisted insight has honest provenance (engine, method, confidence semantics)

### Behavior Changed
- `AnalysisResult.modulations` → removed (or always `[]`)
- No `modulation` insights persisted
- Roman numeral insights only created when `chords` non-empty
- Inspector/Ask no longer show false modulation cards or contradictory RNs

### Evaluation Required
- Regression test: `test_analysis_truthfulness.py` — verify 0 modulation insights, 0 RN insights when chords empty
- Manual verify: Real piano fixture produces Key + Rhythm only (no modulations, no RNs)

### Migration Concerns
- Low — modulation insights were already labeled "possible_" with `confidence=None`
- RN suppression is new but defensible: no chords → no harmonic basis for RNs

### Explicit Non-Goals
- Do NOT implement replacement modulation detection
- Do NOT add "modulation unavailable" insight (absence is signal)
- Do NOT add chord detection fallback

### Acceptance Criteria
- [ ] `analyze_midi()` returns no `modulations` field
- [ ] `handle_analyze` creates 0 modulation insights
- [ ] `handle_analyze` creates 0 Roman numeral insights when `chords` is empty
- [ ] Real piano fixture: only Key + Rhythm insights persisted
- [ ] All existing tests pass

---

## PR B — Evaluated Audio Pulse Evidence (P0)

### Objective
Replace MIDI-metadata tempo/beat with audio-derived beat grid. Enable syncopation, metrical rhythm, and downstream metrical analysis.

### Files Touched
- `backend/domain/capabilities.py` — Modify `handle_analyze` to accept audio version + run beat tracking
- `backend/analyze.py` — Update `analyze_midi()` signature to accept `beat_grid: BeatGrid | None`
- `backend/analyze.py` — Update `_midi_rhythm()` to compute syncopation when beat grid available
- `backend/engines/registry.py` — Ensure `get_beat_engine()` accessible
- `backend/domain/capabilities.py` — Update `handle_analyze` job parameters to include `audio_version_id`

### Benchmark First (Required Before Merge)
Compare on existing scored corpus (MAESTRO excerpts + any annotated beat data):
| Engine | Beat F1 | Downbeat F1 | Tempo RMSE | CPU Time (3 min) |
|--------|---------|-------------|------------|------------------|
| librosa (current) | — | N/A | — | ~5s |
| Beat This! | — | — | — | ~20s |
| All-In-One | — | — | — | ~60s |

Select default based on evidence; make configurable via `BEAT_ENGINE`.

### Behavior Changed
- `tempo` insight → from audio beat tracking (not MIDI metadata)
- `time_signature` insight → from downbeat pattern (if engine provides)
- `rhythm` insight → includes `syncopation_ratio` when beat grid available
- `chord`/`roman_numeral` timing → can map to beats (not just quarter notes)
- Modulation detection (if ever re-added) → uses correct tempo

### Migration Concerns
- `handle_analyze` currently takes only MIDI version — add optional `audio_version_id`
- Job parameter schema change: add optional `audio_version_id`
- Backward compatible: if no audio version, fall back to current behavior (with warning)

### Explicit Non-Goals
- Do NOT change transcription routing
- Do NOT implement downbeat detection if engine doesn't provide (librosa fallback = no downbeats)

### Acceptance Criteria
- [ ] `handle_analyze` accepts optional `audio_version_id` parameter
- [ ] When audio provided: tempo from beat tracking, syncopation computed
- [ ] When audio NOT provided: falls back to MIDI metadata (current behavior)
- [ ] Real piano fixture: tempo ≈ actual BPM (not 120), `syncopation_available=true`
- [ ] Beat engine configurable via `BEAT_ENGINE` env (librosa default, beat_this optional)
- [ ] Benchmark results documented in PR

---

## PR C — Post-Transkun Analysis Diagnostic (P0)

### Objective
Quantify which symbolic analyses improve purely from better transcription. No algorithm changes — diagnostic only.

### Prerequisite
#229 merged (Transkun routing for `solo_piano` profile).

### Method
Run the **exact same analysis pipeline** on the same real-piano audio with two transcriptions:

| Transcription | Notes | Chords | RNs | Melody | Modulations | Tempo (from MIDI) |
|---------------|-------|--------|-----|--------|-------------|-------------------|
| Basic Pitch | 234 | 0 | 5 (wrong) | None | 4 false | 120 (default) |
| Transkun | ? | ? | ? | ? | ? | 120 (default) |

### Measurements
For each transcription, record:
- `chords` count and quality (non-empty? spelled qualities?)
- `roman_numerals` count and correctness (in detected key?)
- `melody` — None or extracted?
- `modulations` count (should be 0 after PR A)
- `key.confidence` — correlation coefficient
- `rhythm` — density, syncopation (if PR B done)

### Decision Gate
If Transkun MIDI yields:
- **Non-empty chords with spelled qualities** → music21 symbolic path works for piano; prioritize symbolic harmony
- **Empty chords** → need audio-native harmony (chordia) even for piano; PR D becomes P0
- **Melody extracted** → skyline works on clean MIDI; keep
- **Still false modulations** → confirms tempo source is the problem (PR B needed)

### Deliverable
Markdown report in PR: `docs/analysis/POST_TRANSKUN_DIAGNOSTIC.md` with table above + recommendations.

### Acceptance Criteria
- [ ] Both transcriptions analyzed through identical pipeline
- [ ] Results table documented
- [ ] Clear recommendation for PR D priority and harmony strategy

---

## PR D — Harmony OSS Bakeoff (P1)

### Objective
Compare plausible OSS/audio/symbolic harmony paths on actual annotated data. No production integration until evidence.

### Candidates to Evaluate
| Engine | Type | Input | Output | License |
|--------|------|-------|--------|---------|
| music21 (current) | Symbolic | MIDI (Transkun) | Chords, RNs, key | BSD |
| chordia | Audio-native | Audio | Chords, key | MIT |
| Essentia KeyExtractor | Audio-native | Audio | Key | AGPL |
| Essentia Chordino (Vamp) | Audio-native | Audio | Chords | AGPL |

### Evaluation Corpus
- MAESTRO excerpts (solo piano, scored)
- Annotated chord corpora (e.g., Beatles, Billboard, or Jazz standards if available)
- Mixed-genre real audio (if ground truth exists)

### Metrics
| Metric | Target |
|--------|--------|
| Chord symbol accuracy (root + quality) | >70% |
| Key accuracy | >80% |
| Tempo alignment (chord boundaries vs beat grid) | <200ms |
| CPU time (3 min track) | <30s |

### Decision Matrix
| Scenario | Decision |
|----------|----------|
| chordia beats music21 on piano + works on non-piano | Adopt chordia as default for all profiles |
| music21 on Transkun beats chordia on piano, chordia wins on non-piano | Profile routing: solo_piano→music21, others→chordia |
| Both weak | Document gaps; keep both as options; defer |

### Migration Concerns
- chordia output format differs → normalize in engine adapter
- Roman numerals only from symbolic path → explicit gap in provenance
- Profile routing parameter needed (`analysis_profile` parallel to `transcription_profile`)

### Explicit Non-Goals
- Do NOT integrate any engine to production in this PR
- Do NOT implement Roman numerals for audio-native path
- Do NOT add genre classifier

### Acceptance Criteria
- [ ] All candidates run on evaluation corpus
- [ ] Metrics table documented in `docs/analysis/HARMONY_BAKEOFF.md`
- [ ] Clear recommendation for production harmony strategy

---

## PR E — Normalized MusicalEvidence Contract + Dual Migration (P1)

### Objective
Introduce typed evidence envelope replacing generic `Insight` for analysis output. Enable querying, relationships, and temporal mapping.

### Schema Design: Common Envelope with Discriminated Union

```typescript
// Single table, typed envelope
MusicalEvidence = {
  id: UUID
  kind: EvidenceKind  // "key_region" | "chord" | "beat" | "downbeat" | "section" | "melody" | "cadence" | "modulation" | "rhythm" | "dynamics" | ...
  sourceArtifactId: UUID
  scope: {
    seconds?: Range      // performance time
    beats?: Range        // metrical time
    measures?: Range     // notation time
    noteIds?: string[]   // symbolic references
  }
  value: EvidenceValue   // discriminated union by kind
  confidence?: number    // calibrated [0,1] or null
  provenance: {
    engine: string
    version: string
    method: string
  }
}

// EvidenceValue discriminated by kind:
type EvidenceValue =
  | { kind: "key_region"; tonic: string; mode: string; strength: number }
  | { kind: "chord"; root: string; quality: string; inversion?: number }
  | { kind: "beat"; position: number; isDownbeat: boolean; bpm: number }
  | { kind: "downbeat"; position: number; measureNumber: number }
  | { kind: "section"; label: string; boundaryConfidence: number }
  | { kind: "melody"; pitch: number; start: number; end: number; salience: number }
  | { kind: "cadence"; type: string; chords: string[]; strength: number }
  | { kind: "modulation"; fromKey: string; toKey: string; pivotChord?: string }
  | { kind: "rhythm"; density: number; syncopation?: number }
  | { kind: "dynamics"; loudnessLufs: number }
  | ...
```

### Files Touched
- `backend/schemas/export/MusicalEvidence.schema.json` — NEW: typed evidence schema
- `backend/domain/models.py` — Add `MusicalEvidence` SQLAlchemy model (single table, JSONB `value`)
- `backend/domain/repositories.py` — Add `EvidenceRepo` with typed queries
- `backend/domain/capabilities.py` — New `_create_evidence()` alongside `_create_insight()` (dual-write)
- `backend/analyze.py` — Return `EvidenceBundle` (list of `MusicalEvidence`) alongside `AnalysisResult`
- `backend/domain/api.py` — New `/versions/{id}/evidence` endpoint (typed, filterable)

### Migration Strategy: Dual-Read / Dual-Write
1. **Phase 1 (this PR)**: Write to both `Insight` and `MusicalEvidence`. Read from `Insight` for Inspector/Ask.
2. **Phase 2 (later)**: Migrate Inspector to `/evidence` endpoint. Keep `/insights` as view.
3. **Phase 3 (later)**: Drop `Insight` table after full migration.

### Phrase/Motif/Tension/Harmonic-Function: Deferred
These higher-level interpretations are **NOT in P0/P1**. They are particularly tempting areas for bespoke rules. Our first target is boring but trustworthy:

| P0/P1 Target Evidence | Why |
|----------------------|-----|
| tempo / beat / downbeat | PR B delivers |
| key | music21 / chordia |
| chords | music21 (Transkun) or chordia |
| melodic/pitch evidence | PR C diagnostic → PR D decision |
| sections | All-In-One (profile-gated) |
| dynamics / density | Essentia / pretty_midi |

If these are reliable and temporally scoped, the LLM can already provide surprisingly useful higher-level explanation without us writing homemade "tension detectors."

### Acceptance Criteria
- [ ] `MusicalEvidence` model with envelope + discriminated union `value`
- [ ] `EvidenceRepo` with CRUD + query by kind/time/confidence
- [ ] `handle_analyze` dual-writes Insight + MusicalEvidence
- [ ] `/versions/{id}/evidence` returns typed evidence with filters
- [ ] `/versions/{id}/insights` still works (unchanged)
- [ ] Real piano fixture: evidence rows for Key, Rhythm (no modulations, no RNs after PR A)
- [ ] Schema validates all current engine outputs

---

## Blocker Decisions (Owner Judgment Not Required for P0 Start)

| Blocker | Status | Resolution |
|---------|--------|------------|
| **Essentia AGPL** | Deferred | Not needed for PR A/B/C. PR D evaluates MIT alternatives first. |
| **Transkun Docker deps** | Owned by #229 | PR C waits for #229 merge. |
| **chordia PyTorch on ARM** | Deferred | PR D evaluates; if fails, music21+Transkun is piano path. |
| **All-In-One NATTEN** | Deferred | Profile-gated; not P0. |
| **Profile parameter UX** | Deferred | Manual `transcription_profile` / `analysis_profile` API params sufficient for P0. |
| **Evidence migration** | Dual-write in PR E | No flag-day replacement. |

---

## PR Order Summary

| Order | PR | Priority | Est. Effort | Value |
|-------|-----|----------|-------------|-------|
| A | Analysis Truthfulness Cleanup | P0 | 1 day | Removes actively misleading output (4 false modulations, contradictory RNs) |
| B | Evaluated Audio Pulse Evidence | P0 | 3 days | Real tempo, syncopation, metrical grid; fixes modulation root cause |
| C | Post-Transkun Analysis Diagnostic | P0 | 1 day | Evidence-driven decision: does better transcription fix symbolic analysis? |
| D | Harmony OSS Bakeoff | P1 | 4 days | Audio-native vs symbolic on scored data; no integration until evidence |
| E | Normalized MusicalEvidence Contract | P1 | 5 days | Foundation for all future analysis; common envelope, dual migration |

**Total**: ~14 days for P0+P1 foundation. Each PR independently shippable.

---

## Non-Goals for This Plan

- ❌ Genre classifier (manual profile params sufficient)
- ❌ Custom ML models (use OSS)
- ❌ RAG/vector DB for evidence (SQL + typed envelope sufficient)
- ❌ Agent framework (Ask is grounded LLM)
- ❌ Real-time streaming (batch first)
- ❌ Phrase/motif/tension/harmonic-function in P0 (deferred — LLM can derive from trustworthy primitives)