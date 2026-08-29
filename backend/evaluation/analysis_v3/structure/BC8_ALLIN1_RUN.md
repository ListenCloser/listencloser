# SongFormBench BC8 × All-In-One result gate

This branch exists to produce a result-bearing Structure V1 evaluation, not to change production routing.

## Fixed inputs

- SongFormBench dataset: `ASLP-lab/SongFormBench`
- dataset revision: `acd574ecbf666be535b0d051b71936f6ec9956ec`
- corpus selector: `lexicographic_source_id_v1`, subset `BC`, count `8`
- All-In-One: `mir-aidj/all-in-one` commit `c04f37609e2c7ba5d3b333d6d69a7e3c429dafc9` (`v1.1.0`)
- All-In-One checkpoint configuration: `harmonix-all`
- madmom: `CPJKU/madmom` commit `27f032e8947204902c675e5e341a3faf5dc86dae`
- PyTorch: `2.5.0+cpu`
- NATTEN: `0.17.4+torch250cpu`
- boundary scorer: the existing hello-ai Structure V1 scorer from #505/#516

The NATTEN pin is intentional: All-In-One v1.1.0 imports the legacy `natten1d*` / `natten2d*` functional API. NATTEN 0.17.5 removed those deprecated operators, while 0.17.4 publishes an explicit Torch 2.5 CPU wheel.

## Audio provenance

The workflow downloads only the eight deterministic `audio_path` files published by the pinned SongFormBench dataset revision. It does not scrape YouTube and does not commit or upload song audio.

Because the benchmark card documents mel reconstruction as a fallback when source audio is invalid, but does not make the semantic origin of every published audio file precise enough for hello-ai to call it original, the manifest records `audio_provenance=local_unknown`. A separate provenance file records the exact Hugging Face dataset revision, acquisition route, source IDs, relative paths, SHA-256 hashes, and byte sizes.

## Hard success gate

The run is successful only when all of the following are true:

- exactly 8 clips are in the manifest;
- exactly 8 clips are scored;
- every row has `status=scored`;
- every row has `evaluation_validity=no_declared_overlap`;
- the candidate-level result has `status=completed`.

`no_declared_overlap` is intentionally weaker than independently held out. BC is cleaner than BHX for a Harmonix-trained candidate, but lack of declared overlap is not proof of independence.

## Outputs

The workflow uploads only non-audio evidence:

- fixed selection JSONL + selection provenance;
- audio acquisition hashes/provenance;
- evaluation manifest;
- per-track + macro Structure metrics;
- machine/environment package inventory;
- downloaded model/checkpoint artifact hashes.

Functional labels such as Verse/Chorus remain unvalidated diagnostics and are not part of this gate.
