"""Markdown report generation for evaluation results."""

from __future__ import annotations

from typing import Any


def write_markdown_report(summary: dict[str, Any], output_path: str) -> None:
    lines: list[str] = []

    lines.append("# Music Quality Evaluation Report")
    lines.append("")
    lines.append(f"**Corpus:** {summary.get('name', 'unnamed')}")
    lines.append(f"**Description:** {summary.get('description', '')}")
    lines.append(f"**Clips:** {summary.get('clip_count', 0)}")
    lines.append(
        f"**Completed:** {summary.get('completed', 0)}  **Failed:** {summary.get('failed', 0)}"
    )
    lines.append("")

    for result in summary.get("results", []):
        if "error" in result:
            lines.append(f"## {result['clip_id']} — ❌ Failed")
            lines.append(f"```\n{result['error']}\n```")
            lines.append("")
            continue

        lines.append(f"## {result['clip_id']} ({result.get('category', '-')})")
        lines.append("")

        lines.append(f"- Processing time: {result.get('transcription_time_s', '?')}s")

        tm = result.get("transcription_metrics")
        if tm:
            lines.append("")
            lines.append("### Transcription")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| Onset-only Note Precision | {tm.get('onset_note_precision', '?')} |")
            lines.append(f"| Onset-only Note Recall | {tm.get('onset_note_recall', '?')} |")
            lines.append(f"| Onset-only Note F1 | {tm.get('onset_note_f1', '?')} |")
            lines.append(
                f"| Onset+Offset Note Precision | {tm.get('onset_offset_note_precision', '?')} |"
            )
            lines.append(
                f"| Onset+Offset Note Recall | {tm.get('onset_offset_note_recall', '?')} |"
            )
            lines.append(f"| Onset+Offset Note F1 | {tm.get('onset_offset_note_f1', '?')} |")
            lines.append(
                "| Matched onset / Matched offset / Predicted / Ref | "
                f"{tm.get('onset_matched_count', '?')} / "
                f"{tm.get('onset_offset_matched_count', '?')} / "
                f"{tm.get('predicted_count', '?')} / "
                f"{tm.get('reference_count', '?')} |"
            )

        bm = result.get("beat_metrics")
        if bm and any(v is not None for v in bm.values()):
            lines.append("")
            lines.append("### Beat")
            lines.append(
                "- BPM: estimated "
                f"{result.get('estimated_bpm', '?')}"
                f"  (abs error: {bm.get('bpm_absolute_error', '?')})"
            )
            if bm.get("beat_f1") is not None:
                lines.append(f"- Beat F1: {bm['beat_f1']}")

        nm = result.get("notation_metrics")
        if nm:
            lines.append("")
            lines.append("### Notation")
            lines.append(f"- Valid MusicXML: {nm['parse_valid']}")
            lines.append(f"- Notes: {nm['total_note_count']}  Measures: {nm['measure_count']}")
            lines.append(
                f"- Short notes: {nm['short_note_count']}"
                f"  Ties: {nm['tie_count']}"
                f"  Tuplets: {nm['tuplet_count']}"
            )
            if nm.get("issues"):
                lines.append("- Issues:")
                for issue in nm["issues"]:
                    lines.append(f"  - {issue}")

        am = result.get("analysis_metrics")
        if am:
            lines.append("")
            lines.append("### Analysis")
            if am.get("key_correct") is not None:
                lines.append(f"- Key correct: {am['key_correct']}")
            if am.get("meter_correct") is not None:
                lines.append(f"- Meter correct: {am['meter_correct']}")

        lines.append("")

    with open(output_path, "w") as fh:
        fh.write("\n".join(lines))
