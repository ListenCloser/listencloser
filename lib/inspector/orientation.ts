export const WORKSPACE_ORIENTATION_EVENT = "workspace:orient-selection";

/**
 * Request a short, presentation-only orientation cue for the active Canvas.
 *
 * The durable target remains the shared workspace selection. This event is
 * intentionally ephemeral so orientation feedback does not become another
 * authoritative workspace state channel.
 */
export function requestWorkspaceOrientation(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(WORKSPACE_ORIENTATION_EVENT));
}
