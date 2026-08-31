# Learned score reconstruction: 2026 production-readiness decision

Parent product owner: #498. Strategy owner: #945. First implementation owner: #953.

## Decision

ListenCloser keeps **performance MIDI** and **readable Score** as separate symbolic products:

```text
audio
├─> performance-note model -> canonical performance MIDI -> Piano Roll/evidence
└─> score reconstruction -> score-oriented representation -> MusicXML -> Score/evidence
```

For explicit solo piano, TransKun remains the performance-MIDI owner. Score reconstruction may consume that MIDI or branch directly from audio, but it must never overwrite the performance representation.

### Experimental-selection policy

The current phase is **ship candidates first, canonize later**.

A credible learned model may enter the runtime as an explicit experimental Score choice when pretrained artifacts are available, its terms permit the intended use, its inference can be bounded behind a clean adapter, and it produces a useful score representation on normal product inputs. We do not require a new generic benchmark program before onboarding it.

This is not a permanent fallback architecture. Engines are explicitly selected and provenance is preserved. If an experimental engine fails, that selected path fails rather than silently substituting another score interpreter. Once product/evaluation evidence establishes a winner for a route, canonize it and delete superseded runtime alternatives.

MuseScore remains the default baseline during this comparison phase.

## Representation model

For MIDI-conditioned score reconstruction, use the literature-grounded distinction:

```text
performance MIDI
    # physical/performed onset, offset, pitch, velocity
    ↓ score reconstruction
score MIDI
    # metrical/notation-oriented timing and score metadata
    ↓ notation import / completion
MusicXML
    # rich score representation rendered by OSMD
```

The current `NotationResult.notation_midi` field can carry score MIDI without forcing an immediate schema rename. It must not become canonical Piano-Roll evidence.

## Current candidate decisions

### Rubato (2026) — QUALITY TARGET / WATCH RELEASE

Rubato is the strongest current direct audio -> readable piano-score target. It predicts a timestamped score representation directly from audio and recent evaluation reports it ahead of the tested performance-MIDI cascades for notation quality.

Current public distribution is restricted. Do not copy/repackage the current demo/model release into the product. Onboard promptly when an adequately open/deployable checkpoint, package, or service becomes available.

### MIDI2ScoreTransformer (2024) — MODULAR QUALITY TARGET / WATCH LICENSE

MIDI2ScoreTransformer remains the strongest modular performance-MIDI -> detailed-score target found in the current literature and fits the TransKun-first piano architecture well.

Operational positives include Python 3.11 code, a released checkpoint, and prediction of richer notation attributes than a simple rhythm quantizer. Current blockers are licensing: the repository has no explicit code license and the released checkpoint cannot be bundled/mirrored because of its training-data restrictions.

Do not train a replacement checkpoint by default. Revisit immediately if upstream licensing/distribution becomes usable.

### joint-apt-epr (ICLR 2026) — INVESTIGATE IF CHECKPOINT TERMS ARE CLEAN

The repository is Apache-2.0 and publishes a checkpoint link. The current release is research-shaped: inference contains corpus/path/device assumptions and the README describes the code as a skeleton release.

Packaging friction alone is not a rejection. If checkpoint terms are acceptable and a bounded arbitrary-MIDI inference adapter can be extracted without reconstructing the research algorithm, it is a valid future challenger.

### piano-a2s (IJCAI 2024) — LOW PRIORITY FOR PRODUCT RUNTIME

Apache-2.0 with pretrained models, but upstream documents constraints that conflict with normal full-recording use: five-bar inputs, roughly 12-second maximum audio due to memory, and occasional invalid Kern requiring post-processing.

Keep as research reference unless a successor removes those constraints.

### PM2S (ISMIR 2022) — FIRST SHIPPABLE LEARNED CHALLENGER

PM2S is MIT-licensed code with public pretrained-model inference and directly models performance-MIDI -> score-MIDI conversion. It predicts learned beat/meter/quantization plus score-related metadata such as hand, key, and time signature.

It is not assumed to be the final winner. More recent evaluation favors MIDI2ScoreTransformer for detailed written notation, and newer applications provide mixed evidence about PM2S quantization quality. That is precisely why PM2S enters as an **explicit challenger**, not a canonical replacement.

Initial path:

```text
TransKun -> performance MIDI -> PM2S -> score MIDI -> MuseScore MIDI import -> MusicXML
```

The MuseScore stage is not a passive serializer: MIDI import may make additional notation decisions. Preserve the PM2S score MIDI as the learned intermediate and record the MuseScore import stage in provenance so later comparison can distinguish PM2S reconstruction from downstream notation changes.

Implementation: #953.

### HookKern / SheetSage-A2S (ACMMM 2026) — FUTURE LEAD-SHEET ROUTE

MIT code, public checkpoints, contemporary pretrained audio features, and documented Docker/inference make this a strong deployable 2026 system. Its popular-music target is melody + chords / lead-sheet transcription rather than a full piano score.

Treat it as a future `lead_sheet` representation rather than a piano Score replacement.

### 2026 beat-conditioned Transformer quantization — WATCH CODE/CHECKPOINT RELEASE

Recent beat-conditioned Transformer work is architecturally attractive for `TransKun performance MIDI + Beat This beats/downbeats -> score rhythm`, but no production-ready public implementation/checkpoint has yet been established. Onboard if a usable release appears; do not reimplement the paper prematurely.

## Admission gate for experimental engines

A model may join the explicit runtime selector when:

1. **Artifacts exist** — pretrained weights or a usable service are available.
2. **Terms are usable** — code and model/service terms permit the intended deployment/evaluation mode.
3. **Inference is bounded** — normal product inputs can run behind a clean adapter without reimplementing the algorithm.
4. **Output is meaningful** — valid score/score-intermediate artifacts can reach the existing Score UI.
5. **Identity is pinned** — source revision, checkpoint/model identity, dependencies, and provenance are reproducible.
6. **No authority leak** — derived score artifacts never replace canonical performance MIDI.
7. **No silent fallback** — the selected engine either produces its result or reports failure.

This gate is intentionally lighter than canonical promotion.

## Canonical-promotion gate

Once multiple paths are runnable, select the canonical route using the smallest useful evidence:

- fixed real piano failures from the product;
- obvious structural sanity/event retention;
- valid MusicXML, OSMD render, playback, and seek behavior;
- score-structure/OMR metrics where aligned references legitimately exist;
- small human A/B for readability/edit effort when useful.

Do not turn evaluation infrastructure into a prerequisite to seeing the models in the product.

## Short-term execution

1. Ship PM2S as an explicit score-MIDI challenger (#953).
2. Keep MuseScore-direct as the baseline choice during comparison.
3. Preserve `performance MIDI -> score MIDI -> MusicXML` provenance and artifacts.
4. Add a small Score-engine selector analogous to transcription-engine selection.
5. Compare real outputs after the path is functional.

## Long-term execution

Onboard stronger pretrained systems opportunistically rather than training our own by default:

1. Rubato when deployable/open distribution exists.
2. MIDI2ScoreTransformer when code/checkpoint licensing permits deployment.
3. joint-apt-epr if its checkpoint terms are acceptable and inference extraction is bounded.
4. new MIREX/ISMIR/ICASSP/ICLR 2026+ score systems meeting the admission gate.
5. HookKern as a separate lead-sheet representation.

The durable architecture is semantic rather than tied to one cascade: performance evidence and score evidence remain separate, while future score engines may consume performance MIDI or branch directly from audio.