# Structure corpus materialization

This note is the reproducibility contract for the first result-bearing Structure V1 run.
It is intentionally separate from production setup: benchmark audio and heavyweight reconstruction
checkpoints are research inputs, not application dependencies.

## Target

Use a small fixed **SongFormBench-CN (`BC`)** subset before expanding the corpus. `BC` is the
benchmark abbreviation used by the SongFormBench documentation; the canonical index/source-tree
subset literal is `CN`. Keep that distinction explicit rather than silently rewriting source
metadata.

`BHX` is derived from HarmonixSet and is training-overlapping for Harmonix-trained All-In-One
checkpoints, so it must not be the first independent-quality claim.

The first corpus should contain 8 SongFormBench-CN songs selected without looking at candidate
outputs. We refer to this fixed set as **BC8** in result filenames because BC is the published
benchmark abbreviation.

## 1. Pin the upstream dataset snapshot

Materialize the canonical SongFormBench index and the official CN mel/reconstruction assets from an
**exact Hugging Face dataset revision**, not a moving `main` checkout. Record that revision in the
selection provenance.

The upstream dataset card currently identifies:

- canonical manual index: `data/SongFormBench.jsonl`;
- SongFormBench-CN benchmark abbreviation: `BC`;
- canonical CN asset/reconstruction paths under `CN`;
- CN reconstruction helper: `utils/CN/infer.py`;
- vocoder checkpoint family: `nvidia/bigvgan_v2_44khz_128band_256x`.

Do not add a YouTube scraper/downloader to this workflow. Original/local audio is preferred when it
is legitimately available; otherwise the benchmark's documented mel reconstruction path is the
fallback and must remain labeled as reconstructed audio.

## 2. Freeze a deterministic CN source subset (BC8 benchmark set)

Before reconstructing or running candidate models, select the corpus from the canonical index using
the source-literal `CN` value:

```bash
cd backend
python -m evaluation.analysis_v3.structure.datasets.songformbench_subset \
  --index /data/SongFormBench/data/SongFormBench.jsonl \
  --subset CN \
  --count 8 \
  --upstream-revision <EXACT_SONGFORMBENCH_REVISION> \
  --output-index /data/hello-ai-structure-v1/songformbench-bc8.jsonl \
  --provenance /data/hello-ai-structure-v1/songformbench-bc8-selection.json
```

Selection policy `lexicographic_source_id_v1` sorts canonical CN-row source IDs and takes the first
N. The source IDs themselves may use the published `BC_...` naming convention; that does not change
the canonical `subset` field. The provenance file records:

- literal `source_subset` (`CN` for this run);
- exact ordered source IDs;
- canonical index SHA-256;
- selection SHA-256;
- upstream revision supplied by the operator;
- expected audio/mel/label paths;
- annotated terminal end time for every selected song.

The selector intentionally does **not** map `BC` to `CN`. Passing the benchmark abbreviation as a
source subset should fail closed if the canonical index does not contain literal `BC` rows. This
keeps upstream schema changes visible rather than hiding them behind an alias.

Commit the small selection/provenance JSON if redistribution of that metadata remains covered by the
upstream CC BY 4.0 dataset license. Do **not** commit reconstructed or dataset-published song audio by
default.

## 3. Materialize one audio provenance for every candidate

Preferred order:

1. legitimately available original/local audio -> `audio_provenance=original`;
2. official CN mel reconstruction -> `audio_provenance=mel_reconstruction`;
3. other documented local audio -> `audio_provenance=local_unknown` only when its exact semantic
   provenance cannot be established.

The pinned SongFormBench dataset may itself publish an `audio_path` file. Acquiring that exact file
from the pinned dataset revision is a legitimate benchmark-input route, but possession alone does
not prove whether it is original source audio or a reconstruction. Record the acquisition route and
file hash separately and use `audio_provenance=local_unknown` unless upstream provenance supports a
stronger label.

For explicit mel reconstruction, use the upstream `utils/CN/infer.py` implementation with
`bigvgan_v2_44khz_128band_256x`. Record the exact BigVGAN code revision and checkpoint revision/hash
used. Do not silently substitute the separate HarmonixSet reconstruction path.

Every compared candidate must receive the **same audio files**. Never compare All-In-One on one
audio provenance with SongFormer on another and call the difference a model result.

## 4. Build the hello-ai evaluation manifest

Make local audio resolve to each selected entry's canonical `audio_path`, then use the existing
builder against the filtered index:

```bash
cd backend
python -m evaluation.analysis_v3.structure.datasets.songformbench \
  --index /data/hello-ai-structure-v1/songformbench-bc8.jsonl \
  --audio-dir /data/SongFormBench \
  --subset CN \
  --audio-provenance local_unknown \
  --output /data/hello-ai-structure-v1/songformbench-bc8-manifest.json
```

The builder must report all 8 rows as materialized before the candidate comparison is treated as the
fixed BC8 run. It should therefore emit dataset provenance as `SongFormBench-CN`, preserving the
canonical source subset literal. Missing rows stay explicit; do not replace them with hand-picked
alternatives after seeing model outputs. If a source is unusable, version a new corpus selection and
explain why.

## 5. Run the exact same manifest

```bash
python -m evaluation.analysis_v3.structure.run \
  --candidate allin1 \
  --manifest /data/hello-ai-structure-v1/songformbench-bc8-manifest.json \
  --device cpu

python -m evaluation.analysis_v3.structure.run \
  --candidate songformer \
  --manifest /data/hello-ai-structure-v1/songformbench-bc8-manifest.json \
  --device cuda
```

Do not use `--allow-training-overlap` for the headline comparison. `no_declared_overlap` is not proof
of an independently held-out checkpoint; preserve the runner's validity label in the report.

## 6. Result report requirements

For each candidate publish:

- per-track and macro 0.5 s / 3 s boundary precision, recall, and F1;
- trimmed interior-boundary diagnostics;
- load and inference time;
- process peak RSS and GPU/VRAM observations where applicable;
- machine/hardware and research-environment details;
- code license and checkpoint license separately;
- exact model/checkpoint/version provenance;
- exact dataset revision, canonical index hash, selection hash, selected source IDs, and audio
  provenance;
- all withheld, missing, candidate-error, and installation-failure rows;
- a qualitative review of the largest boundary failures.

Functional labels such as Verse/Chorus remain diagnostic only in this phase. The first product bridge
is reliable boundary evidence -> Section/Relation evidence -> localized Breakdown/comparison.
