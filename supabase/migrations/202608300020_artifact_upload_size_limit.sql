-- Keep the private artifact bucket's hard Storage boundary aligned with the
-- application upload contract. Storage, not client-declared metadata, is the
-- authoritative guard against oversized direct uploads.
do $$
begin
  update storage.buckets
  set file_size_limit = 26214400
  where id = 'artifacts';

  if not found then
    raise exception 'artifacts storage bucket is missing';
  end if;
end
$$;
