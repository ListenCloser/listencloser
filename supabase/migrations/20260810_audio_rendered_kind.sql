begin;

alter type artifact_kind add value if not exists 'audio_rendered';

commit;
