export const MOCK_PROJECT_REF = "cijhpddqvvzyzfzmkdnn";

export const mockSession = {
  access_token: "e2e-fake-access-token",
  token_type: "bearer",
  expires_in: 3600,
  expires_at: Math.floor(Date.now() / 1000) + 3600,
  refresh_token: "e2e-fake-refresh-token",
  user: {
    id: "00000000-0000-0000-0000-000000000001",
    email: "e2e@example.com",
    aud: "authenticated",
    role: "authenticated",
    app_metadata: {},
    user_metadata: {},
    created_at: new Date().toISOString(),
  },
};

export function persistSessionScript() {
  return ({ projectRef, session }: { projectRef: string; session: unknown }) => {
    try {
      window.localStorage.setItem(
        `sb-${projectRef}-auth-token`,
        JSON.stringify(session),
      );
    } catch {
      /* ignore */
    }
  };
}
