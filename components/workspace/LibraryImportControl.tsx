"use client";

import {
  Dialog,
  DialogBackdrop,
  DialogPanel,
  DialogTitle,
  Menu,
  MenuButton,
  MenuItem,
  MenuItems,
} from "@headlessui/react";
import { useMemo, useState } from "react";

import {
  filterPublicRecordings,
  type PublicRecording,
} from "@/lib/public-recordings";
import type { ScoreEngine, TranscriptionProfile } from "@/lib/stores/workspace";

import styles from "./LibraryImportControl.module.css";

export type ImportProcessingConfig = {
  transcriptionProfile: TranscriptionProfile;
  scoreEngine: ScoreEngine;
};

type ImportIntent =
  | { kind: "upload" }
  | { kind: "public"; recording: PublicRecording };

type LibraryImportControlProps = {
  disabled: boolean;
  busy?: boolean;
  statusId?: string;
  transcriptionProfile: TranscriptionProfile;
  scoreEngine: ScoreEngine;
  onTranscriptionProfileChange: (profile: TranscriptionProfile) => void;
  onScoreEngineChange: (engine: ScoreEngine) => void;
  onUpload: () => void;
  onImport: (recording: PublicRecording, processing: ImportProcessingConfig) => Promise<void>;
};

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function formatBytes(bytes: number): string {
  const mib = bytes / (1024 * 1024);
  if (mib >= 1) return `${mib.toFixed(mib >= 10 ? 0 : 1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

export default function LibraryImportControl({
  disabled,
  busy = false,
  statusId,
  transcriptionProfile,
  scoreEngine,
  onTranscriptionProfileChange,
  onScoreEngineChange,
  onUpload,
  onImport,
}: LibraryImportControlProps) {
  const [publicOpen, setPublicOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [importIntent, setImportIntent] = useState<ImportIntent | null>(null);
  const [draftTranscriptionProfile, setDraftTranscriptionProfile] = useState(transcriptionProfile);
  const [draftScoreEngine, setDraftScoreEngine] = useState(scoreEngine);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recordings = useMemo(() => filterPublicRecordings(query), [query]);

  function openPublicLibrary() {
    setError(null);
    setQuery("");
    setPublicOpen(true);
  }

  function openProcessing(intent: ImportIntent) {
    setError(null);
    setDraftTranscriptionProfile(transcriptionProfile);
    setDraftScoreEngine(scoreEngine);
    setImportIntent(intent);
  }

  function closeProcessing() {
    if (importingId) return;
    setError(null);
    setImportIntent(null);
  }

  async function confirmProcessing() {
    if (!importIntent || importingId) return;

    const processing: ImportProcessingConfig = {
      transcriptionProfile: draftTranscriptionProfile,
      scoreEngine: draftScoreEngine,
    };
    onTranscriptionProfileChange(processing.transcriptionProfile);
    onScoreEngineChange(processing.scoreEngine);

    if (importIntent.kind === "upload") {
      setImportIntent(null);
      onUpload();
      return;
    }

    const { recording } = importIntent;
    setImportingId(recording.id);
    setError(null);
    try {
      await onImport(recording, processing);
      setImportIntent(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not import this recording.");
    } finally {
      setImportingId(null);
    }
  }

  const processingBusy = importIntent?.kind === "public" && importingId === importIntent.recording.id;

  return (
    <div className={styles.root}>
      <Menu as="div" className={styles.menu}>
        <MenuButton
          className="library-import-btn"
          disabled={disabled}
          aria-label="Import audio"
          aria-busy={busy || undefined}
          aria-describedby={statusId}
        >
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
            <path d="M7.5 2v11M2 7.5h11" />
          </svg>
          <span>Import</span>
        </MenuButton>
        <MenuItems className={styles.menuItems}>
          <MenuItem>
            <button type="button" className={styles.menuItem} onClick={() => openProcessing({ kind: "upload" })}>
              Upload recording
            </button>
          </MenuItem>
          <MenuItem>
            <button type="button" className={styles.menuItem} onClick={openPublicLibrary}>
              Public recordings
            </button>
          </MenuItem>
        </MenuItems>
      </Menu>

      <Dialog
        open={publicOpen}
        onClose={() => {
          if (!importingId) setPublicOpen(false);
        }}
      >
        <DialogBackdrop className={styles.backdrop} />
        <div className={styles.dialogWrap}>
          <DialogPanel className={styles.dialog}>
            <div className={styles.dialogHeader}>
              <div>
                <DialogTitle className={styles.dialogTitle}>Public recordings</DialogTitle>
                <p className={styles.dialogDescription}>Freely reusable recordings from Wikimedia Commons.</p>
              </div>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() => setPublicOpen(false)}
                disabled={Boolean(importingId)}
                aria-label="Close public recordings"
              >
                ×
              </button>
            </div>

            <div className={styles.searchWrap}>
              <label className="sr-only" htmlFor="public-recording-search">Search public recordings</label>
              <input
                id="public-recording-search"
                className={styles.search}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search recordings"
                autoComplete="off"
              />
            </div>

            <div className={styles.list} aria-live="polite">
              {error && <div className={styles.error} role="alert">{error}</div>}
              {recordings.length === 0 ? (
                <div className={styles.empty}>No recordings match that search.</div>
              ) : recordings.map((recording) => (
                <article className={styles.recording} key={recording.id}>
                  <div className={styles.recordingCopy}>
                    <div className={styles.recordingHeading}>
                      <span className={styles.recordingTitle}>{recording.title}</span>
                      <span className={styles.recordingStyle}>{recording.style}</span>
                    </div>
                    <div className={styles.recordingCreator}>{recording.creator}</div>
                    <div className={styles.recordingMeta}>
                      <span>{formatDuration(recording.durationSeconds)}</span>
                      <span>~{formatBytes(recording.estimatedBytes)}</span>
                      <a href={recording.licenseUrl} target="_blank" rel="noreferrer">{recording.licenseLabel}</a>
                      <a href={recording.sourcePageUrl} target="_blank" rel="noreferrer">Source</a>
                    </div>
                  </div>
                  <button
                    type="button"
                    className={styles.importButton}
                    disabled={Boolean(importingId)}
                    onClick={() => {
                      setPublicOpen(false);
                      openProcessing({ kind: "public", recording });
                    }}
                  >
                    Import
                  </button>
                </article>
              ))}
            </div>
          </DialogPanel>
        </div>
      </Dialog>

      <Dialog open={Boolean(importIntent)} onClose={closeProcessing}>
        <DialogBackdrop className={styles.backdrop} />
        <div className={styles.dialogWrap}>
          <DialogPanel className={`${styles.dialog} ${styles.processingDialog}`}>
            <div className={styles.dialogHeader}>
              <div>
                <DialogTitle className={styles.dialogTitle}>Process recording</DialogTitle>
                <p className={styles.dialogDescription}>Choose how this recording should be transcribed and scored.</p>
              </div>
              <button
                type="button"
                className={styles.closeButton}
                onClick={closeProcessing}
                disabled={processingBusy}
                aria-label="Close processing options"
              >
                ×
              </button>
            </div>

            <div className={styles.processingBody}>
              <div className={styles.processingGroup}>
                <span className={styles.processingLabel}>Transcription</span>
                <div className={styles.segmented} role="group" aria-label="Transcription mode">
                  <button
                    type="button"
                    className={styles.segment}
                    aria-pressed={draftTranscriptionProfile === "auto"}
                    data-selected={draftTranscriptionProfile === "auto" || undefined}
                    onClick={() => setDraftTranscriptionProfile("auto")}
                  >
                    Auto
                  </button>
                  <button
                    type="button"
                    className={styles.segment}
                    aria-pressed={draftTranscriptionProfile === "solo_piano"}
                    data-selected={draftTranscriptionProfile === "solo_piano" || undefined}
                    onClick={() => setDraftTranscriptionProfile("solo_piano")}
                  >
                    Solo piano
                  </button>
                </div>
              </div>

              <div className={styles.processingGroup}>
                <span className={styles.processingLabel}>Score</span>
                <div className={styles.segmented} role="group" aria-label="Score reconstruction engine">
                  <button
                    type="button"
                    className={styles.segment}
                    aria-pressed={draftScoreEngine === "musescore"}
                    data-selected={draftScoreEngine === "musescore" || undefined}
                    onClick={() => setDraftScoreEngine("musescore")}
                  >
                    MuseScore
                  </button>
                  <button
                    type="button"
                    className={styles.segment}
                    aria-pressed={draftScoreEngine === "pm2s"}
                    data-selected={draftScoreEngine === "pm2s" || undefined}
                    onClick={() => setDraftScoreEngine("pm2s")}
                  >
                    PM2S
                  </button>
                </div>
              </div>

              <p className={styles.processingHint}>These choices apply to this import.</p>
              {error && <div className={styles.error} role="alert">{error}</div>}
            </div>

            <div className={styles.processingFooter}>
              <button type="button" className={styles.secondaryButton} onClick={closeProcessing} disabled={processingBusy}>
                Cancel
              </button>
              <button type="button" className={styles.primaryButton} onClick={() => void confirmProcessing()} disabled={processingBusy}>
                {processingBusy
                  ? "Importing…"
                  : importIntent?.kind === "public"
                    ? "Import recording"
                    : "Choose audio"}
              </button>
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </div>
  );
}
