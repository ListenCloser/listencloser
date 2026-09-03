# Design tooling fixed-task scorecard

Owner: #1143

Use this scorecard to compare design-agent/tool workflows against the **same fixed brief and rendered surface**.

A high score does not automatically mean `ADOPT`. Written evidence and operational cost matter.

## Run metadata

**Workflow / tool:**  
**Version / commit / source:**  
**License:**  
**Installation method:**  
**Model used:**  
**Reference packet:**  
**Target surface:**  
**Viewport(s):**  
**Branch / artifact:**  

## Input parity check

All comparison runs must receive equivalent:

- product brief;
- semantic content;
- reference packet;
- fixed constraints;
- target surface/state;
- viewport requirements;
- no-fake-evidence requirement.

Record deviations before scoring.

## Rendered-output score

Score 1–5 and give one concrete observation for each.

| Dimension | Score | Evidence / observation |
| --- | ---: | --- |
| product specificity |  |  |
| memorability |  |  |
| musical relevance without cliché |  |  |
| typography |  |  |
| composition / hierarchy |  |  |
| material / color coherence |  |  |
| landing ↔ workspace continuity |  |  |
| UX clarity |  |  |
| responsive behavior |  |  |
| accessibility / reduced motion |  |  |
| anti-template quality |  |  |
| truthfulness |  |  |

## AI-slop critique

Mark `present`, `borderline`, or `absent`, then explain any `present/borderline` result.

| Pattern | Result | Notes |
| --- | --- | --- |
| generic centered badge → headline → CTA composition |  |  |
| purple/blue AI gradient or glow by default |  |  |
| glass/translucent cards without functional purpose |  |  |
| excessive rounded rectangles / pills |  |  |
| nested card soup |  |  |
| generic dark neutral + Inter/slate aesthetic |  |  |
| decorative particle/grid/noise background standing in for identity |  |  |
| three-up feature cards |  |  |
| gratuitous animated text / shimmer / magnetic interactions |  |  |
| literal note/equalizer/waveform category cliché |  |  |
| fake product/data visual |  |  |

## Implementation score

| Dimension | Score | Evidence / observation |
| --- | ---: | --- |
| reuses current product architecture |  |  |
| avoids unnecessary dependency additions |  |  |
| code clarity / ownership |  |  |
| responsive implementation quality |  |  |
| maintainability across product states |  |  |
| local component reuse vs duplication |  |  |

## Workflow behavior

Did the tool/workflow:

- explore more than one direction before convergence?
- cite/reference concrete visual decisions rather than vague inspiration?
- notice and revise its own generic defaults?
- use real rendered output for critique?
- preserve product semantics?
- respect current repo primitives where appropriate?
- introduce unrelated design-system/framework work?

Record concrete examples.

## Cost / operational notes

- setup complexity;
- auth/API-key requirement;
- external service dependency;
- pricing/usage constraints;
- CI suitability;
- security implications of fetched/generated code;
- license implications;
- model/context cost;
- human review burden.

## Decision

Choose one:

- **ADOPT** — normal design workflow;
- **USE AS REFERENCE** — research source only;
- **OPTIONAL** — bounded/specialized use;
- **REJECT** — insufficient value or poor fit;
- **RETEST** — promising but evidence incomplete.

### Why

State the specific marginal value compared with the baseline workflow.

### Reopening trigger

What new version/evidence would justify revisiting the decision?
