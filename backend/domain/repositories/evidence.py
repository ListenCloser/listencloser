from uuid import UUID

from supabase import Client

from domain.models import (
    Alignment,
    Cadence,
    ChordEntity,
    Entity,
    EntityKind,
    Insight,
    NoteEntity,
    Span,
)
from domain.repositories._base import _Repo, _first


class EntityRepo(_Repo):
    def __init__(self, client: Client, table: str = "entities"):
        super().__init__(client, table)

    def create(self, entity: Entity, owner_id: str) -> Entity:
        self._verify_version_owner(entity.version_id, owner_id)
        row = self._entity_to_row(entity)
        result = self.client.table(self.table).insert(row).execute()
        return self._row_to_entity(_first(result.data))

    def create_many(self, entities: list[Entity], owner_id: str) -> list[Entity]:
        if not entities:
            return []
        version_id = entities[0].version_id
        if any(entity.version_id != version_id for entity in entities):
            raise ValueError("bulk entities must belong to one version")
        self._verify_version_owner(version_id, owner_id)
        rows = [self._entity_to_row(entity) for entity in entities]
        created: list[Entity] = []
        for start in range(0, len(rows), 500):
            result = self.client.table(self.table).insert(rows[start : start + 500]).execute()
            created.extend(self._row_to_entity(row) for row in result.data)
        return created

    def get(self, entity_id: UUID, owner_id: str) -> Entity | None:
        result = self.client.table(self.table).select("*").eq("id", str(entity_id)).execute()
        if not result.data:
            return None
        self._verify_version_owner(UUID(result.data[0]["version_id"]), owner_id)
        return self._row_to_entity(result.data[0])

    def list_by_version(self, version_id: UUID, owner_id: str) -> list[Entity]:
        self._verify_version_owner(version_id, owner_id)
        result = self.client.table(self.table).select("*").eq("version_id", str(version_id)).execute()
        return [self._row_to_entity(r) for r in result.data]

    def delete(self, entity_id: UUID, owner_id: str) -> None:
        e = self.client.table(self.table).select("version_id").eq("id", str(entity_id)).execute()
        if not e.data:
            raise ValueError("entity not found")
        self._verify_version_owner(UUID(e.data[0]["version_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(entity_id)).execute()

    def _verify_version_owner(self, version_id: UUID, owner_id: str) -> None:
        v = (
            self.client.table("artifact_versions")
            .select("artifact_id")
            .eq("id", str(version_id))
            .execute()
        )
        if not v.data:
            raise ValueError("version not found")
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", v.data[0]["artifact_id"])
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = self.client.table("works").select("project_id").eq("id", a.data[0]["work_id"]).execute()
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("version does not belong to caller's project")

    def _entity_to_row(self, entity: Entity) -> dict:
        row: dict = {
            "id": str(entity.id),
            "version_id": str(entity.version_id),
            "kind": entity.kind.value,
            "label": entity.label,
            "start_seconds": entity.span.start_seconds,
            "end_seconds": entity.span.end_seconds,
            "start_beat": entity.span.start_beat,
            "end_beat": entity.span.end_beat,
            "start_measure": entity.span.start_measure,
            "end_measure": entity.span.end_measure,
        }
        if entity.note:
            row["note_pitch"] = entity.note.pitch
            row["note_start_seconds"] = entity.note.start_seconds
            row["note_end_seconds"] = entity.note.end_seconds
            row["note_velocity"] = entity.note.velocity
            row["note_voice"] = entity.note.voice
            if entity.note.amplitude is not None:
                row["note_amplitude"] = entity.note.amplitude
        if entity.chord:
            row["chord_root"] = entity.chord.root
            row["chord_quality"] = entity.chord.quality
            row["chord_bass"] = entity.chord.bass
            row["chord_start_seconds"] = entity.chord.start_seconds
            row["chord_end_seconds"] = entity.chord.end_seconds
        if entity.cadence:
            row["cadence_kind"] = entity.cadence.kind
            row["cadence_chords"] = entity.cadence.chords
            row["cadence_position_seconds"] = entity.cadence.position_seconds
        return row

    def _row_to_entity(self, row: dict) -> Entity:
        span = Span(
            start_seconds=row.get("start_seconds"),
            end_seconds=row.get("end_seconds"),
            start_beat=row.get("start_beat"),
            end_beat=row.get("end_beat"),
            start_measure=row.get("start_measure"),
            end_measure=row.get("end_measure"),
        )
        note = None
        if row.get("note_pitch") is not None:
            note = NoteEntity(
                pitch=row["note_pitch"],
                start_seconds=row["note_start_seconds"],
                end_seconds=row["note_end_seconds"],
                velocity=row.get("note_velocity", 64),
                voice=row.get("note_voice", 0),
                amplitude=row.get("note_amplitude"),
            )
        chord = None
        if row.get("chord_root") is not None:
            chord = ChordEntity(
                root=row["chord_root"],
                quality=row["chord_quality"],
                bass=row.get("chord_bass"),
                start_seconds=row["chord_start_seconds"],
                end_seconds=row["chord_end_seconds"],
            )
        cadence = None
        if row.get("cadence_kind") is not None:
            cadence = Cadence(
                kind=row["cadence_kind"],
                chords=row.get("cadence_chords", []),
                position_seconds=row["cadence_position_seconds"],
            )
        return Entity(
            id=UUID(row["id"]),
            version_id=UUID(row["version_id"]),
            kind=EntityKind(row["kind"]),
            span=span,
            note=note,
            chord=chord,
            cadence=cadence,
            label=row.get("label", ""),
        )


class InsightRepo(_Repo):
    def __init__(self, client: Client, table: str = "insights"):
        super().__init__(client, table)

    def create(self, insight: Insight, owner_id: str) -> Insight:
        self._verify_version_owner(insight.version_id, owner_id)
        row = insight.model_dump(mode="json")
        row["span"] = insight.span.model_dump(mode="json")
        result = self.client.table(self.table).insert(row).execute()
        return Insight.model_validate(_first(result.data))

    def get(self, insight_id: UUID, owner_id: str) -> Insight | None:
        result = self.client.table(self.table).select("*").eq("id", str(insight_id)).execute()
        if not result.data:
            return None
        self._verify_version_owner(UUID(result.data[0]["version_id"]), owner_id)
        return Insight.model_validate(result.data[0])

    def list_by_version(self, version_id: UUID, owner_id: str) -> list[Insight]:
        self._verify_version_owner(version_id, owner_id)
        result = self.client.table(self.table).select("*").eq("version_id", str(version_id)).execute()
        return [Insight.model_validate(r) for r in result.data]

    def delete(self, insight_id: UUID, owner_id: str) -> None:
        i = self.client.table(self.table).select("version_id").eq("id", str(insight_id)).execute()
        if not i.data:
            raise ValueError("insight not found")
        self._verify_version_owner(UUID(i.data[0]["version_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(insight_id)).execute()

    def _verify_version_owner(self, version_id: UUID, owner_id: str) -> None:
        v = (
            self.client.table("artifact_versions")
            .select("artifact_id")
            .eq("id", str(version_id))
            .execute()
        )
        if not v.data:
            raise ValueError("version not found")
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", v.data[0]["artifact_id"])
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = self.client.table("works").select("project_id").eq("id", a.data[0]["work_id"]).execute()
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("version does not belong to caller's project")


class AlignmentRepo(_Repo):
    def __init__(self, client: Client, table: str = "alignments"):
        super().__init__(client, table)

    def create(self, alignment: Alignment, owner_id: str) -> Alignment:
        self._verify_version_owner(alignment.version_id, owner_id)
        data = alignment.model_dump(mode="json")
        result = self.client.table(self.table).insert(data).execute()
        return Alignment.model_validate(_first(result.data))

    def get(self, alignment_id: UUID, owner_id: str) -> Alignment | None:
        result = self.client.table(self.table).select("*").eq("id", str(alignment_id)).execute()
        if not result.data:
            return None
        self._verify_version_owner(UUID(result.data[0]["version_id"]), owner_id)
        return Alignment.model_validate(result.data[0])

    def list_by_version(self, version_id: UUID, owner_id: str) -> list[Alignment]:
        self._verify_version_owner(version_id, owner_id)
        result = self.client.table(self.table).select("*").eq("version_id", str(version_id)).execute()
        return [Alignment.model_validate(r) for r in result.data]

    def delete(self, alignment_id: UUID, owner_id: str) -> None:
        al = self.client.table(self.table).select("version_id").eq("id", str(alignment_id)).execute()
        if not al.data:
            raise ValueError("alignment not found")
        self._verify_version_owner(UUID(al.data[0]["version_id"]), owner_id)
        self.client.table(self.table).delete().eq("id", str(alignment_id)).execute()

    def _verify_version_owner(self, version_id: UUID, owner_id: str) -> None:
        v = (
            self.client.table("artifact_versions")
            .select("artifact_id")
            .eq("id", str(version_id))
            .execute()
        )
        if not v.data:
            raise ValueError("version not found")
        a = (
            self.client.table("artifacts")
            .select("work_id")
            .eq("id", v.data[0]["artifact_id"])
            .execute()
        )
        if not a.data:
            raise ValueError("artifact not found")
        w = self.client.table("works").select("project_id").eq("id", a.data[0]["work_id"]).execute()
        if not w.data:
            raise ValueError("work not found")
        proj = (
            self.client.table("projects")
            .select("id")
            .eq("id", w.data[0]["project_id"])
            .eq("owner_id", owner_id)
            .execute()
        )
        if not proj.data:
            raise PermissionError("version does not belong to caller's project")
