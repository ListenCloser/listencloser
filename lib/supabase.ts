import { createClient, SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "./database.types";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Validate URL format — placeholder values like "[SENSITIVE]" are not valid URLs
const isValidUrl = url && url.startsWith("http") && !url.includes("[SENSITIVE]");

export const supabase: SupabaseClient<Database> | null =
  isValidUrl && anonKey
    ? createClient<Database>(url, anonKey, {
        auth: {
          // PKCE flow (default). Google redirects with ?code= to /auth/callback,
          // which the server redirects to the client /auth/confirm page that
          // calls exchangeCodeForSession. Must NOT use implicit flow — it breaks
          // the PKCE code_verifier and yields "bad_oauth_state".
          // detectSessionInUrl is false so the client does NOT auto-exchange the
          // ?code= in the URL on init (which would consume it and make the
          // explicit exchangeCodeForSession on /auth/confirm fail). The explicit
          // call on /auth/confirm is the single source of truth.
          flowType: "pkce",
          detectSessionInUrl: false,
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null;

export const isSupabaseConfigured = Boolean(supabase);
