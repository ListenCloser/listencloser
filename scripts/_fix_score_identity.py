from pathlib import Path

path = Path("backend/domain/api.py")
text = path.read_text()
old_job = 'f"hello-ai:score:1.0:{owner_id}:{version_id}:{score_engine}"'
new_job = 'f"listencloser:score:1.0:{owner_id}:{version_id}:{score_engine}"'
old_workflow = 'f"hello-ai:score-workflow:1.0:{owner_id}:{version_id}:{score_engine}"'
new_workflow = 'f"listencloser:score-workflow:1.0:{owner_id}:{version_id}:{score_engine}"'
for old, new in ((old_job, new_job), (old_workflow, new_workflow)):
    if text.count(old) != 1:
        raise RuntimeError(f"expected one match for {old!r}")
    text = text.replace(old, new, 1)
path.write_text(text)
