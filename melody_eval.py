"""Comprehensive melody extraction evaluation.

Evaluates skyline baseline on POP909 dataset against melody ground truth.
"""

import os
import sys
import io
import json
import numpy as np
import pretty_midi
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))


def extract_pop909_melody(midi_path: str) -> list[dict]:
    """Extract melody notes from POP909 MIDI (MELODY track)."""
    pm = pretty_midi.PrettyMIDI(midi_path)
    melody_notes = []
    for inst in pm.instruments:
        if inst.name.upper() == "MELODY":
            for note in inst.notes:
                melody_notes.append({
                    "pitch": note.pitch,
                    "start": note.start,
                    "end": note.end,
                    "velocity": note.velocity,
                })
    return melody_notes


def skyline_melody(midi_input):
    """Run skyline melody extraction (inline version)."""
    try:
        if isinstance(midi_input, (bytes, bytearray)):
            pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_input))
        else:
            pm = pretty_midi.PrettyMIDI(midi_input)
        notes = [note for inst in pm.instruments if not inst.is_drum for note in inst.notes]
        if len(notes) < 2:
            return None
        notes.sort(key=lambda n: (n.start, -n.pitch))

        line = []
        margins = []
        i = 0
        while i < len(notes):
            window = [notes[i]]
            j = i + 1
            while j < len(notes) and notes[j].start - notes[i].start < 0.03:
                window.append(notes[j])
                j += 1
            best, margin = _pick_melody_note(window, line[-1] if line else None)
            if best is not None:
                line.append(best)
                margins.append(margin)
            i = j

        if len(line) < 2:
            return None

        return [{"pitch": n.pitch, "start": n.start, "end": n.end} for n in line]
    except Exception:
        return None


def _pick_melody_note(window, prev):
    """Pick melody note from onset window."""
    if not window:
        return None, 0.0
    scored = []
    for note in window:
        dur = note.end - note.start
        dur_score = min(dur / 2.0, 1.0)
        if prev is not None:
            leap = abs(note.pitch - prev.pitch)
            leap_score = 1.0 - min(leap / 12.0, 1.0)
        else:
            leap_score = 0.5
        height_score = (note.pitch - 60) / 48.0
        score = dur_score * 0.5 + leap_score * 0.4 + height_score * 0.1
        scored.append((score, note))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_note = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else best_score
    margin = best_score - second_score
    return best_note, margin


def evaluate_melody(pred_notes: list[dict], gt_notes: list[dict],
                    onset_tolerance: float = 0.05) -> dict:
    """Evaluate melody extraction against ground truth."""
    if not gt_notes:
        return {"precision": 0, "recall": 0, "f1": 0, "pred_count": 0, "gt_count": 0}
    
    pred_sorted = sorted(pred_notes, key=lambda n: n["start"])
    gt_sorted = sorted(gt_notes, key=lambda n: n["start"])
    
    matched_gt = set()
    true_positives = 0
    
    for pred in pred_sorted:
        best_match = None
        best_dist = float("inf")
        for i, gt in enumerate(gt_sorted):
            if i in matched_gt:
                continue
            onset_dist = abs(pred["start"] - gt["start"])
            pitch_dist = abs(pred["pitch"] - gt["pitch"])
            if onset_dist <= onset_tolerance and pitch_dist == 0:
                if onset_dist < best_dist:
                    best_dist = onset_dist
                    best_match = i
        if best_match is not None:
            matched_gt.add(best_match)
            true_positives += 1
    
    precision = true_positives / len(pred_sorted) if pred_sorted else 0
    recall = true_positives / len(gt_sorted)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pred_count": len(pred_sorted),
        "gt_count": len(gt_sorted),
        "matched": true_positives,
    }


def run_evaluation(pop909_dir: str, max_songs: int = 50):
    """Run full evaluation on POP909."""
    results = []
    songs = sorted(os.listdir(pop909_dir))[:max_songs]
    
    for song_id in songs:
        song_dir = os.path.join(pop909_dir, song_id)
        midi_path = os.path.join(song_dir, f"{song_id}.mid")
        if not os.path.exists(midi_path):
            continue
        
        try:
            gt_melody = extract_pop909_melody(midi_path)
            if not gt_melody:
                continue
            
            with open(midi_path, 'rb') as f:
                midi_bytes = f.read()
            
            pred_melody = skyline_melody(midi_bytes)
            if pred_melody is None:
                results.append({"song": song_id, "error": "skyline returned None"})
                continue
            
            metrics = evaluate_melody(pred_melody, gt_melody)
            results.append({"song": song_id, **metrics})
        except Exception as e:
            results.append({"song": song_id, "error": str(e)})
    
    return results


if __name__ == "__main__":
    pop909_dir = "/tmp/melody-eval/POP909-Dataset/POP909"
    
    print("=== Skyline Melody Extraction on POP909 ===\n")
    results = run_evaluation(pop909_dir, max_songs=30)
    
    valid = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]
    
    print(f"Songs evaluated: {len(valid)}")
    print(f"Songs errored: {len(errors)}")
    
    if valid:
        precisions = [r["precision"] for r in valid]
        recalls = [r["recall"] for r in valid]
        f1s = [r["f1"] for r in valid]
        
        print(f"\nOverall metrics:")
        print(f"  Precision: {np.mean(precisions):.3f} ± {np.std(precisions):.3f}")
        print(f"  Recall:    {np.mean(recalls):.3f} ± {np.std(recalls):.3f}")
        print(f"  F1:        {np.mean(f1s):.3f} ± {np.std(f1s):.3f}")
        
        print(f"\nPer-song results:")
        for r in valid[:10]:
            print(f"  {r['song']}: P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f} ({r['matched']}/{r['gt_count']})")
