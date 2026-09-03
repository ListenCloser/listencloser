# Listen Closer product constitution

Listen Closer is an **evidence-first music-understanding workspace**. It helps a person turn music they care about into an understanding they can hear, inspect, question, verify, relate, and use.

This document owns durable product identity, user progress, strategic arena, product mental model, and product principles. It does **not** prioritize current work, describe current capability maturity, or authorize implementation. The documentation map routes those questions to their current authorities.

## 1. Product definition

Listen Closer exists to make deep musical understanding substantially easier without asking the user to understand music-information-retrieval machinery or trust unsupported AI prose.

It is not primarily an audio-to-sheet-music product, a detector dashboard, or a chatbot over recordings. Representations, analysis, and conversation are means to a larger outcome: helping the user form an inspectable mental model of music and connect that model back to what they actually hear.

The product is successful when a user can move from curiosity — “what is happening here?” — to a supported understanding they can verify for themselves and carry into listening, learning, comparison, practice, communication, or creative action.

## 2. Target users and circumstances

We optimize for people who actively listen in order to understand: curious musicians, composers, students, and serious listeners. Musical circumstance matters more than credential or expertise.

The core circumstance is:

- the user already cares about a piece, performance, or passage;
- something in it attracts attention, creates confusion, or raises a question;
- the user wants more than a label or summary — they want to connect an explanation to the music itself;
- they may not know the right technical vocabulary in advance;
- they want to decide for themselves whether an explanation is convincing.

Listen Closer should support different levels of musical literacy without making internal product concepts or one theoretical tradition prerequisites for use.

## 3. Primary job and north star

Our primary job to be done is:

> **When I encounter music I care about and want to get more from it, help me turn listening into an understanding I can verify for myself and then use.**

Our winning aspiration is to become the best place for a musically curious person to build an inspectable mental model of music they care about: one they can hear, see, question, compare, learn from, and eventually act on.

“Understanding” is not synonymous with producing more analysis fields. It means helping the user answer useful musical questions with enough evidence and context to inspect the answer rather than merely accept it.

## 4. Core experience

The conceptual product loop is:

```text
hear
  → inspect
  → select
  → understand
  → verify
  → relate / compare
  → act
```

Import and Library are entry and return paths into this loop; they are not the conceptual purpose of the product.

- **Hear** — remain grounded in the music itself.
- **Inspect** — look through a useful representation or supported finding.
- **Select** — make “the music I am talking about” explicit.
- **Understand** — connect evidence into a musically meaningful observation or explanation.
- **Verify** — hear, focus, and inspect the support so the user can judge the claim.
- **Relate / compare** — understand repetition, contrast, change, similarity, or context when that advances the question.
- **Act** — use the understanding: ask a better question, learn, test an idea, compare alternatives, practice, communicate, or eventually transform.

The loop should preserve musical context. Looking at another lens, inspecting support, or asking a question should not make the user repeatedly reconstruct where they were or what they were hearing.

## 5. Where we play

Listen Closer competes around **deep understanding of user-chosen music**.

We choose to focus on:

- music the user already cares about, rather than catalog discovery as the primary experience;
- passage- and Work-level understanding where synchronized listening and inspectability matter;
- questions whose answers can be grounded in evidence appropriate to the musical domain;
- users who value understanding and verification more than raw detector output;
- expanding support domain by domain as the product can make useful, truthful claims rather than pretending one theory or representation is universal.

A question may require a simpler view, richer evidence, a relationship between existing views, a better explanation, or no new representation at all. The product should solve the user’s abstraction problem rather than assume that adding another visualization is progress.

## 6. How we win

Listen Closer differentiates through the combination of:

1. **Inspectable truth.** Important claims remain connected to evidence, musical location, provenance, and the limits of what is known.
2. **Complementary musical lenses.** Audio, note/performance views, notation, spectral views, and future representations answer different questions rather than competing to become one universal ontology.
3. **Relationships over output dumps.** Repetition, change, contrast, alignment, and contextual relationships are often more useful than isolated detector values.
4. **Selection as a common operation.** The user can make a passage or musical object explicit and then inspect, explain, compare, ask about, or act on it.
5. **Grounded explanation.** Explanation combines and interprets admitted evidence; it does not become a second unaccountable music detector.
6. **Preserved lineage.** Source material, derived interpretations, corrections, and future creative alternatives do not silently overwrite one another.
7. **Musician-first interaction.** The product absorbs internal complexity and exposes the smallest task-relevant set of concepts and decisions.
8. **Focused ownership of differentiation.** We custom-build music-specific semantics, relationships, interaction, and trust while preferring mature platform or OSS primitives for commodity infrastructure and established technical capabilities.

## 7. Durable product primitives

