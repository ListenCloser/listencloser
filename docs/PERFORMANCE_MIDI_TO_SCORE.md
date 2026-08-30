# Performance MIDI → Score OSS decision

Status: **execution decision, not a benchmark report**  
Owner issue: #700  
Related: #498, #511, #517

## Product boundary

The canonical performance MIDI that backs Piano Roll is evidence and must stay faithful to the performance. Readable Score is a separate derived representation.

```text
audio
  → piano AMT (Transkun for solo piano)
  → canonical performance MIDI        ← Piano Roll / evidence authority
  → performance-to-score interpreter  ← this decision
  → notation MIDI + MusicXML           ← Score / OSMD / score playback
```

Do **not** repair a bad Score by destructively quantizing or rewriting canonical performance MIDI. The score interpreter may normalize onset/release timing, infer meter/voices/staves, split hands, simplify durations, and add notation-specific structure, but those changes belong only to the derived score artifact and must carry provenance.

## Why this is the current bottleneck

The existing `Music21NotationEngine` is an OSS-shaped adapter but does not actually delegate the difficult interpretation boundary to OSS. It still invokes repository-owned adaptive quantization, rhythmic-grid selection, grand-staff assignment, tie repair, and related notation code. In practice, the Piano Roll can therefore be acceptable while Score remains visibly noisy or unreadable.

The near-term goal is not to perfect an evaluation framework. It is to put a credible OSS performance-MIDI→score implementation into the real worker, inspect real product output, ship the better behavior if it clears a small safety gate, and then use formal evaluation to confirm or overturn that choice.

## Candidate map

| Candidate | What it owns | Operational readiness | License / distribution | Decision |
| --- | --- | --- | --- | --- |
| **MuseScore Studio 4** | MIDI import interpretation, notation model, MusicXML/MIDI export | High. Maintained desktop/CLI application with current Linux x86_64 and ARM64 AppImages. Headless converter can be isolated behind the existing engine subprocess seam. | GPL-3.0 external executable. Pin binary + source release; do not link its code into the backend. | **Integrate first as the operational baseline.** |
| **PM2S** (`cheriell/PM2S`) | Learned performance-MIDI→score conversion using neural beat tracking | Medium. Pretrained inference exists, but reference environment is Python 3.8 / PyTorch 1.12 and has aged. | MIT. | **Next selective challenger**, especially for learned beat/hand/score interpretation. Do not assume its full quantizer wins until product inspection. |
| **MIDI2ScoreTransformer** (`TimFelixBeyer/MIDI2ScoreTransformer`) | End-to-end transformer performance-MIDI→detailed score | Medium-low operationally, high research quality signal. Python 3.11, released checkpoint, but requires custom `music21`, ScoreTransformer, manual MUSTER fork, and MuseScore. | Repository does not currently expose a clear top-level software license in the checked tree; checkpoint/use terms need explicit verification before production. | **Quality challenger after licensing/dependency gate.** Its ISMIR 2024 results make it the learned system most worth displacing the baseline with if deployable. |
| **qparse** | Symbolic rhythm transcription / hierarchical quantization using weighted tree automata | Medium-low for this product. Mature research code and explicit MIDI→MEI/quantized-MIDI tools, but requires rhythm grammars/configuration and assumes meter/tempo knowledge in examples. | Verify exact current source license before production packaging. | **Reference / targeted rhythm challenger**, not first production path. |
| **piano-a2s** (`wei-zeng98/piano-a2s`) | End-to-end piano audio→score | Low for production. Upstream explicitly says it is not yet applicable to real-world scenarios; roughly five-bar / 12-second input constraints and possible illegal Kern output. | Apache-2.0. | **Research only.** Do not replace the working Transkun performance-MIDI boundary with it. |
| **Beat-conditioned transformer quantizers (2025–2026 research direction)** | Performance MIDI + explicit beat/downbeat evidence → score | Architecturally attractive because ListenCloser already has a strong pulse seam, but no production-runnable public code + weights + acceptable license was verified in this pass. | Unknown per implementation. | **Watchlist.** Revisit when a runnable OSS release exists. |

Primary sources:

- MuseScore releases: <https://github.com/musescore/MuseScore/releases>
- PM2S: <https://github.com/cheriell/PM2S>
- MIDI2ScoreTransformer: <https://github.com/TimFelixBeyer/MIDI2ScoreTransformer>
- qparse: <https://qparse.gitlabpages.inria.fr/>
- piano-a2s: <https://github.com/wei-zeng98/piano-a2s>

## Current execution choice

### 1. MuseScore is the first production-shaped baseline

