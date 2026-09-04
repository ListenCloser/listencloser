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

import styles from "./LibraryImportControl.module.css";

type LibraryImportControlProps = {
  disabled: boolean;
  busy?: boolean;
  statusId?: string;
  onUpload: () => void;
  onImport: (recording: PublicRecording) => Promise<void>;
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
  onUpload,
  onImport,
}: LibraryImportControlProps) {
  const [publicOpen, setPublicOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [importingId, setImportingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recordings = useMemo(() => filterPublicRecordings(query), [query]);

  function openPublicLibrary() {
    setError(null);
    setQuery("");
    setPublicOpen(true);
  }

  async function importRecording(recording: PublicRecording) {
    if (importingId) return;
    setImportingId(recording.id);
    setError(null);
    try {
      await onImport(recording);
      setPublicOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not import this recording.");
    } finally {
      setImportingId(null);
    }
  }

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
            <button type="button" className={styles.menuItem} onClick={onUpload}>
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
              ) : recordings.map((recording) => {
                const importing = importingId === recording.id;
                return (
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
                      onClick={() => void importRecording(recording)}
                    >
                      {importing ? "Importing…" : "Import"}
                    </button>
                  </article>
                );
              })}
            </div>
          </DialogPanel>
        </div>
      </Dialog>
    </div>
  );
}
