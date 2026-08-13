"""Harmony engine adapters for OSS evaluation.

Adapters for:
- Music21 symbolic (existing baseline)
- lv-chordia (lv-chordia/chordia)
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.engines import EngineInfo, EngineAdapter, EngineCategory

logger = logging.getLogger("eval.engines.harmony")


# ============================================================
# Music21 Symbolic (existing baseline - already in production)
# ============================================================

@dataclass
class Music21HarmonyAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="music21_symbolic",
        category="harmony",
        repo_url="https://github.com/cuthbertLab/music21",
        license="BSD",
        install_cmd="pip install music21",
        model_size_mb=0,
        requires_gpu=False,
        notes="Symbolic analysis via music21. Key, chords, RN, cadences, voice leading, modulations. Current production baseline.",
    )

    def __init__(self, **kwargs):
        pass

    def is_available(self) -> bool:
        try:
            import music21  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        pass

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        import io
        from music21 import converter, chord, roman, voiceLeading, key

        score = converter.parse(io.BytesIO(midi_bytes))

        # Key estimation
        k = score.analyze("key")
        key_result = {
            "tonic": k.tonic.name if k.tonic else "C",
            "mode": k.mode or "major",
            "confidence": float(k.correlationCoefficient) if k.correlationCoefficient else 0.0,
        }

        # Chords
        chords = []
        for ch in score.flatten().getElementsByClass("Chord"):
            try:
                root = ch.root()
                if root is None:
                    continue
                root_name = root.name
                implied = str(ch.impliedQuality) if hasattr(ch, "impliedQuality") else ""
                quality = _quality_map(implied)
                if not quality or quality == "unknown":
                    continue
                start = float(ch.getOffsetInHierarchy(score))
                dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                if dur > 0:
                    chords.append({
                        "root": root_name,
                        "quality": quality,
                        "start": round(start, 3),
                        "end": round(start + dur, 3),
                    })
            except Exception:
                continue

        # Roman numerals
        roman_numerals = []
        detected_key = score.analyze("key")
        for part in score.parts:
            for measure in part.getElementsByClass("Measure"):
                for ch in measure.getElementsByClass("Chord"):
                    try:
                        rn = roman.romanNumeralFromChord(ch, detected_key)
                        if not rn.figure:
                            continue
                        root_p = ch.root()
                        if root_p is None:
                            continue
                        root_name = root_p.name
                        implied = str(rn.impliedQuality) if hasattr(rn, "impliedQuality") else "unknown"
                        quality = _quality_map(implied)
                        if not quality or quality == "unknown":
                            continue
                        start = float(ch.getOffsetInHierarchy(score))
                        dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                        roman_numerals.append({
                            "figure": rn.figure,
                            "root": root_name,
                            "quality": quality,
                            "start": round(start, 3),
                            "end": round(start + dur, 3),
                        })
                    except Exception:
                        continue

        # Cadences
        cadences = []
        patterns = [
            ("authentic", ["V", "I"]), ("plagal", ["IV", "I"]),
            ("half", ["I", "V"]), ("deceptive", ["V", "vi"]),
            ("authentic", ["V7", "I"]), ("authentic", ["V", "i"]),
            ("half", ["i", "V"]), ("deceptive", ["V", "VI"]),
        ]
        chord_seq = []
        for part in score.parts:
            for measure in part.getElementsByClass("Measure"):
                m_start = float(measure.offset) if measure.offset is not None else 0.0
                for ch in measure.getElementsByClass("Chord"):
                    try:
                        rn = roman.romanNumeralFromChord(ch, detected_key)
                        offset = float(ch.getOffsetInHierarchy(score))
                        dur = float(ch.quarterLength) if hasattr(ch, "quarterLength") else 0.0
                        chord_seq.append((offset, rn.figure, dur, m_start))
                    except Exception:
                        continue

        for i in range(len(chord_seq) - 1):
            prev_off, prev_fig, prev_dur, prev_m = chord_seq[i]
            off, fig, dur, m_start = chord_seq[i + 1]
            pair = [prev_fig, fig]
            for cad_type, pattern in patterns:
                if pair == pattern:
                    near_boundary = (off - m_start) <= 0.5
                    long_arrival = dur >= 1.0
                    evidence_score = 0.5
                    if near_boundary:
                        evidence_score += 0.2
                    if long_arrival:
                        evidence_score += 0.1
                    cadences.append({
                        "type": cad_type,
                        "chords": pair,
                        "position": round(off, 3),
                        "evidence_score": round(min(evidence_score, 0.8), 3),
                        "evidence": {
                            "metric_position": "near_measure_boundary" if near_boundary else "mid_measure",
                            "arrival_duration_qn": round(dur, 3),
                            "method": "roman_numeral_pattern",
                        },
                    })
                    break

        # Voice leading
        voice_leading = None
        try:
            parts = [p for p in list(score.parts) if _has_melodic_content(p)]
            if len(parts) >= 2:
                parallel = contrary = oblique = similar = total = 0
                for i in range(min(len(parts), 4)):
                    for j in range(i + 1, min(len(parts), 4)):
                        try:
                            for vlq in voiceLeading.iterateAllVoiceLeadingQuartets(parts[i], parts[j]):
                                motion = vlq.motionType()
                                if "Parallel" in str(motion):
                                    parallel += 1
                                elif "Contrary" in str(motion):
                                    contrary += 1
                                elif "Oblique" in str(motion):
                                    oblique += 1
                                elif "Similar" in str(motion):
                                    similar += 1
                                total += 1
                                if total > 2000:
                                    break
                        except Exception:
                            continue
                        if total > 2000:
                            break
                    if total > 2000:
                        break
                if total > 0:
                    p, c, o, s = (round(n / total, 3) for n in [parallel, contrary, oblique, similar])
                    dominant = max(
                        ("parallel", p), ("contrary", c), ("oblique", o), ("similar", s),
                        key=lambda x: x[1],
                    )
                    voice_leading = {
                        "parallel": p, "contrary": c, "oblique": o, "similar": s,
                        "motion_summary": f"{dominant[0]} motion dominates ({dominant[1] * 100:.0f}%)",
                    }
        except Exception:
            pass

        # Modulations (custom windowed KS)
        modulations = _detect_modulations(score)

        return {
            "key": key_result,
            "chords": chords,
            "roman_numerals": roman_numerals,
            "cadences": cadences,
            "modulations": modulations,
            "voice_leading": voice_leading,
            "phrases": [],  # Not implemented
        }

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# lv-chordia
# ============================================================

@dataclass
class LVChordiaAdapter(EngineAdapter):
    engine_info = EngineInfo(
        name="lv_chordia",
        category="harmony",
        repo_url="https://github.com/lv-chordia/chordia",
        license="MIT",
        install_cmd="pip install chordia",
        model_size_mb=30,
        requires_gpu=False,
        notes="Chord recognition + key estimation using CNN+CRF. Works on audio directly (no MIDI required).",
    )

    def __init__(self, **kwargs):
        self._chordia = None

    def is_available(self) -> bool:
        try:
            import chordia  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self) -> None:
        if self._chordia is not None:
            return
        try:
            from chordia import ChordRecognizer
            self._chordia = ChordRecognizer()
        except Exception as e:
            logger.warning("Chordia prepare failed: %s", e)
            self._chordia = None

    def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
        # Chordia works on audio, not MIDI. For evaluation, we'd need to
        # render MIDI to audio first, or this adapter is audio-native.
        # For now, we'll use pretty_midi to render to WAV and then run chordia.
        # But this is a harmony adapter - it expects MIDI input.
        # Let's render MIDI to audio and run chordia.
        import io
        import soundfile as sf
        import pretty_midi
        import tempfile

        if self._chordia is None:
            self.prepare()
        if self._chordia is None:
            raise RuntimeError("Chordia not available")

        # Render MIDI to audio
        pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            pm.fluidsynth(f)
            temp_path = f.name

        try:
            chords = self._chordia.predict(temp_path)
            # Convert chordia output to our format
            # chordia returns: time, chord_label, confidence
            chord_results = []
            for t, label, conf in chords:
                # Parse label like "C:maj" or "A:min"
                parts = label.split(":")
                if len(parts) == 2:
                    root, quality = parts
                    quality_map = {"maj": "M", "min": "m", "dim": "dim", "aug": "aug"}
                    chord_results.append({
                        "root": root,
                        "quality": quality_map.get(quality, quality),
                        "start": round(float(t), 3),
                        "end": round(float(t) + 1.0, 3),  # Assume 1s duration
                        "confidence": float(conf),
                    })

            # Key estimation from chords (simple heuristic)
            key_result = self._estimate_key_from_chords(chord_results)

            return {
                "key": key_result,
                "chords": chord_results,
                "roman_numerals": [],
                "cadences": [],
                "modulations": [],
                "voice_leading": None,
                "phrases": [],
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def _estimate_key_from_chords(self, chords: list[dict]) -> dict[str, Any]:
        # Simple heuristic: most common root
        from collections import Counter
        roots = [c["root"] for c in chords]
        if not roots:
            return {"tonic": "C", "mode": "major", "confidence": 0.0}
        most_common = Counter(roots).most_common(1)[0][0]
        return {"tonic": most_common, "mode": "major", "confidence": 0.5}

    def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ============================================================
# Helpers
# ============================================================

_QUALITY_MAP = {
    "major": "M", "minor": "m", "diminished": "dim", "augmented": "aug",
    "dominant seventh": "7", "major seventh": "maj7", "minor seventh": "min7",
    "half-diminished": "m7b5", "diminished seventh": "dim7",
    "suspended fourth": "sus4", "major sixth": "6", "minor sixth": "m6",
    "dominant ninth": "9",
}


def _quality_map(implied: str) -> str:
    return _QUALITY_MAP.get(implied, implied)


def _has_melodic_content(part) -> bool:
    try:
        notes = list(part.recurse().getElementsByClass("Note"))
        return len(notes) >= 4
    except Exception:
        return False


_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _key_from_pc_vector(pc_vec):
    import numpy as np
    pc = np.array(pc_vec)
    if pc.sum() <= 0:
        return None
    pc_c = pc - pc.mean()
    pc_c = pc_c / (np.linalg.norm(pc_c) + 1e-10)
    ks_major_c = np.array(_KS_MAJOR) - np.mean(_KS_MAJOR)
    ks_major_c = ks_major_c / np.linalg.norm(ks_major_c)
    ks_minor_c = np.array(_KS_MINOR) - np.mean(_KS_MINOR)
    ks_minor_c = ks_minor_c / np.linalg.norm(ks_minor_c)

    candidates = []
    for shift in range(12):
        rolled = np.roll(pc_c, -shift)
        candidates.append((_NOTES[shift], "major", float(np.dot(rolled, ks_major_c))))
        candidates.append((_NOTES[shift], "minor", float(np.dot(rolled, ks_minor_c))))
    candidates.sort(key=lambda x: x[2], reverse=True)
    best = candidates[0]
    return {"tonic": best[0], "mode": best[1], "confidence": round(min(max(best[2], 0.0), 1.0), 3)}


def _detect_modulations(score, tempo_bpm: float | None = None):
    """Detect key changes using overlapping windows."""
    import numpy as np
    from collections import Counter

    all_notes = []
    for part in score.parts:
        for note in part.recurse().getElementsByClass("GeneralNote"):
            offset = float(note.offset) if note.offset is not None else 0.0
            if hasattr(note, "pitch") and note.pitch is not None:
                all_notes.append((offset, note.pitch.midi))
    if len(all_notes) < 16:
        return []
    all_notes.sort(key=lambda x: x[0])

    qpm = tempo_bpm if tempo_bpm else 120.0
    max_offset_qn = all_notes[-1][0] if all_notes else 1.0
    total_sec = max_offset_qn * 60.0 / qpm
    if total_sec <= 0:
        return []

    window_sec = total_sec / 8.0
    step_sec = window_sec / 2.0

    key_history = []
    t = 0.0
    while t + window_sec <= total_sec + 1e-9:
        t_start_qn = t * qpm / 60.0
        t_end_qn = (t + window_sec) * qpm / 60.0
        pitches = [p for toff, p in all_notes if t_start_qn <= toff < t_end_qn]
        if len(pitches) >= 4:
            pc_dist = np.zeros(12)
            for pc, cnt in Counter(p % 12 for p in pitches).items():
                pc_dist[pc] = cnt
            kr = _key_from_pc_vector(pc_dist)
            if kr is not None:
                key_history.append((t, f"{kr['tonic']} {kr['mode']}"))
        t += step_sec

    runs = []
    for kt, k in key_history:
        if runs and runs[-1][0] == k:
            runs[-1] = (runs[-1][0], runs[-1][1], runs[-1][2] + 1)
        else:
            runs.append((k, kt, 1))

    modulations = []
    for i in range(1, len(runs)):
        prev_key, prev_start, prev_len = runs[i - 1]
        new_key, new_start, new_len = runs[i]
        if new_len >= 3:
            kind = "possible_modulation"
        elif new_len == 2:
            kind = "possible_tonicization"
        else:
            continue
        modulations.append({
            "from_key": prev_key,
            "to_key": new_key,
            "position": round(new_start, 3),
            "kind": kind,
            "run_length_windows": new_len,
            "duration_seconds": round(new_len * step_sec, 3),
            "window_size_seconds": round(window_sec, 3),
        })
    return modulations


# ============================================================
# Registry
# ============================================================

HARMONY_ADAPTERS = {
    "music21_symbolic": Music21HarmonyAdapter,
    "lv_chordia": LVChordiaAdapter,
}


def get_harmony_adapter(name: str, **kwargs) -> EngineAdapter:
    if name not in HARMONY_ADAPTERS:
        raise ValueError(f"Unknown harmony adapter: {name}. Available: {list(HARMONY_ADAPTERS)}")
    return HARMONY_ADAPTERS[name](**kwargs)


def list_harmony_adapters() -> list[str]:
    return list(HARMONY_ADAPTERS.keys())