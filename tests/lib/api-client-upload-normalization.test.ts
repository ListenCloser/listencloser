import { beforeEach, describe, expect, it, vi } from "vitest";

const { post, uploadToSignedUrl } = vi.hoisted(() => ({
  post: vi.fn(),
  uploadToSignedUrl: vi.fn(),
}));

vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { POST: post },
  requireOpenApiData: <T,>({ data, error, response }: { data?: T; error?: unknown; response: Response }): T => {
    if (data !== undefined) return data;
    const message =
      typeof error === "object" && error !== null && "error" in error
        ? (error as { error?: unknown }).error
        : undefined;
    throw new Error(typeof message === "string" ? message : `Request failed: ${response.status}`);
  },
}));
vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/supabase", () => ({
  supabase: {
    storage: {
      from: vi.fn(() => ({ uploadToSignedUrl })),
    },
  },
}));

import { uploadArtifact } from "@/lib/api-client";

const ok = <T,>(data: T) => ({
  data,
  response: new Response(JSON.stringify(data), { status: 200 }),
});

const artifact = {
  id: "artifact-1",
  work_id: "work-1",
  kind: "audio_original" as const,
  mime_type: "audio/wav",
  created_at: "2026-08-30T00:00:00Z",
};

const version = {
  id: "version-1",
  artifact_id: artifact.id,
  parent_version_id: null,
  lineage: [],
  storage_key: "work-1/source.wav",
  storage_bucket: "artifacts",
  byte_size: 5,
  sha256: null,
  created_at: "2026-08-30T00:00:00Z",
  created_by: null,
  produced_by_job_id: null,
  label: "Original",
  metadata: {},
};

describe("generated upload finalize normalization", () => {
  beforeEach(() => {
    post.mockReset();
    uploadToSignedUrl.mockReset();
    uploadToSignedUrl.mockResolvedValue({ error: null });
  });

  it("rejects a finalize response missing a server-materialized Version field", async () => {
    const { metadata: _metadata, ...invalidVersion } = version;
    post
      .mockResolvedValueOnce(ok({
        bucket: "artifacts",
        storage_key: version.storage_key,
        token: "signed-token",
        max_bytes: 10_000,
      }))
      .mockResolvedValueOnce(ok({ artifact, version: invalidVersion }));

    await expect(
      uploadArtifact("project-1", new File(["audio"], "source.wav", { type: "audio/wav" }), "work-1"),
    ).rejects.toThrow('Invalid Version response: missing server field "metadata"');

    expect(uploadToSignedUrl).toHaveBeenCalledTimes(1);
  });
});
