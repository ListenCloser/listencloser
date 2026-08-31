# Evaluation methodology

This document defines the reusable evaluation protocol for choosing, rejecting, or bounding music-analysis implementations. It describes **how a decision should be evaluated**. Concrete results and next decision-changing evidence belong in [`EVALUATION_DECISIONS.md`](EVALUATION_DECISIONS.md) and the owning result/report.

The goal is not to maximize benchmark infrastructure. The goal is to produce trustworthy evidence that changes a production or product decision.

## Decision flow

```mermaid
flowchart TD
    Question["Named production / product decision"] --> Contract["Define equal candidate contract"]
    Contract --> Candidates["Pin candidate implementations + versions/checkpoints"]
    Candidates --> Corpus["Select legitimate corpus / split"]
    Corpus --> Validity["License + provenance + train/eval overlap checks"]
    Validity -->|invalid| Stop["Stop / correct protocol"]
    Validity -->|valid| Preprocess["Canonical preprocessing"]
    Preprocess --> Run["Run baseline + candidates"]
    Run --> Score["Task-standard metrics + failure diagnostics"]
    Score --> Product["Downstream product-value / runtime checks when relevant"]
    Product --> Decision{"Decision"}
    Decision --> Adopt["ADOPT / productionize bounded contract"]
    Decision --> Research["RESEARCH / retain evidence only"]
    Decision --> Reject["REJECT / stop work"]
    Decision --> Revisit["REVISIT only on named trigger"]
    Adopt --> Ledger["Update decision ledger + provenance"]
    Research --> Ledger
    Reject --> Ledger
    Revisit --> Ledger
```

## 1. Start with the decision, not the model

Every evaluation track must name the question that the result can change. Examples:

- Should Beat This replace the current localized beat/downbeat engine?
- Which production transcription profile should handle solo piano?
- Is an OSS performance-MIDI-to-score engine good enough to replace custom quantization/staffing stages?
- Does source separation improve a specific downstream claim enough to justify its runtime cost?

"This model/library is interesting" is not a sufficient evaluation question.

Before adding another candidate, metric, dataset adapter, or harness abstraction, state what outcome would change the decision.

## 2. Compare an equal production-shaped contract

Candidates should receive equivalent inputs and be scored on equivalent outputs. When production includes meaningful preprocessing, routing, cleanup, or postprocessing, evaluate that real contract rather than a convenient raw model wrapper unless the raw model itself is the subject of the experiment.

Record at minimum:

| Field | Required evidence |
| --- | --- |
| Candidate | package/repository and exact version or commit |
| Model | checkpoint/model identifier and digest when practical |
| Input | source representation and preprocessing |
| Output contract | normalized representation used by the scorer/product |
| Runtime | device/architecture and material execution constraints |
| License | code, weights, and dataset status relevant to production use |

If a candidate cannot satisfy the same contract, report the incompatibility rather than silently weakening the protocol for that candidate.

## 3. Treat corpus validity as a gate

A high metric is not promotion evidence when the evaluation data overlaps model training or validation data in a way that invalidates the claim.

```mermaid
flowchart LR
    Dataset["Dataset / split"] --> Provenance["Verify source + annotation provenance"]
    Model["Model / checkpoint"] --> Training["Verify declared training / validation corpora"]
    Provenance --> Overlap{"Decision-relevant overlap?"}
    Training --> Overlap
    Overlap -->|Yes| Bounded["Use only for bounded diagnostic claims"]
    Overlap -->|No| Scored["Eligible for held-out/generalization claim"]
```

Preserve the distinction between:

- controlled/synthetic correctness fixtures;
- training-overlap diagnostics;
- published validation splits;
- genuinely held-out evaluation evidence;
- real product fixtures without ground truth.

Do not collapse these evidence tiers into one headline score.

## 4. Prefer task-standard tooling and metrics

Use maintained domain tooling where it already exists rather than recreating scorers or dataset semantics locally. Current examples include `mir_eval` for task metrics and `mirdata` where its dataset adapter matches the exact required annotation contract.

A custom metric is justified only when a named product property is not represented by an accepted task metric. Keep canonical metrics and product diagnostics separate so a product-specific diagnostic does not quietly become a benchmark definition.

Always retain per-item/failure distributions where practical. Aggregate means alone hide negative tails that are often operationally important for music systems.

### OSS-first adoption and custom-ablation rule

For a mature MIR problem with a credible maintained OSS implementation, treat OSS as the presumptive implementation after verifying its input/output contract, license, maintenance status, runtime, and deployment fit. Do not require standard OSS to defeat an equivalent repository-local implementation in a ceremonial bakeoff before replacing bespoke machinery.

