# Structure V1 bakeoff

This directory evaluates music-structure **boundary detection** without changing production routing.
It depends on the boundary metric contract introduced by #505.

## Why this is isolated

Structure candidates have very different runtime stacks. Do not add All-In-One, SongFormer, MuQ,
MusicFM, or research checkpoints to the production backend lock just to benchmark them.

## Candidates

### `allin1`

The adapter lazily imports the upstream package in a dedicated research environment. The default
checkpoint is `harmonix-all`, configurable with `STRUCTURE_ALLIN1_MODEL`.

`harmonix-all` is an ensemble across HarmonixSet folds. The runner therefore treats matching
HarmonixSet-family rows as training-overlapping unless explicit held-out provenance says otherwise.
Canonical BHX names such as `SongFormBench-BHX` are normalized to the Harmonix family so naming
aliases cannot bypass the gate.

### `songformer`

The adapter mirrors the official Hugging Face one-click contract:

1. use a configured local snapshot or materialize `ASLP-lab/SongFormer`;
2. add the snapshot to `sys.path` and set `SONGFORMER_LOCAL_DIR`;
3. load with `AutoModel.from_pretrained(..., trust_remote_code=True)`;
4. pass the audio filepath to the remote-code model;
5. normalize the returned `{start, end, label}` segments.

This remains research-only. Remote-code trust, checkpoint/commercial-use licensing, CPU/ARM
feasibility, model-load cost, RAM/VRAM, and training-corpus overlap remain adoption gates.

The one-click checkpoint does not expose sufficiently precise training-lineage metadata to infer one
published variant safely. Published SongFormer variants use Harmonix/HX with optional SongFormDB
Ext/Hook/Gem families, so the default provenance treats the **union of those released training
families** as potentially overlapping. Narrow that list or declare a held-out partition with the
`STRUCTURE_SONGFORMER_*` provenance variables only when checkpoint-specific evidence supports it.
The repository code license and checkpoint license are also tracked separately; an unresolved
checkpoint license must not be inferred from the repository's CC BY 4.0 code license.

### `external_json`

This generic fallback runs a candidate command with `shell=False` and expects a JSON list of segment
dicts, or `{"segments": [...]}`, on stdout. It is useful for heavyweight or non-Python systems that
should remain in their own environment.

## SongFormBench materialization

`datasets/songformbench.py` supports the benchmark's canonical manual index
`data/SongFormBench.jsonl` as well as timestamp/label text annotations.

The canonical index fields used by the upstream dataset loader include `id`, `subset`, `audio_path`,
`mel_path`, `label_path`, and `labels` containing `start`/`label` rows.

SongFormBench's documentation calls the Chinese benchmark **SongFormBench-CN (`BC`)**. Keep the two
names distinct in evaluation plumbing: `BC` is the published benchmark abbreviation, while the
canonical source/index subset literal used by the materializer is `CN`. Do not silently translate
one into the other; manifests should preserve the source literal as `SongFormBench-CN`.

Audio is **never downloaded or reconstructed implicitly**. Only already-materialized local audio is
placed in a manifest. Missing audio is reported together with the expected mel path. Every clip also
records `audio_provenance` as one of:

- `original`;
- `mel_reconstruction`;
- `local_unknown`.

If mel reconstruction is used, candidates being compared must receive the same reconstruction
provenance. Do not present reconstructed audio as original source audio.

Example for the SongFormBench-CN / BC benchmark lane:

```bash
cd backend
python -m evaluation.analysis_v3.structure.datasets.songformbench \
  --index /data/SongFormBench/data/SongFormBench.jsonl \
  --audio-dir /data/SongFormBench \
  --subset CN \
  --audio-provenance mel_reconstruction \
  --output /tmp/songformbench-bc.json
```

## Run

```bash
python -m evaluation.analysis_v3.structure.run \
  --candidate allin1 \
  --manifest /tmp/songformbench-bc.json \
  --device cpu
```

or:

```bash
python -m evaluation.analysis_v3.structure.run \
  --candidate songformer \
  --manifest /tmp/songformbench-bc.json \
  --device cuda
```

Outputs include per-clip task-standard 0.5 s / 3 s boundary metrics, trimmed interior-boundary
diagnostics, latency, load time, process peak RSS, candidate provenance, dataset/split/license/audio
provenance, and explicit withheld/error states.

Labels are retained for diagnostics but are **not** scored as validated section semantics.

## Training-overlap rule

If candidate metadata names the same dataset family as a clip, the runner emits
`withheld_training_overlap` and does not run inference for that row by default.

A documented held-out dataset/partition can be declared in candidate provenance. Otherwise
`--allow-training-overlap` is only an explicitly labeled in-sample diagnostic; scored rows carry
`evaluation_validity = in_sample_override`.

For the first All-In-One cross-model gate, SongFormBench-CN (`BC` benchmark abbreviation) is cleaner
than BHX because BHX comes from HarmonixSet. SongFormer independence still depends on the exact
checkpoint's documented training sources; do not assume CN/BC or BHX is held out without that
evidence.

## Non-goals

This harness does not:

- enable Structure in production;
- validate `verse`/`chorus` labels;
- evaluate repeated-section grouping;
- infer model quality from paper numbers;
- redistribute benchmark audio;
- change production dependencies, worker routing, schema, or UI.

The next result-bearing step is a same-manifest All-In-One/SongFormer run on legitimately
materialized annotated audio, with per-track failures, quality, latency, RAM/VRAM, installation
friction, licensing, and overlap validity reported before any product exposure.
