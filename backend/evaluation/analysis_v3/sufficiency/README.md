# Evidence sufficiency — perturbation evaluation boundary

Issue: #457

The claim matrices in this branch are architecture/research artifacts. Executable perturbation/error-propagation experiments should live in an isolated evaluation branch/PR so this docs lane does not become a mixed research+runtime diff.

First executable probes should remain theory-neutral:

1. shift a trusted/reference metric grid by controlled milliseconds and measure the resulting error in beat-relative event offsets;
2. shift comparison/section boundaries by controlled amounts and measure the change in aggregate span summaries;
3. later add melody-note deletion/insertion and source-activity noise only after the corresponding relation contracts are concrete.

The purpose is to determine **claim tolerance**, not to invent semantic thresholds. Any threshold used by a downstream claim must be declared by that claim/sufficiency gate rather than hidden in the perturbation helper.
