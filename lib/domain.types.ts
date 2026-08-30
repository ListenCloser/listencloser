import type { components } from "./api-types";

type Schemas = components["schemas"];
type Complete<T> = { [K in keyof T]-?: Exclude<T[K], undefined> };

export type ArtifactKind = Schemas["ArtifactKind"];
export type WorkflowKind = Schemas["WorkflowKind"];
export type JobStage = Schemas["JobStage"];
export type EntityKind = Schemas["EntityKind"];

// FastAPI marks fields with server-side defaults as optional in OpenAPI even
// though persisted API responses materialize them. Keep that response contract
// explicit while deriving field types from the generated schema.
export type Project = Complete<Schemas["Project"]>;
export type Work = Complete<Schemas["Work"]>;
export type Artifact = Complete<Schemas["Artifact"]>;
export type Version = Complete<Schemas["Version"]>;
export type Capability = Complete<Schemas["Capability"]>;
export type ProcessingStatus = Complete<Schemas["ProcessingStatus"]>;
export type JobLifecycle = Complete<Schemas["JobLifecycle"]>;
export type Workflow = Complete<Schemas["Workflow"]>;
export type Span = Complete<Schemas["Span"]>;

export type Job = Omit<Complete<Schemas["Job"]>, "capability" | "lifecycle"> & {
  capability: Capability;
  lifecycle: JobLifecycle;
};

export type NoteEntity = Schemas["NoteEntity"];
export type ChordEntity = Schemas["ChordEntity"];
export type Cadence = Complete<Schemas["Cadence"]>;

export type Entity = Omit<Schemas["Entity"], "id" | "span" | "note" | "chord" | "cadence"> & {
  id: string;
  span: Span;
  note?: NoteEntity | null;
  chord?: ChordEntity | null;
  cadence?: Cadence | null;
};

export type Insight = Omit<Complete<Schemas["Insight"]>, "span"> & {
  span: Span;
};

export type WorkArtifactBundle = Omit<
  Complete<Schemas["WorkArtifactBundleResponse"]>,
  "artifact" | "latest_version" | "versions"
> & {
  artifact: Artifact;
  latest_version: Version | null;
  versions: Version[];
};

export type WorkBundle = {
  work: Work;
  artifacts: WorkArtifactBundle[];
  jobs: Job[];
};

export type JobStatus = Schemas["JobStateResponse"];

export type VersionResource = {
  artifact: Artifact;
  version: Version;
  signed_url: string;
};
