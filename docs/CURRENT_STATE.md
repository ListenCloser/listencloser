# Current State Snapshot

> **Purpose:** Fast orientation for implementation agents. This file summarizes current `main` and the machine-readable capability registry; it is not the strategic roadmap. Read `MASTER_SPEC.md` for direction and verify the deployed release SHA before making production claims.
>
> **Snapshot date:** August 2026.

---

## 1. Product shell

Current merged workspace direction:

- persistent Library / Work lifecycle,
- durable background processing,
- global transport,
- independent representation vs playback-source selection,
- shared selection across representations,
- contextual Analysis Inspector,
- synchronized analysis annotations,
- Compare support,
- persisted analysis/reload behavior,
- deletion/work-switch transport cleanup.

### Current primary representations

- Waveform,
- Piano Roll,
- Score,
- Spectrogram,
- Compare.

Spectrogram was added as a client-side synchronized performance-time representation with shared seek/selection/playhead behavior.

### Current playback sources

Product labels:

- Original,
- Transcription,
- Score.

Actual availability depends on persisted artifacts for the active Work.

---

## 2. Analysis capability matrix

The exact authority is `backend/config/capabilities.json`. The following is a convenience summary only.

### Production

#### Key

- input: MIDI
- engine: music21
- scope: global key only
- exposed: Inspector + Ask
- registry benchmark: GuitarSet key accuracy 0.8
- must not be interpreted as local key regions/modulations.

#### Chords

- input: audio
- engine: lv-chordia
- exposed: Inspector + annotations + Ask
- registry benchmark: GuitarSet chordal subset root accuracy 0.787
- monophonic/no-chord regions may be withheld.

#### Roman numerals

- input: derived
- engine: theory interpreter
- requires trusted chord + trusted key
- exposed: Inspector + annotations + Ask
- registry evaluation is **oracle** theory mapping, not end-to-end audio accuracy.

#### Harmonic function

- input: derived
- engine: theory interpreter
- requires trusted chord + trusted key
- exposed: Inspector + annotations + Ask
- similarly depends on upstream chord/key correctness.

#### Tempo / audio tempo

- input: audio
- engine category: beat engine
- exposed in Inspector/Ask.

#### Time signature

- input: MIDI
- engine: music21
- exposed in Inspector/Ask.

#### Rhythm

Current deterministic production evidence includes:

- temporal note/onset density,
- observed rest/onset-gap spans,
- beat-relative onset distribution,
- strongest temporal activity findings/annotations.

Do **not** call the beat-phase distribution a validated syncopation metric.

### Experimental

#### Melody

- input: MIDI
- engine: LStoM
- validation domain: POP909 / pop-arranged symbolic MIDI
- registry held-out F1: 0.768; precision 0.720; recall 0.839
- model: ~2.5M parameter BiLSTM, ~9.66 MB, CPU inference
- broad classical/general performance domain is not formally validated.

Experimental melody-derived product evidence currently includes:

- highest/lowest register events,
- interval summary (stepwise/leap/repeated-note ratios),
- conservative ascending/descending contour spans,
- dense/sparse melody-activity spans.

These are deterministic derivations from LStoM output and inherit its domain limitations. Do not treat them as ground-truth phrasing, motifs, emotion, or universal melody analysis.

### Evaluation-only / withheld

#### Structure / section detection

- evaluation-only,
- current reproducible baseline: librosa CENS + recurrence + novelty + peak-pick structural-boundary candidate pipeline,
- no product exposure until lawful labeled audio evaluation establishes useful boundary quality,
- semantic Verse/Chorus/etc. labels are not trusted.

The capability registry may still contain historical `allin1` engine metadata for structure. Treat this as registry/documentation drift if the active evaluation baseline has changed; do not infer production availability from it.

#### Cadence

- withheld,
- DCML-Mozart F1 ~0.266 in current registry,
- no Inspector/annotations/Ask exposure.

#### Key regions / modulation

- withheld,
- current registry boundary accuracy ~0.188,
- no product exposure.

#### Voice leading

- withheld.

#### Harmonic rhythm

- currently withheld in the registry.
- The registry reason references an unreliable chord stream and may be stale now that lv-chordia is production; **do not promote automatically**. Re-evaluate the task/metric first.

#### Motif discovery

- custom interval matcher retained as evaluation-only,
- no production exposure until benchmarked/justified.

#### Skyline melody baseline

- evaluation-only / deprecated as production path,
- retained only for comparison against LStoM.

---

## 3. Current engine architecture

Verify exact registry/config at implementation time, but current major paths are:

```text
Audio
├── transcription routing → MIDI / note entities
├── audio beat engine → tempo / beat evidence
├── lv-chordia → chord spans
└── browser decoding → Waveform / Spectrogram

MIDI
├── music21 → global key / time signature / theory utilities
├── LStoM → melody-note evidence
├── deterministic rhythm analysis
└── notation pipeline → MusicXML / score-derived playback

trusted chords + trusted key
→ theory interpreter
→ Roman numerals / harmonic function
```

Transcription historically routes Basic Pitch and Transkun depending on profile. Inspect `backend/engines/registry.py` and current capability/profile code before changing defaults.

---

## 4. Important recent merged work

Recent relevant PR sequence includes:

- #318 — approved melody register findings visible in Inspector.
- #319 — narrow Ruff repair.
- #320 — synchronized Spectrogram representation.
- #322 — beat-relative onset distribution.
- #323 — continuous expired worker-lease recovery; fixed queue-health/import blockage.
- #324 — evaluation-only librosa structure baseline.
- #325 — temporal Rhythm evidence annotations.
- #326 — experimental melody interval/contour/activity findings.

Older custom rhythm PR #316 was closed as superseded. Old CI hygiene PR #297 was closed as stale/already incorporated.

---

## 5. Infrastructure snapshot

Current intended topology:

```text
Vercel / Next.js
  → authenticated proxy
  → FastAPI on Oracle VM
  → Supabase Auth/Postgres/private Storage

Oracle worker
  → Supabase durable queue/storage
  → music engines
```

Current DevEx/operations foundation includes:

- GitHub Actions,
- generated OpenAPI TypeScript contracts,
- real-stack Playwright coverage,
- production smoke verification,
- CodeQL / dependency review / secrets scanning / Semgrep-style security checks,
- OpenTelemetry instrumentation,
- Grafana Cloud traces,
- exact-release/deployment metadata.

Do not assume a CI failure is pre-existing/flaky; inspect evidence.

---

## 6. Current strategic pause / next research gate

Do not continue adding many bespoke Analysis micro-features by default.

The next strategic program is issue #327 / `MASTER_SPEC.md` §20:

1. music foundation representation bakeoff,
2. style/instrument/semantic tagging bakeoff,
3. modern source separation bakeoff,
4. beat/downbeat/meter bakeoff.

UI/UX redesign (#328) and platform/DevEx review (#329) can proceed as separate bounded tracks without changing analysis truthfulness.

---

## 7. Drift checklist

When this file disagrees with main:

1. check `backend/config/capabilities.json`,
2. check engine registry/config,
3. check recent merged PRs,
4. check deployed release SHA if production behavior matters,
5. update this snapshot in the same/follow-up docs PR.

Never use a stale snapshot to override runtime evidence.
