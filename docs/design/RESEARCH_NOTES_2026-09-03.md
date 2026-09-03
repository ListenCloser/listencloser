# Design tooling research notes — 2026-09-03

Owner: #1143

These notes capture time-sensitive observations from current public documentation. Re-verify before relying on operational details.

## 21st.dev

Current public 21st agent tooling describes a workflow that can:

- search its component catalog;
- inspect/install real component code and dependencies;
- generate multiple variants;
- explore design directions before code;
- review existing UI;
- publish a project's own theme/components for later agent reuse.

This strengthens the case for evaluating 21st as **component/reuse infrastructure after art direction**, not merely as an inspiration gallery.

The most interesting long-term possibility is not community-component dependence. It is using a project-owned approved component catalog so agents retrieve already-shipped Listen Closer primitives before inventing duplicates.

Caution: current public plan/usage language includes hosted account/usage constraints. Do not make normal repo verification depend on 21st availability.

## Vercel Web Interface Guidelines

Current public guidance includes detailed mechanical rules covering keyboard operation, focus visibility/management, hit targets, mobile input sizing, interaction contrast, surface/radius/shadow craft, accessible charts, browser color-scheme behavior, and actionable copy/error recovery.

The documentation explicitly positions the rules for use with coding agents. This is a strong fit for a **post-art-direction implementation reviewer**.

Caution: the source explicitly distinguishes Vercel-specific brand/copy preferences from more general interface guidance. Preserve that distinction.

## SuperDesign

Current public writing from SuperDesign argues that generic AI design comes from asking the model to supply both taste and execution; its proposed workflow separates human/reference direction from execution and emphasizes inspiration boards / component-level reference grounding.

That premise aligns with #1143's working model. The product itself still needs primary-source repository/setup/license verification before use.

## Environment availability

A search of the currently installable ChatGPT plugin catalog returned no direct plugin for the initial candidate set (21st, Mobbin, SuperDesign, design taste, frontend design).

Therefore this research branch treats them as external web/repository/local-tool candidates. Durable Listen Closer design guidance must remain repo-native and reproducible without a specific ChatGPT plugin.
