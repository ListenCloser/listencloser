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

This also means Ballroom, Hainsworth, SMC, ASAP, RWC, Harmonix, Candombe, and
the other published Beat This training datasets are not fair generalization
tests for `final0` unless a checkpoint/split that excludes the scored tracks is
used.

## Held-out paths

### Default `final*` / `small*`: GTZAN

For the default `final0` checkpoint, GTZAN is the cleanest paper-defined
held-out corpus. The official model documentation identifies GTZAN as the test
set excluded from `final*`/`small*` training.

The repository provides:

- explicit checkpoint/training/held-out provenance in `PulseMetadata`;
- a default guard that rejects train/evaluation dataset overlap;
- `--allow-training-overlap` only for deliberately labeled in-sample probes;
- `datasets/gtzan.py` to build a deterministic manifest from Beat This v1.0
  GTZAN beat/downbeat annotations while requiring a local user-supplied audio
  copy;
- `run_manifest.py` to evaluate an explicit held-out manifest without
  overwriting the historical diversity probe.

#### GTZAN licensing caveat

The Beat This annotation repository is MIT-licensed, but the original GTZAN
audio licensing/distribution status is not asserted here. This repository does
not redistribute GTZAN audio. A local user-supplied copy is required, and the
manifest records the audio license as unknown rather than inventing a license.

### `single_final*`: published single-split validation rows

Beat This also publishes `single_final0`, `single_final1`, and `single_final2`
checkpoints trained from its documented `single.split` partitioning. Upstream
`BeatDataModule` reads `single.split`, sends rows marked `train` to training,
and rows marked `val` to validation.

That creates a second legitimate evaluation path for datasets that otherwise
participate in Beat This training: score a `single_final*` checkpoint only on
the exact `val` rows from the same published split/version.

For Candombe, Beat This annotations v1.0 mark exactly five performances as
validation rows:

- `csic.1995_ansina1_03`
- `csic.1995_ansina2_01`
- `csic.1995_ansina2_04`
- `csic.1995_cuareim_02`
- `zavala.muniz.2014_41`

The Candombe audio dataset is publicly distributed under CC BY 4.0 and includes
expert beat/downbeat annotations. This makes the five-track split operationally
more reproducible than GTZAN while also probing a rhythmically distinct corpus.
It remains a **small validation set**, not a standalone production-promotion
benchmark.

The evaluation contract therefore records partition-qualified dataset IDs:

- `candombe` — ambiguous/raw corpus identifier; overlaps training and is rejected;
- `candombe_single_split_train` — training partition; rejected;
- `candombe_single_split_val` — held-out partition; accepted for
  `beat_this_single_final0` when built from Beat This annotations v1.0.

`datasets/candombe.py` builds the exact validation manifest from an upstream
v1.0 checkout and a local Candombe audio directory. Audio is never copied into
the repository.

Example:

```bash
python -m backend.evaluation.analysis_v3.pulse.datasets.candombe \
  /path/to/beat_this_annotations/candombe/annotations/beats \
  /path/to/beat_this_annotations/candombe/single.split \
  /path/to/candombe_audio \
  /tmp/candombe_single_val.json

python -m backend.evaluation.analysis_v3.pulse.run_manifest \
  --candidate current \
  --manifest /tmp/candombe_single_val.json

python -m backend.evaluation.analysis_v3.pulse.run_manifest \
  --candidate beat_this_single_final0 \
  --manifest /tmp/candombe_single_val.json
```

Do **not** replace `beat_this_single_final0` with `beat_this` in the Candombe
comparison and call it held out. `final0` trained on Candombe.

## Promotion gate

Do not switch the production beat engine based on the GuitarSet numbers or a
single five-track validation split.

Promotion should require at minimum:

1. current production baseline and a checkpoint-compatible Beat This candidate
   scored on legitimately held-out audio using the same clips;
2. preferably more than one held-out corpus/split before a default-engine switch;
3. per-piece beat/downbeat distributions, tempo errors including half/double
   errors, latency, failure rate, and deterministic/runtime evidence;
4. explicit checkpoint, annotation version, dataset split, audio license, and
   dataset provenance;
5. downstream sensitivity evidence from #457 for the exact claims the metric
   grid is expected to unlock;
6. independent review of the resulting evidence.

A Candombe `single_final0` result can materially improve the evidence base and
probe generalization within the model family, but it does not by itself prove
that default `final0` should replace the production librosa path.
