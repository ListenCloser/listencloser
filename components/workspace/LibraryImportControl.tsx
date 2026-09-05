"use client";

import { useMemo, useState } from "react";
import Button, { IconButton } from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogHeading,
} from "@/components/ui/Dialog";
import { CloseIcon, PlusIcon } from "@/components/ui/Icons";
import InlineNotice from "@/components/ui/InlineNotice";
import { Menu, MenuButton, MenuItem, MenuItems } from "@/components/ui/Menu";
import SegmentedControl from "@/components/ui/SegmentedControl";
import TextField from "@/components/ui/TextField";
import ScoreSourceControl from "@/components/workspace/ScoreSourceControl";
import {
  filterPublicRecordings,
  type PublicRecording,
} from "@/lib/public-recordings";
import { useWorkspace, type ScoreEngine, type TranscriptionProfile } from "@/lib/stores/workspace";
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
  const {
    workspace,
    requestAttachScore,
    requestScoreEngine,
    selectScoreSource,
  } = useWorkspace();
  const [publicOpen, setPublicOpen] = useState(false);
  const [scoreSourcesOpen, setScoreSourcesOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [importIntent, setImportIntent] = useState<ImportIntent | null>(null);
  const [draftTranscriptionProfile, setDraftTranscriptionProfile] = useState(transcriptionProfile);
  const [draftScoreEngine, setDraftScoreEngine] = useState(scoreEngine);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recordings = useMemo(() => filterPublicRecordings(query), [query]);
  const canManageScoreSources = Boolean(workspace.activeWorkId) && !workspace.isLoadingWork;

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
      <Menu>
        <MenuButton
          disabled={disabled}
          aria-label="Import audio"
          aria-busy={busy || undefined}
          aria-describedby={statusId}
        >
          <PlusIcon />
          <span>Import</span>
        </MenuButton>
        <MenuItems>
          <MenuItem onClick={() => openProcessing({ kind: "upload" })}>Upload recording</MenuItem>
          <MenuItem onClick={openPublicLibrary}>Public recordings</MenuItem>
          {workspace.activeWorkId && (
            <>
              <MenuItem disabled={!canManageScoreSources || disabled} onClick={requestAttachScore}>
                Attach MusicXML score
              </MenuItem>
              <MenuItem disabled={!canManageScoreSources} onClick={() => setScoreSourcesOpen(true)}>
                Choose score source
              </MenuItem>
            </>
          )}
        </MenuItems>
      </Menu>

      <Dialog
        open={publicOpen}
        onClose={() => {
          if (!importingId) setPublicOpen(false);
        }}
      >
        <DialogHeader>
          <DialogHeading title="Public recordings" description="Freely reusable recordings from Wikimedia Commons." />
          <IconButton variant="ghost" onClick={() => setPublicOpen(false)} disabled={Boolean(importingId)} aria-label="Close public recordings">
            <CloseIcon />
          </IconButton>
        </DialogHeader>
        <DialogBody className={styles.publicBody}>
          <label className="sr-only" htmlFor="public-recording-search">Search public recordings</label>
          <TextField
            id="public-recording-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search recordings"
            autoComplete="off"
          />
          <div className={styles.list} aria-live="polite">
            {error && <InlineNotice tone="danger" role="alert">{error}</InlineNotice>}
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
                <Button
                  size="compact"
                  disabled={Boolean(importingId)}
                  onClick={() => {
                    setPublicOpen(false);
                    openProcessing({ kind: "public", recording });
                  }}
                >
                  Import
                </Button>
              </article>
            ))}
          </div>
        </DialogBody>
      </Dialog>

      <Dialog open={Boolean(importIntent)} onClose={closeProcessing} compact>
        <DialogHeader>
          <DialogHeading title="Process recording" description="Choose how this recording should be transcribed and scored." />
          <IconButton variant="ghost" onClick={closeProcessing} disabled={processingBusy} aria-label="Close processing options">
            <CloseIcon />
          </IconButton>
        </DialogHeader>
        <DialogBody className={styles.processingBody}>
          <div className={styles.processingGroup}>
            <span className={styles.processingLabel}>Transcription</span>
            <SegmentedControl
              label="Transcription mode"
              value={draftTranscriptionProfile}
              options={[
                { value: "auto", label: "Auto" },
                { value: "solo_piano", label: "Solo piano" },
              ]}
              onChange={setDraftTranscriptionProfile}
            />
          </div>
          <div className={styles.processingGroup}>
            <span className={styles.processingLabel}>Score</span>
            <SegmentedControl
              label="Score reconstruction engine"
              value={draftScoreEngine}
              options={[
                { value: "musescore", label: "MuseScore" },
                { value: "pm2s", label: "PM2S" },
              ]}
              onChange={setDraftScoreEngine}
            />
          </div>
          <InlineNotice tone="quiet">These choices apply to this import.</InlineNotice>
          {error && <InlineNotice tone="danger" role="alert">{error}</InlineNotice>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={closeProcessing} disabled={processingBusy}>Cancel</Button>
          <Button variant="primary" onClick={() => void confirmProcessing()} disabled={processingBusy}>
            {processingBusy ? "Importing…" : importIntent?.kind === "public" ? "Import recording" : "Choose audio"}
          </Button>
        </DialogFooter>
      </Dialog>

      <Dialog open={scoreSourcesOpen} onClose={() => setScoreSourcesOpen(false)} compact>
        <DialogHeader>
          <DialogHeading title="Score source" description="Choose the notation evidence shown for this recording." />
          <IconButton variant="ghost" onClick={() => setScoreSourcesOpen(false)} aria-label="Close score source options">
            <CloseIcon />
          </IconButton>
        </DialogHeader>
        <DialogBody className={styles.processingBody}>
          <ScoreSourceControl
            selection={workspace.scoreDisplaySelection}
            sources={workspace.scoreSources}
            disabled={workspace.isLoadingWork}
            attachDisabled={disabled || workspace.isLoadingWork}
            onSelectEngine={requestScoreEngine}
            onSelectSource={selectScoreSource}
            onAttach={requestAttachScore}
          />
          <InlineNotice tone="quiet">
            Attached MusicXML is independent source evidence. It does not replace the performance transcription or imply score-to-audio timing.
          </InlineNotice>
        </DialogBody>
      </Dialog>
    </div>
  );
}
