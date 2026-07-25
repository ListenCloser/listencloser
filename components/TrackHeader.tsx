/**
 * Track header component — displays track info across all feature tabs.
 *
 * WHY: Every feature page (Transform, Visualize, Analysis) needs to show
 * which track is being worked on. Without this, users lose context when
 * switching between tabs. The header provides a consistent anchor point.
 *
 * WHAT IT SHOWS:
 * - Track title
 * - Processing status indicators (from TrackState)
 * - Current artifact being viewed
 */

"use client";

import type { LibFile } from "@/lib/types";
import { deriveTrackState } from "@/lib/types";

type Props = {
  file: LibFile;
  currentArtifact?: string;
};

export default function TrackHeader({ file, currentArtifact }: Props) {
  const state = deriveTrackState(file);

  return (
    <div className="track-header">
      <div className="track-header-title">{file.name}</div>
      <div className="track-header-status">
        {state.transcribed && <span className="track-badge">MIDI</span>}
        {state.sheetMusic && <span className="track-badge">Sheet Music</span>}
        {state.analysis && <span className="track-badge">Analyzed</span>}
      </div>
      {currentArtifact && (
        <div className="track-header-artifact">Viewing: {currentArtifact}</div>
      )}
    </div>
  );
}