PR #707 adds `MuseScoreNotationEngine` without changing the default. It feeds untouched canonical performance MIDI to a pinned MuseScore Studio runtime and asks the application to export both derived notation MIDI and MusicXML. The worker image itself must prove a tiny MIDI→MusicXML conversion on native amd64 and arm64 before the candidate is considered runnable.

This choice is deliberately about **operational baseline quality**, not a claim that MuseScore is the best research system. It has three advantages now:

1. it can own a much larger portion of the current bespoke score-interpretation problem immediately;
2. it produces the formats the product already consumes, so the integration is thin and reversible;
3. it provides a stable reference output against which learned systems can be judged without first building another evaluator.

Important limitation: MuseScore's MIDI import currently performs its own temporal interpretation. It does **not** consume ListenCloser's Beat This beat/downbeat grid through the adapter, so provenance must say `beat_grid_consumed=false`. We should not pretend the new pulse model fixes score quantization unless a later score engine actually consumes that evidence.

### 2. PM2S is a component challenger, not an automatic whole-pipeline replacement

PM2S is directly on the right problem boundary and is MIT-licensed. It remains worth running after the baseline. However, its old reference environment raises maintenance risk, and contemporary downstream use of Transkun→PM2S reports enough onset drift to treat the quantizer cautiously while still finding some hand-splitting behavior useful. That downstream report is anecdotal evidence, not a benchmark result.

If PM2S materially improves hand assignment or rhythmic readability, prefer a thin adapter or selective component reuse over reintroducing equivalent bespoke heuristics.

### 3. MIDI2ScoreTransformer is the highest-priority quality challenger once legally runnable

The 2024 transformer is a stronger research match for the full task: it directly predicts note values, rhythmic structure, staff assignment, and additional notation details from performance MIDI and reports improvements on end-to-end score metrics. The problem is deployability, not relevance. Before any production integration:

- obtain an explicit software license / permission for the repository code;
- verify checkpoint redistribution/use terms;
- inventory the custom forks and decide whether they can be isolated rather than imported into the main backend environment;
- prove CPU inference latency/memory on the current worker class.

If those gates pass, this should be compared against MuseScore before investing in more custom notation heuristics.

## Promotion gate: product first, evaluator second

A candidate does **not** need a new benchmark framework before it can change product behavior. The first promotion gate is intentionally small:

1. runs in the production-shaped worker with pinned/reproducible dependencies;
2. preserves canonical performance MIDI unchanged;
3. emits valid notation MIDI + MusicXML that OSMD and score playback can consume;
4. on the canonical real-piano Work plus a handful of fixed clips, has no catastrophic note loss, timing drift, or broken measure structure;
5. side-by-side inspection is clearly no worse—and preferably visibly better—than the current Score for rhythmic readability, ties/durations, staff assignment, and density;
6. records exact engine/version/provenance and has an immediate rollback path.

If these hold, **ship the candidate**. Then formal paired evaluation under #498/#517 should verify the choice, identify failure classes, and determine whether PM2S/MIDI2ScoreTransformer or a later OSS system should replace it.

## What formal evaluation should eventually answer

Evaluation is follow-up evidence, not the blocker for #707. Reuse existing infrastructure and standard metrics before writing new framework code. The eventual suite should separate:

- note preservation from performance MIDI to notation;
- onset/offset quantization error relative to reference score timing;
- rhythm spelling / duration / tie complexity;
- meter and measure-boundary correctness;
- voice and staff assignment;
- structural score similarity (MUSTER/MV2H or equivalent standard OSS metrics where appropriate);
- operational cost: wall time, CPU/RAM, image size, failure rate;
- human/product preference on a small canonical corpus.

Every evaluated candidate must end in **SHIP / KEEP / REJECT**. A benchmark PR with no production consequence is incomplete.

## Deletion policy after promotion

Once an OSS score interpreter is the default and has survived a bounded rollback window, delete repository-owned notation machinery that no longer adds product-specific value. Likely deletion targets include superseded portions of:

- `backend/notation/quantize.py`;
- `backend/notation/staffing.py`;
- `notation_midi_from_performance` / `adaptive_notation_from_performance` paths;
- duplicate tie/duration/grid heuristics now owned by the selected engine.

Keep only product-specific glue: artifact lineage, immutable performance MIDI, provenance, engine selection, playback alignment, rendering contract, and genuinely necessary normalization around OSS boundaries.

## Decision rule going forward

> A credible runnable OSS score system gets a production-shaped adapter before ListenCloser writes more score heuristics. Bespoke notation logic must justify itself by beating or filling a demonstrated gap in the OSS baseline.
