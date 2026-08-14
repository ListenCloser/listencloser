# PR Summary: feat: route solo-piano transcription through Transkun

## MAESTRO Decision Evidence

Scored solo-piano benchmark on 15 MAESTRO v3.0.0 test clips (diverse composers, 25s excerpts):

| Engine | Macro Note F1 | Macro Onset F1 | Avg Runtime |
|--------|--------------:|---------------:|------------:|
| basic_pitch | 0.1083 | 0.7112 | 1.1s |
| **transkun** | **0.8034** | **0.9848** | 9.1s |
| piano_transcription | 0.4014 | 0.9687 | 12.6s |

Transkun wins every single clip. Full report: `evaluation/reports/transcription_bakeoff_decision.md`

## Routing Contract

```python
get_transcription_engine(profile="solo_piano")  # -> transkun
get_transcription_engine(profile="general")     # -> basic_pitch
get_transcription_engine(profile="auto")        # -> basic_pitch (default)
get_transcription_engine(name="basic_pitch")    # explicit engine overrides profile
```

No classifier. `auto` does NOT detect piano. Default remains Basic Pitch.

## Dependency / Deployment Requirements

| Item | Value |
|------|-------|
| Package | `transkun==2.0.1` |
| Model | Bundled in package: `transkun/pretrained/2.0.pt` (53.8 MB) + `2.0.conf` |
| License | MIT |
| First-run download | None (model bundled) |
| Cold runtime (54.5s solo piano) | 15.7s |
| Warm runtime | 13.6s |
| Peak RSS | ~509 MB (model + inference) |
| CPU execution | ✅ Works |
| Model caching | ✅ In-memory after first load |

## Canonical Basic Pitch vs Transkun Metrics (real-piano.m4a, 54.5s solo piano)

### Transcription

| Metric | Basic Pitch | Transkun |
|--------|------------:|---------:|
| Raw note count | 234 | 102 |
| Pitch range | 29–93 | 48–93 |
| Notes <150ms | 10 | 5 |
| Notes ≥ MIDI 86 | 18 | 16 |
| Isolated high-register notes | 0 | 2 |
| Max polyphony | 6 | 6 |
| Median note duration | 0.545s | 0.877s |
| Transcription runtime | 5.73s | 14.23s |

### Downstream Pipeline

| Metric | Basic Pitch | Transkun |
|--------|------------:|---------:|
| Notation note count | 234 | 102 |
| Measures | 27 | 28 |
| Score systems | 1 | 1 |
| Tie elements | 102 | 68 |
| Accidental elements | 234 | 102 |
| Pitch range | 29–93 | 48–93 |
| Notes ≥ MIDI 86 | 18 | 16 |
| Analysis insight count | 3 | 3 |
| Key result | C major (0.86) | C major (0.90) |
| Tempo result | 120 BPM (0.9) | 120 BPM (0.9) |
| Meter result | 4/4 (0.9) | 4/4 (0.9) |
| Pipeline runtime (total) | ~6.4s | ~14.7s |

## Visual Evidence

**Piano Rolls** (identical viewport: 0-55s, pitch 21-108):
- `evaluation/reports/engine_comparison/basic_pitch_pianoroll.png`
- `evaluation/reports/engine_comparison/transkun_pianoroll.png`

**Score Screenshots**:
- MusicXML generated for both (PNG rendering has environmental music21 issue; MusicXML files available)

**Synthesized Playback**:
- `evaluation/reports/engine_comparison/basic_pitch_playback.wav`
- `evaluation/reports/engine_comparison/transkun_playback.wav`

**Comparison Page**: `evaluation/reports/engine_comparison/comparison.html`

## Downstream Pipeline Comparison

Both engines successfully complete:
- ✅ Transcription → midi_performance
- ✅ Beat tracking → beat grid
- ✅ Notation (adaptive quantization) → midi_corrected + grand-staff MusicXML
- ✅ Analysis (harmony/melody/rhythm) → key/tempo/meter + insights
- ✅ Provenance includes `profile_requested` and `routing_reason`

## Real-Stack Evidence

**Provenance Example** (solo_piano):
```json
{
  "engine": "transkun",
  "library_version": "2.0.1",
  "model": "transkun_2.0",
  "parameters": {"onset_threshold": 0.5, "frame_threshold": 0.3, "device": "cpu"},
  "profile_requested": "solo_piano",
  "routing_reason": "profile=solo_piano -> engine=transkun"
}
```

**Provenance Example** (general):
```json
{
  "engine": "basic_pitch",
  "library_version": "0.4.0",
  "parameters": {"onset_threshold": 0.5, "frame_threshold": 0.3},
  "profile_requested": "general",
  "routing_reason": "profile=general -> engine=basic_pitch"
}
```

## Current User Behavior (Explicit)

**`auto` does NOT detect piano.** Default routing remains Basic Pitch for all inputs unless caller explicitly specifies `transcription_profile="solo_piano"`.

No existing frontend/API flow sets `solo_piano` automatically. Production routing is implemented, but ordinary UI transcription continues to use `auto`/Basic Pitch until a later UX/profile-selection PR.

No classifier added. No frontend selector in this PR.

## Regression Tests (334 passing)

- New routing/unit tests: `tests/test_transcription_profile_routing.py` (10 tests)
- Profile-based routing in registry
- Provenance includes `profile_requested` + `routing_reason`
- Explicit engine override remains authoritative
- `handle_transcribe` signature supports `transcription_profile`
- Engine suite: 76/77 pass (1 pre-existing `test_beat_this.py` failure)
- Full suite: 334 pass (excluding pre-existing failures)

## Known Operational Limitations

1. **Memory**: ~509 MB peak RSS — ensure production workers have ≥1 GB available
2. **Latency**: 13-16s per 54.5s audio — consider async processing for long files
3. **No classifier**: Caller must explicitly request `solo_piano`
4. **Score PNG rendering**: Environmental music21 issue; MusicXML output is valid
5. **Model security warning**: PyTorch `weights_only=False` — acceptable since model is bundled and trusted

## Files Changed

```
backend/engines/transcription/transkun.py          # New production engine
backend/engines/registry.py                        # Profile-based routing
backend/music_features.py                          # Profile param + provenance
backend/domain/capabilities.py                     # handle_transcribe supports profile
backend/tests/test_transcription_profile_routing.py # 10 new tests
backend/CURRENT_USER_BEHAVIOR.md                   # Behavior documentation
backend/evaluation/reports/transcription_bakeoff_decision.md
backend/evaluation/reports/engine_comparison/      # Visual/audio evidence
```

## Stop for Review