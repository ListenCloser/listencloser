# OSS Engine Evaluation Report

Generated: 2026-08-13T18:40:14

## basic_pitch (transcription)

- **License**: MIT
- **Model size**: 30 MB
- **Requires GPU**: False
- **Clips**: 10/10 succeeded
- **Scored**: 5 clips, **Ineligible**: 5 clips
- **Avg runtime**: 1.70s
- **Avg memory**: 20.3 MB
- **Aggregate metrics**: {'macro_note_f1': 0.06523999999999999, 'macro_precision': 0.07588, 'macro_recall': 0.06005999999999999, 'clips_scored': 5, 'clips_ineligible': 5}

## librosa (beat_tracking)

- **License**: ISC
- **Model size**: N/A MB
- **Requires GPU**: False
- **Clips**: 10/10 succeeded
- **Scored**: 5 clips, **Ineligible**: 5 clips
- **Avg runtime**: 0.11s
- **Avg memory**: 98.3 MB
- **Aggregate metrics**: {'macro_f_measure': 0.30886, 'clips_scored': 5, 'clips_ineligible': 5}

## beat_this (beat_tracking)

- **License**: MIT
- **Model size**: 50 MB
- **Requires GPU**: True
- **Clips**: 10/10 succeeded
- **Scored**: 5 clips, **Ineligible**: 5 clips
- **Avg runtime**: 0.30s
- **Avg memory**: 4.3 MB
- **Aggregate metrics**: {'macro_f_measure': 0.33515999999999996, 'clips_scored': 5, 'clips_ineligible': 5}

## music21_symbolic (harmony)

- **License**: BSD
- **Model size**: N/A MB
- **Requires GPU**: False
- **Clips**: 5/10 succeeded
- **Avg runtime**: 0.22s
- **Avg memory**: 3.3 MB
- **Aggregate metrics**: {'macro_key_accuracy': 0, 'macro_chord_f1': 0, 'clips_scored': 5, 'clips_ineligible': 0}
- **Failures**: 5 clips

