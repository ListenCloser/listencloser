-- Preserve Basic Pitch per-note inference evidence (note amplitude) alongside
-- canonical note entities.  The persisted performance MIDI remains standard
-- MIDI; this column only enriches the note metadata.
alter table entities add column if not exists note_amplitude double precision;
