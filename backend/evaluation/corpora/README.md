# Evaluation corpora

This directory stores **manifests and small, reviewable metadata only**. External music corpora, audio, MIDI collections, and upstream repositories are not vendored into this repository.

## Local acquisition

Some research/evaluation workflows may use local checkouts or downloaded datasets under paths such as:

- `bps-fh/`
- `mozart_piano_sonatas/`
- `romantic_piano_corpus/`

Those directories are intentionally ignored by Git. Acquire a dataset only from its documented upstream source and comply with its code/data license before using it. Do not commit dataset payloads merely to make an evaluation reproducible.

If an evaluation begins to depend on one of these corpora, add an explicit acquisition adapter or manifest that records at least:

- upstream project/dataset name and source
- pinned release, revision, or checksum where possible
- code, model, and dataset licenses separately
- whether commercial/product use is permitted
- expected local directory layout
- whether audio is distributable or must be acquired manually
- the exact evaluation subset used

## Why there are no submodules here

This repository previously contained three gitlink entries for the paths above but no `.gitmodules` configuration. They could not be checked out and caused GitHub Actions cleanup to emit `No url found for submodule path ...` on normal jobs. They were legacy repository metadata, not a reproducible acquisition mechanism.

Use a documented, license-aware acquisition path instead of adding an unconfigured gitlink or committing a large corpus directly.
