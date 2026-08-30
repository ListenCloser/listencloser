"use client";

import { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { clearWorkDataCache } from "@/lib/api-client";
import { clearMusicXmlCache } from "@/lib/musicxml-cache";
import { supabase, isSupabaseConfigured } from "@/lib/supabase";

type AuthCtx = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthCtx>({
  user: null,
  session: null,
  loading: true,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const authenticatedUserId = useRef<string | null | undefined>(undefined);

  const applySession = useCallback((nextSession: Session | null) => {
    const nextUserId = nextSession?.user.id ?? null;
    const previousUserId = authenticatedUserId.current;

    // User-owned browser caches must never cross authenticated identities.
    // Keep same-user token refreshes from disrupting the active workspace, but
    // clear both mutable Work snapshots and immutable artifact text on change.
    if (previousUserId !== undefined && previousUserId !== nextUserId) {
      clearWorkDataCache();
      clearMusicXmlCache();
    }

    authenticatedUserId.current = nextUserId;
    setSession(nextSession);
  }, []);

  const fetchSession = useCallback(async () => {
    if (!isSupabaseConfigured) {
      setLoading(false);
      return;
    }
    const { data } = await supabase!.auth.getSession();
    applySession(data.session);
    setLoading(false);
  }, [applySession]);

  const signOut = useCallback(async () => {
    await supabase?.auth.signOut();
    applySession(null);
  }, [applySession]);

  useEffect(() => {
    fetchSession();

    if (!isSupabaseConfigured) return;

    const {
      data: { subscription },
    } = supabase!.auth.onAuthStateChange((_event, nextSession) => {
      applySession(nextSession);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, [applySession, fetchSession]);

  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        session,
        loading,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
