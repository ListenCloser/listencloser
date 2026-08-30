import type { QueryClient } from "@tanstack/react-query";
import { getAppQueryClient } from "@/lib/query-client";

const MUSICXML_CACHE_TTL_MS = 5 * 60 * 1000;

function musicXmlKey(versionId: string) {
  return ["artifact-text", "musicxml", versionId] as const;
}

export async function getMusicXml(
  versionId: string,
  signedUrl: string,
  queryClient: QueryClient = getAppQueryClient(),
): Promise<string> {
  return queryClient.fetchQuery({
    queryKey: musicXmlKey(versionId),
    queryFn: async () => {
      const response = await fetch(signedUrl);
      if (!response.ok) throw new Error("score request failed");
      return response.text();
    },
    // Artifact Versions are immutable. The short garbage-collection lifetime
    // bounds browser memory while allowing A → B → A revisits to reuse the
    // exact text even if a refreshed Work bundle carries a new signed URL.
    staleTime: Infinity,
    gcTime: MUSICXML_CACHE_TTL_MS,
  });
}
