# Pulse Benchmark Validity Notes

## Checkpoint/data leakage correction

The historical GuitarSet comparison in `REPORT.md` must **not** be treated as
held-out evidence for promoting the default Beat This checkpoint.

The evaluation adapter uses Beat This `final0`. The official Beat This model
documentation states that `final0`, `final1`, and `final2` were trained on all
of the paper's training/validation datasets except GTZAN, and explicitly warns
that evaluating those checkpoints on their training datasets can produce
unfairly good results:

- https://github.com/CPJKU/beat_this#available-models
- https://arxiv.org/abs/2407.21658 (Section 4.1 datasets)

GuitarSet is part of that training collection. The paper states that the Beat
This training setup uses GuitarSet comping tracks. Therefore the previously
reported GuitarSet result (Beat This beat F1 0.94 versus the production
librosa baseline 0.30) is useful as an **in-sample capability probe**, but it
is not valid evidence of generalization superiority for `final0`.

This also means Ballroom, Hainsworth, SMC, ASAP, RWC, Harmonix, and the other
published Beat This training datasets are not fair generalization tests for
`final0` unless a checkpoint/split that excludes the scored tracks is used.

## Fair next comparison

For the default `final0` checkpoint, GTZAN is the cleanest paper-defined
held-out corpus. The official model documentation identifies GTZAN as the test
set excluded from `final*`/`small*` training.

The repository now provides:

- explicit checkpoint/training/held-out provenance in `PulseMetadata`;
- a default guard that rejects train/evaluation dataset overlap;
- `--allow-training-overlap` only for deliberately labeled in-sample probes;
- `datasets/gtzan.py` to build a deterministic manifest from Beat This v1.0
  GTZAN beat/downbeat annotations while requiring a local user-supplied audio
  copy;
- `run_manifest.py` to evaluate an explicit held-out manifest without
  overwriting the historical diversity probe.

## GTZAN licensing caveat

The Beat This annotation repository is MIT-licensed, but the original GTZAN
audio licensing/distribution status is not asserted here. This repository does
not redistribute GTZAN audio. A local user-supplied copy is required, and the
manifest records the audio license as unknown rather than inventing a license.

## Promotion gate

Do not switch the production beat engine based on the GuitarSet numbers.
Promotion should require at minimum:

1. current production baseline and Beat This `final0` scored on held-out GTZAN
   (or another demonstrably unseen annotated corpus), using the same audio;
2. per-piece beat/downbeat distributions, tempo errors including half/double
   errors, latency, failure rate, and deterministic/runtime evidence;
3. explicit checkpoint, annotation version, and dataset provenance;
4. independent review of the resulting evidence.
