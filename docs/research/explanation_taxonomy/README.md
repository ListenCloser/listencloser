# Explanation Capability Taxonomy research

Issue: #456  
Parent direction: #458  
Consumers: #457, #460, #461

## Current status

This is the **seed pass**, not the final 30–50-artifact corpus.

It establishes:
- a source manifest with provenance;
- a paraphrase-only annotation policy;
- a controlled first-pass claim/relation/evidence vocabulary;
- explicit review-depth metadata;
- seed annotations across materially different analytical traditions.

## Why this is separate from MIR benchmarking

MIR benchmarks answer whether an evidence source detects a musical object reliably. This research answers a different question:

> Which evidence-backed relationships are actually useful ingredients in high-quality human musical explanations?

The two streams meet in #457.

## Seed findings to test, not assume

The first annotations suggest several reusable patterns:

1. **Relation > label.** Strong explanations often depend on `changes`, `returns`, `aligns`, `responds`, or `contrasts`, not merely identifying a chord/meter/instrument.
2. **Comparison is pervasive.** A/B sections, recurrence, reharmonization, and performer interaction all need explicit comparison targets.
3. **Temporal quality requirements differ by claim.** Rap flow/beat alignment needs event-level timing; timbre/texture section contrast can tolerate coarser boundaries.
4. **Framework-specific interpretation must be explicit.** Functional harmony, jazz interaction, and culturally named rhythmic conventions should not masquerade as universal measured facts.
5. **Proof is part of the product.** Replay, loop, isolate, highlight, compare, transform, or recreate are often what make an explanation convincing.
6. **Timbre/texture/source activity matter structurally.** Analysis cannot remain score/MIDI-centric if it wants to explain produced popular music.

These are provisional until the corpus is expanded and independently re-annotated.

## Next research slice

1. Fully review the two user-seeded videos plus 3 contrasting sources.
2. Double-annotate those sources using the rubric.
3. Resolve rubric ambiguity before scaling.
4. Expand toward 30–50 artifacts with intentional coverage of:
   - tonal/harmonic analysis;
   - rhythm/groove;
   - form/repetition;
   - timbre/production/arrangement;
   - performance/interaction;
   - rap/text-music analysis;
   - teaching/recreation/counterfactual demonstration;
   - analytical traditions that expose Western/score-centric assumptions.
5. Produce frequency counts only after `metadata_only` rows are excluded.
6. Feed stable claim families and evidence prerequisites into #457.

## Copyright / research-content policy

The repository stores source metadata and **paraphrased analytical annotations only**. Do not commit transcripts, copied scripts, long quotations, video/audio payloads, textbook chapters, or copyrighted score images.
