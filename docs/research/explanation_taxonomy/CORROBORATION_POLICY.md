# Explanation Taxonomy — corroboration policy

Issue: #456  
Roadmap: #458

## Why this exists

A source may be useful for learning the **shape of an explanation** even when some factual or creator-intent details are better established elsewhere. Keep those roles separate rather than silently upgrading a partially reviewed video to `full_review` because a secondary source confirms one detail.

## Additional annotation fields

Second-pass rows may add:

- `review_basis` — what was actually inspected (full artifact, relevant section, creator companion description, indexed chapter metadata, etc.);
- `corroborating_source_ids` — IDs from `supporting_sources.json` that independently support factual/contextual details;
- `corroboration_status` — short methodological note such as `strong_external`, `creator_process_documented`, or `independent_pedagogical_use`.

These fields **do not override `review_depth`**.

A `metadata_only` row remains metadata-only even if an external source strongly corroborates a factual detail. It must still be excluded from final corpus frequency counts until the primary explanatory artifact is reviewed to the required depth.

## What corroboration is for

Use corroboration to distinguish:

1. **explanation structure** — how the analyst organizes and proves an argument;
2. **musical fact** — e.g. the presence of mixed meter;
3. **creator intent** — e.g. why a composer says a device was chosen;
4. **pedagogical reuse** — whether an independent course treats a demonstration as a useful teaching pattern.

These are different evidence claims.

## Examples from the seed corpus

### Underground Theme
The 8-bit Music Theory chapter metadata identifies time-signature evolution as an explanatory topic. Koji Kondo interview material and a separate audio documentary independently support the mixed-meter intent and later regularization facts. That makes the cross-arrangement relation a strong research hypothesis, but it does **not** make the unreviewed video a `full_review` artifact.

### Reharmonization
Adam Neely's creator description establishes that one chorus is reharmonized through multiple approaches. NYU independently uses the video to teach how changing harmony changes how a retained melody/song is heard. This strengthens the product principle that controlled A/B transformation can function as proof.

### Recreation
Nahre Sol's creator process article documents concentrated listening, property note-taking, experimentation, and writing a new piece. This supports treating recreation as a way to test whether an analysis captured operational properties, while avoiding the stronger claim that stylistic resemblance proves authorship or exhaustive style understanding.

## Product implication

`replay`, `compare`, `normalize`, `reharmonize`, and `recreate` should be modeled as **proof/demonstration affordances**. They do not automatically increase the truth tier of the underlying claim; they help a user inspect or challenge it.
