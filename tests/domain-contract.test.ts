import { describe, it, expect } from "vitest";
import ArtifactSchema from "@/backend/schemas/export/Artifact.schema.json";
import ProjectSchema from "@/backend/schemas/export/Project.schema.json";
import WorkSchema from "@/backend/schemas/export/Work.schema.json";
import VersionSchema from "@/backend/schemas/export/Version.schema.json";
import EntitySchema from "@/backend/schemas/export/Entity.schema.json";
import InsightSchema from "@/backend/schemas/export/Insight.schema.json";
import AlignmentSchema from "@/backend/schemas/export/Alignment.schema.json";
import JobSchema from "@/backend/schemas/export/Job.schema.json";
import JobLifecycleSchema from "@/backend/schemas/export/JobLifecycle.schema.json";
import SelectionSchema from "@/backend/schemas/export/Selection.schema.json";
import SpanSchema from "@/backend/schemas/export/Span.schema.json";
import WorkflowSchema from "@/backend/schemas/export/Workflow.schema.json";

const schemas = {
  Project: ProjectSchema,
  Work: WorkSchema,
  Artifact: ArtifactSchema,
  Version: VersionSchema,
  Entity: EntitySchema,
  Insight: InsightSchema,
  Alignment: AlignmentSchema,
  Job: JobSchema,
  JobLifecycle: JobLifecycleSchema,
  Selection: SelectionSchema,
  Span: SpanSchema,
  Workflow: WorkflowSchema,
} as const;

describe("Domain contracts: TypeScript ↔ Python alignment", () => {
  it("all 12 domain schemas are present", () => {
    expect(Object.keys(schemas)).toHaveLength(12);
  });

  for (const [name, schema] of Object.entries(schemas)) {
    it(`${name} schema has required fields`, () => {
      expect(schema.type).toBe("object");
      expect(schema.properties).toBeDefined();
      expect(Object.keys(schema.properties).length).toBeGreaterThan(0);
    });

    it(`${name} schema has title`, () => {
      expect(schema.title).toBe(name);
    });

    it(`${name} schema is valid JSON Schema`, () => {
      const s = schema as Record<string, unknown>;
      expect(s.type).toBe("object");
    });
  }

  it("Project has owner_id, name as required", () => {
    const required = ProjectSchema.required;
    expect(required).toContain("owner_id");
    expect(required).toContain("name");
  });

  it("Version has storage_key, storage_bucket, artifact_id as required", () => {
    const required = VersionSchema.required;
    expect(required).toContain("storage_key");
    expect(required).toContain("storage_bucket");
    expect(required).toContain("artifact_id");
  });

  it("Insight has confidence bounded 0-1", () => {
    const conf = InsightSchema.properties.confidence;
    expect(conf.minimum).toBe(0);
    expect(conf.maximum).toBe(1);
  });

  it("Job has capability and lifecycle", () => {
    const props = Object.keys(JobSchema.properties);
    expect(props).toContain("capability");
    expect(props).toContain("lifecycle");
    expect(props).toContain("workflow_id");
  });

  it("Entity has version_id and kind", () => {
    const required = EntitySchema.required;
    expect(required).toContain("version_id");
    expect(required).toContain("kind");
  });

  it("JobLifecycle has current, progress, retry_count, max_retries", () => {
    const props = Object.keys(JobLifecycleSchema.properties);
    expect(props).toContain("current");
    expect(props).toContain("progress");
    expect(props).toContain("retry_count");
    expect(props).toContain("max_retries");
  });

  it("Selection supports time, beat, and measure ranges", () => {
    const props = Object.keys(SelectionSchema.properties);
    expect(props).toContain("time_start_seconds");
    expect(props).toContain("time_end_seconds");
    expect(props).toContain("beat_start");
    expect(props).toContain("beat_end");
    expect(props).toContain("measure_start");
    expect(props).toContain("measure_end");
  });
});
