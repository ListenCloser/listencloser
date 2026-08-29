# Structure V1 bakeoff

This directory evaluates music-structure **boundary detection** without changing production routing.
It depends on the boundary metric contract introduced by #505.

## Why this is isolated

Structure candidates currently have very different runtime stacks:

- `allin1` can be imported directly in a dedicated research environment;
- SongFormer uses its own research stack, including MuQ, MusicFM, SongFormer checkpoints/config,
  and the upstream inference/post-processing code;
- future candidates may expose a CLI rather than a Python package.

Do not add those stacks to the production backend lock just to benchmark them.

## Candidates

### `allin1`

The adapter lazily imports the upstream package. The default checkpoint is `harmonix-all` and can
be changed with `STRUCTURE_ALLIN1_MODEL`.

`harmonix-all` must not be treated as independent held-out evidence on ordinary HarmonixSet rows:
it is an ensemble across HarmonixSet folds. The runner therefore withholds matching dataset-family
rows by default.

### `external_json`

This adapter runs a command with `shell=False` and expects JSON on stdout. It is the preferred seam
for heavyweight research systems such as SongFormer.

Set:

```bash
export STRUCTURE_EXTERNAL_NAME=songformer
export STRUCTURE_EXTERNAL_COMMAND='python /path/to/songformer_wrapper.py {audio}'
export STRUCTURE_EXTERNAL_REPO='https://github.com/ASLP-lab/SongFormer'
export STRUCTURE_EXTERNAL_CODE_LICENSE='CC-BY-4.0'
export STRUCTURE_EXTERNAL_CHECKPOINT='SongFormer.safetensors'
export STRUCTURE_EXTERNAL_TRAINING_DATASETS='HarmonixSet'
```

The command must print either:

```json
[
  {"start": 0.0, "end": 12.4, "label": "intro"},
  {"start": 12.4, "end": 31.8, "label": "verse"}
]
```

or:

```json
{"segments": [{"start": 0.0, "end": 12.4}]}
```

Labels are retained for diagnostics but are **not** scored as validated semantics.

For SongFormer, wrap the released upstream inference implementation rather than inventing a simple
`AutoModel(audio)` call. The upstream path in `src/SongFormer/infer/infer.py` loads MuQ, MusicFM,
SongFormer configuration/checkpoint state, and functional-structure post-processing.

## Manifest

The runner reuses `evaluation.models.CorpusManifest`. A scored clip needs:

- an accessible local audio path;
- `reference.sections` containing `start`/`end` spans;
- dataset/split provenance when known.

Example:

```json
{
  "name": "structure-held-out-v1",
  "clips": [
    {
      "id": "track-001",
      "audio": "/data/track-001.wav",
      "category": "full_mix",
      "dataset": "IndependentSet",
      "split": "test",
      "reference": {
        "sections": [
          {"start": 0.0, "end": 14.2},
          {"start": 14.2, "end": 42.8}
        ]
      }
    }
  ]
}
```

## Run

```bash
cd backend
python -m evaluation.analysis_v3.structure.run \
  --candidate allin1 \
  --manifest /path/to/manifest.json \
  --device cpu
```

or:

```bash
python -m evaluation.analysis_v3.structure.run \
  --candidate external_json \
  --manifest /path/to/manifest.json \
  --device cuda
```

Outputs include per-clip metrics, inference latency, process peak RSS, candidate provenance, and
macro 0.5 s / 3 s boundary F1. Both task-standard start/end-inclusive scores and trimmed interior
boundary diagnostics are retained.

## Training-overlap rule

If candidate metadata names the same dataset family as a clip, the runner emits
`withheld_training_overlap` and does not even run candidate inference for that row.

A published held-out split can be declared with the external adapter's held-out metadata fields.
Otherwise `--allow-training-overlap` is available only for an explicitly labeled in-sample
diagnostic; such rows are emitted with `evaluation_validity = in_sample_override`.

## Non-goals

This harness does not:

- enable Structure in production;
- validate `verse`/`chorus` labels;
- evaluate repeated-section grouping;
- claim a candidate is production-ready from paper numbers;
- install All-In-One, SongFormer, or their checkpoints in the production environment.

The next result-bearing step is to materialize a small, legitimate annotated corpus and run the same
manifest through All-In-One and the real SongFormer upstream pipeline, reporting quality, runtime,
RAM/VRAM, licensing, and per-track failures before any product exposure.
