export function getAuthCallbackUrl(next?: string): string {
  const base = "/auth/callback";
  if (next && next !== "/") return `${base}?next=${encodeURIComponent(next)}`;
  return base;
}
