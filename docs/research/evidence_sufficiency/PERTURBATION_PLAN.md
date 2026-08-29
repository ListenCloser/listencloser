# Evidence sufficiency — perturbation plan

Issue: #457  
Roadmap: #458 / #460

## Question

How much upstream error can a downstream relation tolerate before its measured support materially changes?

The perturbation harness must report **raw sensitivity**. It must not hide product semantics or arbitrary musical thresholds inside generic utilities.

## First probes

### Metric-grid shift

Given reference event times and reference beats/downbeats:
- compute event-to-reference-grid offsets;
- shift the metric grid by controlled values such as ±10, ±20, ±50, ±100 ms;
- recompute offsets and nearest-grid assignment;
- report absolute offset error and assignment changes.

Consumers such as groove/flow relations can then declare their own tolerance. A global tempo estimate is not enough.

### Span-boundary shift

Given a time series and reference span:
- compute a declared aggregate (mean/median);
- shift start/end boundaries independently;
- report aggregate delta and fraction of frames whose membership changes.

This distinguishes broad section summaries that tolerate coarse boundaries from exact entry/exit claims that do not.

## Later probes

Add only when corresponding evidence/relation work is concrete:
- melody note deletion/insertion/timing jitter → contour/recurrence stability;
- chord/key corruption → Roman-numeral/function/cadence propagation;
- stem bleed/activity noise → source entry/exit and coordination;
- codec/gain/sample-rate perturbation → perceptual-series stability (#455).

## Reporting

Each probe should emit machine-readable rows containing:
- reference input;
- perturbation type + magnitude;
- measured downstream delta;
- assignment/topology changes where relevant;
- no semantic conclusion unless a claim-specific gate is supplied explicitly.

This keeps `EXACT_EVENT_REQUIRED`, `LOCALIZATION_TOLERANT`, and similar quality gates empirically grounded rather than rhetorical labels.
