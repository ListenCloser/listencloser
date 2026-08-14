# Transkun Production Integration — Current User Behavior

## Routing Contract

| Profile | Engine | Use Case |
|---------|--------|----------|
| `solo_piano` | Transkun | Explicitly requested for solo piano recordings |
| `general` | Basic Pitch | Explicitly requested for general/unknown content |
| `auto` | Basic Pitch | **Default** — no automatic piano detection |
| (omitted) | Basic Pitch | **Default** — same as `auto` |

## Key Design Decision: No Classifier

**`auto` does NOT detect piano.** The default routing remains Basic Pitch for all inputs unless the caller explicitly specifies `transcription_profile="solo_piano"`.

This is intentional:
- No automatic instrument/genre classifier exists in this codebase
- We explicitly chose not to invent one in this PR
- Routing is deterministic and explicit

## Who Sets `solo_piano` Today?

**No existing frontend/API flow sets `solo_piano` automatically.**

The profile must be set explicitly by the caller:
- API clients can pass `transcription_profile="solo_piano"` in job parameters
- Internal tooling/scripts can set it for known solo-piano content
- Future UX/profile-selection PR will add user-facing selection

## Production Behavior

```
Ordinary UI transcription (no profile specified)
  → handle_transcribe
  → get_transcription_engine_for_job(profile=None)
  → get_transcription_engine(profile=None)  # "auto" default
  → Basic Pitch (current production engine)

Explicit solo_piano request
  → handle_transcribe(parameters={"transcription_profile": "solo_piano"})
  → get_transcription_engine_for_job(profile="solo_piano")
  → get_transcription_engine(profile="solo_piano")
  → Transkun (new piano-specialist engine)
```

## Migration Path

1. **This PR**: Routing implemented, default unchanged
2. **Future PR**: Add UX for profile selection (e.g., "Piano" toggle in upload flow)
3. **Future PR**: If classifier is developed, `auto` could route to Transkun for detected solo piano

## Provenance Tracking

Every transcription job persists:
```json
{
  "provenance": {
    "engine": "transkun|basic_pitch",
    "profile_requested": "solo_piano|general|auto",
    "routing_reason": "profile=solo_piano -> engine=transkun",
    ...
  }
}
```

This enables auditing which engine was used and why.

## No Breaking Changes

- Existing jobs without `transcription_profile` continue to use Basic Pitch
- `TRANSCRIPTION_ENGINE` env var still works as fallback
- Explicit `transcription_engine` parameter still overrides profile
- All existing tests pass