Where quality can materially differ, run the smallest valid evaluation needed to detect regression. A repository-local implementation or heuristic bears the burden of demonstrating a meaningful, reproducible advantage on held-out or production-path evidence; otherwise prefer the OSS implementation and delete the bespoke alternative, obsolete fallbacks, and dedicated helper/tests.

Custom rules layered over OSS should be evaluated as an ablation: **upstream OSS** versus **upstream OSS + custom rule**. The custom layer survives only if it demonstrates incremental value on valid evidence. Disabled fallbacks are not retained merely "just in case."

For standard infrastructure such as accepted MIR metrics and supported dataset loaders, contract verification is normally sufficient. Prefer a small evaluation stack—canonical dataset/metric tooling, thin normalization adapters, compact machine-readable results, and ordinary tests—over experiment databases, dashboards, or bespoke orchestration without a demonstrated requirement.

## 5. Separate model quality from product value

Objective quality can be necessary without being sufficient for production adoption.

```mermaid
flowchart LR
    A["Model/task quality"] --> B["Contract compatibility"]
    B --> C["Runtime / memory / deployment"]
    C --> D["Downstream product behavior"]
    D --> E["Production decision"]
```

Examples:

- a separator can improve SI-SDR while failing to improve beat or transcription quality;
- a model can improve an aggregate metric while producing unacceptable negative-tail failures;
- a notation engine can emit valid MusicXML while still producing a less readable score;
- a model can be accurate but too slow for the intended execution topology.

Only evaluate downstream product value that can change the decision. Do not build a universal product-value framework before a concrete decision needs one.

## 6. Result artifact contract

A decision-bearing evaluation should preserve enough information that another contributor can reproduce or invalidate the conclusion without reconstructing a chat/PR history.

The durable result should include:

- decision question;
- baseline and candidate identities;
- dataset/split provenance and licensing notes;
- checkpoint training/validation overlap assessment;
- canonical preprocessing;
- scorer/library + version + metric parameters;
- per-item results and aggregate summary;
- material failures/negative tail;
- runtime/resource measurements when decision-relevant;
- explicit `ADOPT`, `RESEARCH`, `REJECT`, or `REVISIT` implication;
- exact conditions that would justify revisiting the result.

Machine-readable results are preferred when practical. Narrative reports should summarize and interpret them rather than becoming the only copy of measured numbers.

## 7. Allowed evaluation PR shapes

```mermaid
flowchart TD
    PR["Evaluation PR"] --> Kind{"What does it produce?"}
    Kind --> R["RESULT_BEARING\nlegitimate corpus + decision"]
    Kind --> V["VALIDITY_CORRECTION\nfixes invalid/overstated evidence"]
    Kind --> P["PRODUCTIONIZATION\nimplements bounded winner"]
    Kind --> N["NECESSARY_PREREQUISITE\nminimum blocker for named run"]
```

Once a runnable harness exists, the default next change is **RESULT_BEARING**, not another framework extension.

Avoid:

- adding candidates because they are popular rather than decision-relevant;
- adding a second scorer for a task already covered by a standard metric;
- refactoring a harness before it has produced its first legitimate result;
- treating green harness CI as benchmark evidence;
- promoting a model from a tiny qualitative probe or invalid train/eval overlap;
- building deployment infrastructure before the quality/product gate has been crossed.

## 8. Evaluation architecture and ownership

```mermaid
flowchart LR
    Manifest["Candidate / corpus manifests"] --> Harness["backend/evaluation"]
    Dataset["Datasets / annotations"] --> Harness
    Production["Production adapters / profiles"] --> Harness
    Harness --> Metrics["Canonical metric libraries"]
    Harness --> Results["Machine-readable results"]
    Results --> Report["Owning evaluation report"]
    Report --> Ledger["EVALUATION_DECISIONS.md"]
    Ledger --> Runtime["Production change or explicit no-change"]
```

Ownership rules:

- production adapters/config own production behavior;
- evaluation code owns repeatable experimental execution, not product policy;
- result artifacts own measured evidence for an exact protocol;
- `EVALUATION_DECISIONS.md` owns the cross-track decision summary and next allowed decision-changing result;
- GitHub issues own unresolved future work.

## 9. Reproducibility tooling boundary

Do not introduce an experiment platform merely to make the diagram look cleaner.

A DVC pilot is appropriate only on a track that already has a real decision-bearing run and only if DVC replaces meaningful bespoke dataset/provenance/pipeline/result plumbing. The pilot must have an explicit deletion test: if it mostly wraps existing repository machinery, remove it instead of maintaining two systems.

MLflow or another experiment service is not required for the current decision workflow. Revisit only if cross-machine run tracking/model registry needs become a demonstrated operational problem.
