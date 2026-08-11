# Product orchestration

The application has one shipped workflow: durable audio understanding.

## Runtime sequence

1. The authenticated browser uploads audio through Vercel.
2. FastAPI creates a private original artifact and immutable version.
3. FastAPI creates one `understand:1.0` job in Postgres.
4. The worker claims the job with a lease and runs transcription, analysis,
   rendered playback, and score generation.
5. The browser may poll, close, reconnect, cancel, or manually retry the job.
6. The browser reloads the persisted work graph and renders only stored output.

Manual retry creates a new job linked by `retry_of_job_id`; it never erases the
terminal attempt. Automatic retry storage keys include the attempt number, so
partial artifacts remain immutable and cannot collide with later attempts.

Cancellation is cooperative at persisted progress boundaries. A blocking
third-party model call may finish internally, and artifacts already written are
kept as partial results, but subsequent stages stop and the cancelled job cannot
transition back to `succeeded` or be automatically requeued.

## Next capability sequence

1. Release hardening and deployed smoke coverage.
2. Selection-linked melodic, rhythmic, harmonic, and structural analysis.
3. Correction as immutable MIDI/score versions.
4. Comparison using explicit version alignments.
5. Grounded conversational commands over the active work and selection.
6. Human-guided generation with audition, provenance, and accept/reject.

Every new visible action must map to a tested backend capability. An LLM may
orchestrate those capabilities, but it does not own canonical musical state.
