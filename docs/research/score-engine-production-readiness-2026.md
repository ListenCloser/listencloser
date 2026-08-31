# Learned score reconstruction: 2026 production-readiness decision

Parent product owner: #498. Execution owner: #945.

## Decision

ListenCloser keeps **performance MIDI** and **readable Score** as separate symbolic products:

```text
audio
├─> performance-note model -> canonical performance MIDI -> Piano Roll/evidence
└─> score reconstruction -> notation-native representation -> MusicXML -> Score/evidence
```

For explicit solo piano, TransKun remains the performance-MIDI owner. Score reconstruction may consume that MIDI or branch directly from audio, but it must not overwrite the performance representation.

### Production-selection policy

We do **not** want a permanent runtime fallback tree between notation engines. One engine should own Score for a validated route. A challenger may run experimentally while proving operational viability, but promotion means replacing the previous route rather than layering another silent fallback.

MuseScore therefore remains the single current production score engine until a learned challenger clears the ship gate. Once a learned engine clears the gate for solo piano, it should become the sole normal `solo_piano` score path; MuseScore can remain only as an explicit rollback during rollout and should leave the normal hot path afterward.

## Current candidate decisions

### Rubato (2026) — TARGET / BLOCKED ON DISTRIBUTION

Current reported evidence makes Rubato the quality target for piano notation. It directly predicts a timestamped score from audio and recent external evaluation reports it as the strongest notation system among the compared end-to-end pipelines. Its own paper also reports a notation advantage over performance-MIDI cascades even when those cascades receive oracle performance MIDI.

Operational blocker: no reproducibly deployable public checkpoint/package with clearly acceptable production-use terms has been verified. Do not reimplement the paper in-product merely to remove this blocker.

### MIDI2ScoreTransformer (2024) — TARGET / BLOCKED ON LICENSE

This remains the strongest modular performance-MIDI -> detailed-score candidate found in the current literature and is especially attractive because it can consume the existing TransKun performance MIDI.

Operational positives:
- Python 3.11 code;
- released checkpoint;
- direct performance-MIDI -> detailed score modeling;
- reported improvement over older neural and HMM approaches.

Blocker: the public repository currently declares no license. Public source/checkpoint availability is not sufficient permission for a production dependency. Do not vendor or deploy it until explicit usable terms are available.

### joint-apt-epr (ICLR 2026) — REJECT FOR CURRENT PRODUCTION

The repository is Apache-2.0 and publishes a checkpoint link, but the current upstream release is explicitly a skeleton release rather than a production inference package. Current inference code contains corpus/path/device assumptions and the README says detailed instructions are still forthcoming.

Decision: do not spend a product branch reconstructing the research environment. Revisit only after upstream publishes a clean inference path/checkpoint contract or another implementation proves substantially simpler.

### piano-a2s (IJCAI 2024) — REJECT FOR CURRENT PRODUCTION

Apache-2.0 with pretrained models, but upstream explicitly says the model is not applicable to real-world scenarios yet:
- input constrained to 5 bars;
- maximum audio length about 12 seconds due to memory;
- occasional illegal Kern output requiring post-processing.

Those limitations conflict directly with ListenCloser's normal full-recording workflow.

### PM2S (ISMIR 2022) — KEEP AS REFERENCE, DO NOT PROMOTE

PM2S is MIT and runnable, but the original environment pins Python 3.8-era Torch/Numpy. More importantly, a current MIT application (`mqtik/muse`) that uses TransKun + PM2S reports dropping PM2S's learned quantization because it measured roughly 164 ms mean onset drift (p95 about 385 ms). That application uses PM2S only for hand/key/time classification rather than as its score-quantization owner.

This makes PM2S useful prior art but not a justified replacement for the current MuseScore production path.

### HookKern / SheetSage-A2S (ACMMM 2026) — ROUTE-SPECIFIC RESEARCH

MIT code, public checkpoints, and contemporary real-audio training make this operationally attractive, but its popular-music target is melody + chords / lead-sheet transcription rather than a full piano score. Treat it as a possible future `lead_sheet` representation, not the replacement for the piano Score path.

## Ship gate for the next learned score engine

Candidate selection may rely on reported literature. We do not require a new benchmark program before trying a model.

Before production promotion, however, the candidate must satisfy all of:

1. **Legal** — code and weights/service terms permit intended production use.
2. **Reproducible** — model identity/checkpoint and dependencies are pinned without manual research-environment reconstruction.
3. **Operational** — handles normal product-length inputs on supported worker hardware.
4. **Artifact-complete** — produces a deterministic path to valid non-empty MusicXML and notation playback data.
5. **Structurally sane** — no obvious catastrophic note deletion/hallucination, invalid measures, broken chunk boundaries, or illegal symbolic output on fixed product probes.
6. **Visibly better** — on the target piano failure, rendered notation is materially more readable/credible than the current MuseScore result.
7. **Truthful** — provenance names the exact source Version, engine/model/checkpoint, and score-domain role; Piano Roll performance evidence remains untouched.

After promotion, deeper OMR-NED/score-structure and human-readability evaluation can post-validate the decision and drive later routing changes.

## Next action

Do not add another local score heuristic or generic evaluation framework.

The highest-leverage unblock is obtaining production-usable distribution/terms for the two quality leaders:

1. Rubato deployable checkpoint/package/API;
2. MIDI2ScoreTransformer explicit license.

If either becomes available, implement it behind the existing notation boundary as a short production-shaped challenger, validate on the fixed product probes, and **replace** the solo-piano Score route if it clears the ship gate.
