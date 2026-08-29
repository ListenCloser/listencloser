# Analysis V3: Source Separation Downstream-Value Bakeoff

Evaluation harness for #334.

The first merged stage proved only source-separation feasibility. This follow-up adds the first real downstream product-value path: compare the **same production beat estimator** on the original mixture and the separated drum stem, scored with the canonical Analysis V3 beat metric.

It still does **not** establish that source separation should be promoted to production. Chord, melody/bass, arrangement, objective separation quality, and broader multi-style evidence remain open gates.

## Quick Start

```bash
python -m backend.evaluation.analysis_v3.separation.run --candidate demucs --task operational
python -m backend.evaluation.analysis_v3.separation.run --candidate demucs --task separation
```

To measure downstream beat value, pass an annotated manifest containing `reference_beats`. The existing GuitarSet pulse manifest is compatible:

```bash
python -m backend.evaluation.analysis_v3.separation.run \
  --candidate demucs \
  --task separation \
  --manifest backend/evaluation/analysis_v3/pulse/manifests/guitarset_beats.json
```

The scored downstream path requires `mir_eval==0.8.2` in the benchmark environment, matching the canonical #335 metric implementation.

## Candidates

| Candidate | Model ID | Code License | Weight License | Status |
|---|---|---|---|---|
| bs_roformer | lucidrains/BS-RoFormer | MIT | CC-BY-NC-SA-4.0 | REVISIT: exact compatible pretrained inference path not yet validated |
| demucs | facebookresearch/demucs / HTDemucs | MIT | MIT | RESEARCH: operationally runnable |

## What is evaluated

1. install/load feasibility
2. CPU latency/runtime feasibility
3. expected stem extraction shape on real audio
4. when beat annotations are present, mixture-vs-drums beat F1 using:
   - production baseline: `music_features.estimate_beat_grid`
   - metric: `mir_eval.beat.f_measure`
   - threshold: `0.07`
5. per-clip beat deltas plus aggregate mean/median and improved/degraded counts

## Still not evaluated

- objective SDR/SIR/SAR on an isolated-source reference corpus
- perceptual separation errors
- downstream chord/harmony improvement
- downstream melody/vocal or bass-pitch improvement
- arrangement/layer entry-exit value
- product UI or production routing/storage

Unimplemented task metrics intentionally return `None` rather than fabricating evidence or substituting easier proxy detectors.

## Manifests

- `diversity_probe.json`: real-music extraction smoke probes from GuitarSet and BabySlakh
- an explicit `--manifest` may point to any compatible annotated manifest; `pulse/manifests/guitarset_beats.json` is the current beat-scoring path

## Results

Machine-readable results are saved to `results/{candidate}.json`.

A scored row contains a downstream block of the form:

```json
{
  "downstream": {
    "beat_f1_drums": {
      "mixture_score": 0.30,
      "stem_score": 0.52,
      "delta": 0.22
    }
  }
}
```

These numbers are illustrative only; no result is claimed until the benchmark is actually run on lawful annotated audio.

See `REPORT.md` for the prior feasibility-stage evidence boundary and remaining #334 gates.