These are product-level mental models, not a database schema.

### Work

A **Work** is the persistent musical object the user returns to. Its representations, evidence, selections, interpretations, and future alternatives belong to the same musical context.

The user should not need to understand Jobs, Artifacts, database rows, processing stages, or internal Version machinery to complete the ordinary product loop.

### Musical time and selection

Musical time keeps listening, views, evidence, and actions oriented to the same place. A **selection** means “the music I am operating on.” When selection affects an action, its scope should be explicit rather than hidden state.

### Representation

A representation is a **lens on the music**, chosen for the question. No representation is the final or universally correct form of a Work.

The best evidence source and the best display representation may differ. A compact abstraction can be more useful than a richer one for one task and less useful for another.

### Playback source

What the user **hears** and what the user **looks at** are distinct choices. Changing a visual representation must not implicitly redefine the audible source.

### Evidence

Evidence is measured, derived, or otherwise admitted support with enough provenance and localization to justify the claim being made. Sufficiency is claim-specific: evidence that supports a broad statement may be inadequate for a precise local one.

Unknown, unsupported, disputed, and unavailable are valid product states.

### Finding, relationship, and explanation

A **finding** makes supported evidence useful to a person. A **relationship** connects musical objects or contexts through repeat, change, contrast, sequence, alignment, similarity, or another bounded musical relation. An **explanation** helps the user understand what those supported observations mean within an appropriate musical framework.

These layers must not erase the distinction between what was measured, what was derived, and what was interpreted.

## 8. Product principles

### Truthfulness beats completeness

A missing or qualified answer is better than a plausible unsupported one. Product polish, ranking, confidence-like styling, or generated prose must never imply stronger evidence than the underlying contract supports.

### Evidence precedes interpretation

Precise musical facts should come from appropriate evaluated evidence. Relationships and explanations sit downstream of that evidence. Language models may explain, connect, retrieve, or teach from support; they are not trusted as the sole detector for exact musical facts.

### Important claims should be verifiable in the music

Where practical, the user should be able to hear, focus, or inspect the passage and support behind an important claim. Provenance is useful because it enables trust and correction, not because implementation metadata deserves primary UI space.

### Representation follows the question

Do not privilege notation, MIDI, a waveform, a detector output, or any future view as the product ontology. Choose the level of abstraction and representation that best serves the user’s musical question and available evidence.

### Musical frameworks are contextual, not universal

Western tonal theory is one useful framework among many. Style-, culture-, instrument-, and tradition-specific concepts should appear only when relevant and supported, with their scope made clear. Expand product support by validated musical domain rather than forcing every Work through one theory vocabulary.

### Reduce conceptual load without hiding truth

Do not make a musician learn Listen Closer’s internal data model to use Listen Closer. Prefer deletion, consolidation, grouping, progressive disclosure, and user-facing language before adding more interface. Keep irreducible detail available when it matters for truthfulness, control, accessibility, or recovery.

### Protect musical flow

Playback, selection, and task-relevant context should remain stable while the user changes views or inspects deeper information. Long-running or advanced capabilities should not unnecessarily interrupt already-useful listening and exploration.

### Capabilities earn product surface through progress, not availability

A model, algorithm, visualization, or technical capability is not a product feature merely because it works. It should create meaningful progress for a real user circumstance and support the exact claims the product intends to make.

### Preserve human choice for future creative action

Corrections, transformations, and generated alternatives should be explicit proposals the user can inspect, compare, accept, or reject. They must not silently replace source or performance evidence.

## 9. Explicit non-goals

Listen Closer is deliberately **not** trying to become:

- a generic prompt-to-song generation product;
- a full DAW, mixer, or production environment;
- a full notation editor;
- a generic LMS or complete music-theory curriculum;
- a streaming catalog, discovery, or recommendation service;
- a MIR benchmark, model-comparison, or detector dashboard;
- an opaque “ask anything about audio” chatbot whose prose substitutes for evidence;
- a universal Western-theory analyzer;
- a collection of every technically possible musical representation.

These boundaries do not ban individual capabilities such as notation, learning, practice, comparison, or creative transformation. They mean those capabilities must extend the core music-understanding job instead of redefining Listen Closer into a different primary product.

## 10. Long-term product envelope

The same trustworthy musical objects can support a wider set of user progress without changing the constitution:

- **understand** what is happening and why;
- **relate and compare** passages, performances, or Works;
- **learn** concepts through the user’s own music;
- **act** by testing, practicing, communicating, or trying an alternative;
- **transform or create** through inspectable, human-chosen proposals;
- **generalize** patterns across a personal body of music when that becomes useful.

These are an envelope, not a roadmap or commitment. Current priorities, gates, experiments, and implementation owners belong to the roadmap and focused work authorities.
