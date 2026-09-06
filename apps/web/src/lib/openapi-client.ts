import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./api-types";
import { supabase } from "./supabase";

export async function withCurrentSupabaseAuth(request: Request): Promise<Request> {
  if (!supabase) return request;

  // Supabase owns token refresh. Read the current session per request so
  // the transport never creates a second, stale bearer-token cache.
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) request.headers.set("Authorization", `Bearer ${token}`);
  return request;
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    return withCurrentSupabaseAuth(request);
  },
};

export const openapiClient = createClient<paths>({});
openapiClient.use(authMiddleware);

export function throwOpenApiError(error: unknown, response: Response): never {
  const message =
    typeof error === "object" && error !== null && "error" in error
      ? (error as { error?: unknown }).error
      : undefined;

  throw new Error(typeof message === "string" ? message : `Request failed: ${response.status}`);
}

export function requireOpenApiData<T>({
  data,
  error,
  response,
}: {
  data?: T;
  error?: unknown;
  response: Response;
}): T {
  if (data === undefined) throwOpenApiError(error, response);
  return data;
}
