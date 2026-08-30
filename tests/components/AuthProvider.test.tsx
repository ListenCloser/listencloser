import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Session } from "@supabase/supabase-js";
import { beforeEach, describe, expect, it, vi } from "vitest";

const authMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(),
  unsubscribe: vi.fn(),
  clearWorkDataCache: vi.fn(),
  callback: null as null | ((event: string, session: unknown) => void),
}));

vi.mock("@/lib/api-client", () => ({
  clearWorkDataCache: authMocks.clearWorkDataCache,
}));

vi.mock("@/lib/supabase", () => ({
  isSupabaseConfigured: true,
  supabase: {
    auth: {
      getSession: authMocks.getSession,
      signOut: authMocks.signOut,
      onAuthStateChange: authMocks.onAuthStateChange,
    },
  },
}));

import AuthProvider, { useAuth } from "@/components/AuthProvider";

function session(userId: string): Session {
  return { user: { id: userId } } as Session;
}

function Probe() {
  const { user, loading, signOut } = useAuth();
  return (
    <>
      <span data-testid="auth-state">{loading ? "loading" : (user?.id ?? "none")}</span>
      <button type="button" onClick={() => void signOut()}>
        Sign out
      </button>
    </>
  );
}

function emitAuthState(event: string, nextSession: Session | null) {
  if (!authMocks.callback) throw new Error("auth callback not registered");
  act(() => {
    authMocks.callback?.(event, nextSession);
  });
}

describe("AuthProvider cache boundaries", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMocks.callback = null;
    authMocks.getSession.mockResolvedValue({ data: { session: session("user-a") } });
    authMocks.signOut.mockResolvedValue({ error: null });
    authMocks.onAuthStateChange.mockImplementation(
      (callback: (event: string, nextSession: Session | null) => void) => {
        authMocks.callback = callback as (event: string, nextSession: unknown) => void;
        return { data: { subscription: { unsubscribe: authMocks.unsubscribe } } };
      },
    );
  });

  it("clears user-owned caches only when the authenticated identity changes", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("user-a"));
    expect(authMocks.clearWorkDataCache).not.toHaveBeenCalled();

    emitAuthState("TOKEN_REFRESHED", session("user-a"));
    expect(authMocks.clearWorkDataCache).not.toHaveBeenCalled();

    emitAuthState("SIGNED_OUT", null);
    expect(screen.getByTestId("auth-state").textContent).toBe("none");
    expect(authMocks.clearWorkDataCache).toHaveBeenCalledTimes(1);

    emitAuthState("SIGNED_IN", session("user-b"));
    expect(screen.getByTestId("auth-state").textContent).toBe("user-b");
    expect(authMocks.clearWorkDataCache).toHaveBeenCalledTimes(2);
  });

  it("clears caches on explicit sign-out even when no auth event is emitted", async () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("user-a"));
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(authMocks.signOut).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("none"));
    expect(authMocks.clearWorkDataCache).toHaveBeenCalledTimes(1);
  });
});
