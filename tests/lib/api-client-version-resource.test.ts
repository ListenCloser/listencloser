import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, apiFetch } = vi.hoisted(() => ({
  get: vi.fn(),
  apiFetch: vi.fn(),
}));

vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { GET: get },
  requireOpenApiData: <T,>({ data, error, response }: { data?: T; error?: unknown; response: Response }): T => {
    if (data !== undefined) return data;
    const message =
      typeof error === "object" && error !== null && "error" in error
        ? (error as { error?: unknown }).error
        : undefined;
    throw new Error(typeof message === "string" ? message : `Request failed: ${response.status}`);
  },
}));
vi.mock("@/lib/api", () => ({ apiFetch }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { getVersionResource } from "@/lib/api-client";

const artifact = {
  id: "00000000-0000-0000-0000-000000000010",
  created_at: "2026-08-30T00:00:00Z",
  kind: "audio_original" as const,
  mime_type: "audio/wav",
  work_id: "00000000-0000-0000-0000-000000000001",
};

const version = {
  artifact_id: artifact.id,
  byte_size: 1024,
  created_at: "2026-08-30T00:00:00Z",
  created_by: null,
  id: "00000000-0000-0000-0000-000000000011",
  label: "original",
  lineage: [],
  metadata: {},
  parent_version_id: null,
  produced_by_job_id: null,
  sha256: "abc123",
  storage_bucket: "artifacts",
  storage_key: "works/test/original.wav",
};

const resource = {
  artifact,
  version,
  signed_url: "https://storage.example.test/signed",
};

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

describe("generated VersionResource transport", () => {
  beforeEach(() => {
    get.mockReset();
    apiFetch.mockReset();
  });

  it("reads the resource through the generated path operation", async () => {
    get.mockResolvedValueOnce(ok(resource));

    await expect(getVersionResource(version.id)).resolves.toEqual(resource);
    expect(get).toHaveBeenCalledWith("/api/v1/versions/{version_id}", {
      params: { path: { version_id: version.id } },
    });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fails closed when Artifact omits a server-materialized field", async () => {
    const { id: _id, ...invalidArtifact } = artifact;
    get.mockResolvedValueOnce(ok({ ...resource, artifact: invalidArtifact }));

    await expect(getVersionResource(version.id)).rejects.toThrow(
      'Invalid Artifact response: missing server field "id"',
    );
  });

  it("fails closed when Version omits a server-materialized field", async () => {
    const { metadata: _metadata, ...invalidVersion } = version;
    get.mockResolvedValueOnce(ok({ ...resource, version: invalidVersion }));

    await expect(getVersionResource(version.id)).rejects.toThrow(
      'Invalid Version response: missing server field "metadata"',
    );
  });
});
