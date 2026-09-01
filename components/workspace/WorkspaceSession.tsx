"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/AuthProvider";
import type { ServiceStatus } from "@/components/workspace/WorkspaceShell";
import {
  cancelJob,
  getEntities,
  getInsights,
  getWorkBundle,
  retryJob,
  startCompareWorkflow,
  startUnderstandWorkflow,
  startVariationWorkflow,
  uploadArtifact,
} from "@/lib/api-client";
import { getMusicXml } from "@/lib/musicxml-cache";
import { JobObservationError, waitForJob, sanitizeJobError } from "@/lib/job-tracking";
import { refreshProjectWorks, useLibraryProject, useProjectWorks } from "@/lib/server-state";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { understandStageLabel, presentableTitle } from "@/lib/format";
import { buildPlaybackSources } from "@/lib/playback-sources";
import { canPublishWorkLoad } from "@/lib/work-load-authority";
import {
  useWorkspace,
  type RepresentationEntry,
} from "@/lib/stores/workspace";

const ACCEPT = ".wav,.mp3,.m4a,.flac,.ogg,.aac,audio/*";
const ALLOWED_EXTENSIONS = new Set(["wav", "mp3", "m4a", "flac", "ogg", "aac"]);
const ACTIVE_JOB_STATES = new Set(["queued", "claimed", "running"]);
const PROCESSING_REFRESH_MS = 1200;
type UploadStage = "idle" | "uploading" | "processing" | "disconnected" | "success" | "error";

export default function WorkspaceSession({ serviceStatus }: { serviceStatus: ServiceStatus }) {
  const { user } = useAuth();
  const {
    replaceRepresentations,
    setActiveWorkId,
    setAnalysisState,
    setInsights,
    setLoadingWork,
    setStudioOperation,
    setTakes,
    workspace,
  } = useWorkspace();
  const transcriptionProfile = workspace.transcriptionProfile;
  const { replaceSources } = useTransport();
  const { setBpm, setTimeSignature, resetTimeline } = useTimeline();
  const queryClient = useQueryClient();
  const projectQuery = useLibraryProject(user?.id ?? "");
  const projectId = projectQuery.data?.id ?? "";
  const worksQuery = useProjectWorks(projectId);
  const works = worksQuery.data ?? [];
  const [stage, setStage] = useState<UploadStage>("idle");
  const [filename, setFilename] = useState("");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [processingWorkId, setProcessingWorkId] = useState<string | null>(null);
  const [pendingSourceVersionId, setPendingSourceVersionId] = useState<string | null>(null);
  const [loadWarnings, setLoadWarnings] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadSequenceRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadedWorkRef = useRef<string | null>(null);
  const initializedProjectSelectionRef = useRef<string | null>(null);
  // A completed request is not automatically allowed to publish into the
  // workspace. The selected Work is the user-facing authority, and it can
  // change while an import/open request is still in flight.
  const activeWorkIdRef = useRef<string | null>(workspace.activeWorkId);
  activeWorkIdRef.current = workspace.activeWorkId;

  const clearProcessingRefresh = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const loadWork = useCallback(async (workId: string) => {
    // Background completion/polling for another Work must not clear or
    // repopulate the shared workspace after the user has selected elsewhere.
    // This guard must run before cancelling the current request, because that
    // current request may be the selected Work's open.
    if (activeWorkIdRef.current !== workId) return;

    const preserveWorkspace = loadedWorkRef.current === workId;
    loadedWorkRef.current = workId;
    const sequence = ++loadSequenceRef.current;
    clearProcessingRefresh();
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    const isCurrentLoad = () => canPublishWorkLoad({
      workId,
      activeWorkId: activeWorkIdRef.current,
      sequence,
      latestSequence: loadSequenceRef.current,
    });

    setLoadingWork(!preserveWorkspace);
    setError(null);
    setLoadWarnings([]);
    if (!preserveWorkspace) {
      setActiveJobId(null);
      setProcessingWorkId(null);
      setPendingSourceVersionId(null);
      resetTimeline();
      replaceRepresentations([]);
      replaceSources([]);
      setInsights([]);
      setTakes([]);
      setAnalysisState("idle");
    }

    try {
      const bundle = await getWorkBundle(workId);
      if (!isCurrentLoad()) return;

      const latestJob = bundle.jobs[0];
      const activeJob = latestJob && ACTIVE_JOB_STATES.has(latestJob.lifecycle.current) ? latestJob : undefined;
      const terminalJob = latestJob && ["failed", "cancelled"].includes(latestJob.lifecycle.current)
        ? latestJob
        : undefined;

      if (activeJob) {
        setActiveJobId(activeJob.id);
        setProcessingWorkId(workId);
        setPendingSourceVersionId(null);
        setAnalysisState("analyzing");
        setFilename(bundle.work.title);
        setStage("processing");
        setProgress(Math.round(activeJob.lifecycle.progress * 100));
        setMessage(understandStageLabel(activeJob.lifecycle.progress));
      }

      const latestByKind = new Map<string, (typeof bundle.artifacts)[number]>();
      for (const item of bundle.artifacts) {
        if (item.latest_version && item.signed_url && !latestByKind.has(item.artifact.kind)) {
          latestByKind.set(item.artifact.kind, item);
        }
      }

      const original = latestByKind.get("audio_original");
      const baseMidi = latestByKind.get("midi_performance");
      const midi = baseMidi ?? latestByKind.get("midi_corrected");
      const score = latestByKind.get("musicxml_score");
      const renderedScore = latestByKind.get("rendered_score");

      const takeArtifacts = bundle.artifacts.filter((item) =>
        item.latest_version && item.signed_url && ["midi_performance", "midi_corrected"].includes(item.artifact.kind),
      );
      setTakes(takeArtifacts.flatMap((item) => item.latest_version ? [{
        versionId: item.latest_version.id,
        label: item.artifact.kind === "midi_performance" ? "Transcription" : item.latest_version.label || "Derived take",
        parentVersionId: item.latest_version.parent_version_id,
      }] : []));

      const renderedArtifacts = bundle.artifacts.filter((item) =>
        item.latest_version && item.signed_url && item.artifact.kind === "audio_rendered",
      );
      const primaryRendered = renderedArtifacts.find(
        (item) => item.latest_version?.parent_version_id === baseMidi?.latest_version?.id,
      ) ?? renderedArtifacts.find(
        (item) => item.latest_version?.parent_version_id === midi?.latest_version?.id,
      ) ?? renderedArtifacts[0];
      const extraRendered = renderedArtifacts.filter(
        (item) => item.latest_version && item.signed_url && item.latest_version.id !== primaryRendered?.latest_version?.id,
      );
      const { sources, activeId } = buildPlaybackSources({
        original: original?.latest_version && original.signed_url ? { id: original.latest_version.id, url: original.signed_url } : null,
        transcription: primaryRendered?.latest_version && primaryRendered.signed_url ? { id: primaryRendered.latest_version.id, url: primaryRendered.signed_url } : null,
        extraTakes: extraRendered.map((item) => ({ id: item.latest_version!.id, url: item.signed_url! })),
        score: renderedScore?.latest_version && renderedScore.signed_url ? { id: renderedScore.latest_version.id, url: renderedScore.signed_url } : null,
      });

      const representations: RepresentationEntry[] = [];
      if (original?.signed_url) {
        representations.push({
          kind: "waveform",
          label: "Waveform",
          sourceUrl: original.signed_url,
          sourceLabel: "Playback source",
          confidence: null,
          provenance: "uploaded source",
          audioUrl: original.signed_url,
          versionId: original.latest_version?.id,
        });
      }

      // The durable source is the first usable workspace state. Processing may
      // still be running, but it must not hold playback behind a job modal.
      replaceSources(sources, activeId ?? undefined, preserveWorkspace);
      if (representations.length > 0) {
        replaceRepresentations([...representations]);
        setLoadingWork(false);
      }

      const midiVersionId = midi?.latest_version?.id ?? null;
      const entitiesPromise: Promise<Awaited<ReturnType<typeof getEntities>>> = midiVersionId
        ? getEntities(midiVersionId)
        : Promise.resolve([]);
      const insightsPromise: Promise<Awaited<ReturnType<typeof getInsights>>> = midiVersionId
        ? getInsights(midiVersionId)
        : Promise.resolve([]);
      const scoreVersionId = score?.latest_version?.id ?? null;
      const scorePromise: Promise<string | null> = score?.signed_url && scoreVersionId
        ? getMusicXml(scoreVersionId, score.signed_url, queryClient)
        : Promise.resolve(null);

      const upsertLocalRepresentation = (representation: RepresentationEntry) => {
        const index = representations.findIndex((item) => item.kind === representation.kind);
        if (index >= 0) representations[index] = representation;
        else representations.push(representation);
      };
      const publishRepresentation = (representation: RepresentationEntry) => {
        if (!isCurrentLoad()) return;
        upsertLocalRepresentation(representation);
        replaceRepresentations([...representations]);
      };
      const pianoRepresentation = (entities: Awaited<ReturnType<typeof getEntities>>): RepresentationEntry | null => {
        const notes = entities.flatMap((entity) => entity.note ? [{
          id: entity.id,
          pitch: entity.note.pitch,
          start: entity.note.start_seconds,
          end: entity.note.end_seconds,
          velocity: entity.note.velocity,
        }] : []);
        if (!midiVersionId || notes.length === 0) return null;
        return {
          kind: "piano_roll",
          label: "Piano Roll",
          sourceUrl: midi?.signed_url ?? "",
          sourceLabel: `${notes.length} detected notes`,
          confidence: null,
          provenance: "transcription",
          notes,
          versionId: midiVersionId,
        };
      };
      const scoreRepresentation = (musicxml: string | null): RepresentationEntry | null => {
        if (!score?.signed_url || !musicxml) return null;
        const measureStarts = (renderedScore?.latest_version?.metadata?.measure_starts_seconds as number[] | undefined) ?? [];
        return {
          kind: "score",
          label: "Score",
          sourceUrl: score.signed_url,
          sourceLabel: "Notation draft",
          confidence: null,
          provenance: "music21 notation",
          musicxml,
          measureStarts,
          versionId: score.latest_version?.id,
        };
      };
      const publishInsightContext = (pendingInsights: Awaited<ReturnType<typeof getInsights>>) => {
        if (!isCurrentLoad()) return;
        setInsights(pendingInsights);
        const tempo = pendingInsights.find((item) => item.kind === "tempo")?.evidence.bpm;
        if (typeof tempo === "number" && tempo > 0) setBpm(tempo);
        const signature = pendingInsights.find((item) => item.kind === "time_signature")?.evidence;
        if (typeof signature?.numerator === "number" && typeof signature?.denominator === "number") {
          setTimeSignature(signature.numerator, signature.denominator);
        }
      };

      // These three children are independent product surfaces. Keep the
      // requests concurrent, but publish each successful result immediately so
      // a slow MusicXML fetch cannot hold back Piano Roll or analysis (and vice
      // versa). The original promises are still awaited below for final warning
      // reconciliation, so this does not add requests or a second cache.
      void entitiesPromise.then((entities) => {
        const representation = pianoRepresentation(entities);
        if (representation) publishRepresentation(representation);
      }).catch(() => undefined);
      void insightsPromise.then((pendingInsights) => {
        publishInsightContext(pendingInsights);
      }).catch(() => undefined);
      void scorePromise.then((musicxml) => {
        const representation = scoreRepresentation(musicxml);
        if (representation) publishRepresentation(representation);
      }).catch(() => undefined);

      const [entitiesResult, insightsResult, scoreResult] = await Promise.allSettled([
        entitiesPromise,
        insightsPromise,
        scorePromise,
      ]);
      if (!isCurrentLoad()) return;

      const warnings: string[] = [];
      const entities = entitiesResult.status === "fulfilled" ? entitiesResult.value : [];
      const pendingInsights = insightsResult.status === "fulfilled" ? insightsResult.value : [];
      if (midiVersionId && entitiesResult.status === "rejected") warnings.push("Piano roll data is temporarily unavailable.");
      if (midiVersionId && insightsResult.status === "rejected") warnings.push("Analysis is temporarily unavailable.");

      const pendingPianoRoll = pianoRepresentation(entities);
      if (pendingPianoRoll) upsertLocalRepresentation(pendingPianoRoll);

      let pendingTempo: number | null = null;
      let pendingSignature: { numerator: number; denominator: number } | null = null;
      const tempo = pendingInsights.find((item) => item.kind === "tempo")?.evidence.bpm;
      if (typeof tempo === "number" && tempo > 0) pendingTempo = tempo;
      const signature = pendingInsights.find((item) => item.kind === "time_signature")?.evidence;
      if (typeof signature?.numerator === "number" && typeof signature?.denominator === "number") {
        pendingSignature = { numerator: signature.numerator, denominator: signature.denominator };
      }

      if (score?.signed_url) {
        if (scoreResult.status === "fulfilled" && scoreResult.value) {
          const pendingScore = scoreRepresentation(scoreResult.value);
          if (pendingScore) upsertLocalRepresentation(pendingScore);
        } else if (scoreResult.status === "rejected") {
          warnings.push("Score data is temporarily unavailable.");
        }
      }

      replaceRepresentations(representations);
      setInsights(pendingInsights);
      if (pendingTempo !== null) setBpm(pendingTempo);
      if (pendingSignature !== null) setTimeSignature(pendingSignature.numerator, pendingSignature.denominator);
      setLoadWarnings(warnings);

      if (activeJob) {
        // Re-fetch the source-of-truth bundle rather than inventing local stage
        // thresholds. If MIDI/score/insights become durable mid-job they will
        // appear on the next poll without changing the active view or source.
        refreshTimerRef.current = setTimeout(() => {
          if (isCurrentLoad() && loadedWorkRef.current === workId) {
            void loadWork(workId);
          }
        }, PROCESSING_REFRESH_MS);
      } else if (terminalJob) {
        setAnalysisState("completed");
        setProcessingWorkId(workId);
        setActiveJobId(terminalJob.id);
        setError(sanitizeJobError(terminalJob.error || terminalJob.lifecycle.message || `Understanding audio ${terminalJob.lifecycle.current}`));
        setStage("error");
      } else if (original?.latest_version && !midi && !score) {
        setAnalysisState("idle");
        setActiveJobId(null);
        setPendingSourceVersionId(original.latest_version.id);
        setProcessingWorkId(workId);
        setError(null);
        setStage("success");
      } else if (representations.length === 0) {
        setAnalysisState("idle");
        setActiveJobId(null);
        setProcessingWorkId(null);
        setError(null);
        setStage("success");
      } else {
        setAnalysisState("completed");
        setActiveJobId(null);
        setPendingSourceVersionId(null);
        setProcessingWorkId(null);
        setError(null);
        setStage("success");
      }
    } catch (cause) {
      if (!isCurrentLoad()) return;
      if (preserveWorkspace) {
        setProcessingWorkId(workId);
        setError(cause instanceof Error ? cause.message : "Could not refresh processing status");
        setStage("disconnected");
      } else {
        setError(cause instanceof Error ? cause.message : "Could not load this recording");
        setStage("error");
      }
    } finally {
      if (isCurrentLoad()) setLoadingWork(false);
    }
  }, [clearProcessingRefresh, queryClient, replaceRepresentations, replaceSources, resetTimeline, setAnalysisState, setBpm, setInsights, setLoadingWork, setTakes, setTimeSignature]);

  useEffect(() => () => {
    abortRef.current?.abort();
    clearProcessingRefresh();
  }, [clearProcessingRefresh]);

  useEffect(() => {
    if (workspace.activeWorkId === null) {
      abortRef.current?.abort();
      clearProcessingRefresh();
    }
  }, [clearProcessingRefresh, workspace.activeWorkId]);

  const handledStudioAction = useRef(0);
  useEffect(() => {
    const action = workspace.studioAction;
    if (!action || action.id === handledStudioAction.current || !projectId || !workspace.activeWorkId) return;
    handledStudioAction.current = action.id;
    const workId = workspace.activeWorkId;
    void (async () => {
      const label = action.kind === "variation" ? "Creating a playable take" : "Comparing saved takes";
      setStudioOperation({ state: "running", label, message: "Queued" });
      try {
        const result = action.kind === "variation"
          ? await startVariationWorkflow(action.versionIds[0], projectId, action.semitones ?? 0)
          : await startCompareWorkflow(action.versionIds[0], action.versionIds[1], projectId);
        await waitForJob(result.job.id, (current) => {
          setStudioOperation({ state: "running", label, message: current.message || "Working" });
        });
        await loadWork(workId);
        setStudioOperation({
          state: "success",
          label: action.kind === "variation" ? "New take is ready" : "Comparison is ready",
          message: action.kind === "variation" ? "The new take is ready to audition." : "Comparison is ready.",
        });
      } catch (cause) {
        const disconnected = cause instanceof JobObservationError;
        setStudioOperation({
          state: disconnected ? "disconnected" : "error",
          label: disconnected ? "Connection interrupted" : "Operation failed",
          message: cause instanceof Error ? cause.message : "Please try again.",
        });
      }
    })();
  }, [loadWork, projectId, setStudioOperation, workspace.activeWorkId, workspace.studioAction]);

  useEffect(() => {
    if (projectQuery.isError || worksQuery.isError) {
      setLoadingWork(false);
      setError("Could not load your library");
      setStage("error");
      return;
    }
    if (projectQuery.isPending || (projectId && worksQuery.isPending)) {
      setLoadingWork(true);
      return;
    }
    if (!projectId) return;

    const activeWorkStillExists = Boolean(
      workspace.activeWorkId && works.some((work) => work.id === workspace.activeWorkId),
    );
    const isInitialSelectionForProject = initializedProjectSelectionRef.current !== projectId;
    if (isInitialSelectionForProject) {
      initializedProjectSelectionRef.current = projectId;
      if (activeWorkStillExists) return;
      if (works[0]) setActiveWorkId(works[0].id);
      else {
        setActiveWorkId(null);
        setLoadingWork(false);
      }
      return;
    }

    if (!workspace.activeWorkId) {
      setLoadingWork(false);
      return;
    }
    if (activeWorkStillExists) return;

    if (works[0]) setActiveWorkId(works[0].id);
    else {
      setActiveWorkId(null);
      setLoadingWork(false);
    }
  }, [
    projectId,
    projectQuery.isError,
    projectQuery.isPending,
    setActiveWorkId,
    setLoadingWork,
    workspace.activeWorkId,
    works,
    worksQuery.isError,
    worksQuery.isPending,
  ]);

  useEffect(() => {
    if (workspace.activeWorkId) void loadWork(workspace.activeWorkId);
  }, [loadWork, workspace.activeWorkId]);

  useEffect(() => {
    if (workspace.importRequestId > 0) fileInputRef.current?.click();
  }, [workspace.importRequestId]);

  const handleFile = useCallback(async (file: File) => {
    setProcessingWorkId(null);
    setActiveJobId(null);
    if (!projectId) {
      setError("Your library is still loading.");
      setStage("error");
      return;
    }
    if (serviceStatus === "unavailable") {
      setError("Audio processing is temporarily unavailable. Your file was not uploaded.");
      setStage("error");
      return;
    }
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.has(extension)) {
      setError("Choose a WAV, MP3, M4A, FLAC, OGG, or AAC audio file.");
      setStage("error");
      return;
    }

    setFilename(file.name);
    setPendingSourceVersionId(null);
    setStage("uploading");
    setProgress(2);
    setMessage("");
    setError(null);
    try {
      const { artifact, version } = await uploadArtifact(projectId, file);
      setPendingSourceVersionId(version.id);
      setProcessingWorkId(artifact.work_id);
      await refreshProjectWorks(queryClient, projectId);

      // Durability is the boundary for leaving the blocking import state. Open
      // the Work before starting enrichment so workflow-start failure cannot
      // make a successfully saved recording disappear.
      setActiveWorkId(artifact.work_id);
      setStage("processing");
      setProgress(0);
      setMessage("Understanding audio…");

      try {
        const { job } = await startUnderstandWorkflow(version.id, projectId, transcriptionProfile);
        setActiveJobId(job.id);
        setPendingSourceVersionId(null);
        await loadWork(artifact.work_id);
      } catch (cause) {
        setActiveJobId(null);
        setPendingSourceVersionId(version.id);
        setError(cause instanceof Error ? cause.message : "Could not start processing");
        setStage("error");
      }
    } catch (cause) {
      setProcessingWorkId(null);
      setPendingSourceVersionId(null);
      setError(cause instanceof Error ? cause.message : "Import failed");
      setStage("error");
    }
  }, [loadWork, projectId, queryClient, serviceStatus, setActiveWorkId, transcriptionProfile]);

  const cancelActiveJob = useCallback(async () => {
    if (!activeJobId) return;
    setMessage("Cancelling after the current processing step");
    try {
      await cancelJob(activeJobId);
      const workId = processingWorkId ?? workspace.activeWorkId;
      if (workId) await loadWork(workId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not cancel the job");
      setStage("error");
    }
  }, [activeJobId, loadWork, processingWorkId, workspace.activeWorkId]);

  const retryActiveJob = useCallback(async () => {
    const workId = processingWorkId ?? workspace.activeWorkId;
    if (!activeJobId || !workId) return;
    setStage("processing");
    setError(null);
    setProgress(0);
    try {
      const retried = await retryJob(activeJobId);
      setActiveJobId(retried.id);
      await loadWork(workId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Retry failed");
      setStage("error");
    }
  }, [activeJobId, loadWork, processingWorkId, workspace.activeWorkId]);

  const resumeActiveJob = useCallback(async () => {
    const workId = processingWorkId ?? workspace.activeWorkId;
    if (!workId) return;
    setStage("processing");
    setError(null);
    try {
      await loadWork(workId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not reconnect to this job");
      setStage("disconnected");
    }
  }, [loadWork, processingWorkId, workspace.activeWorkId]);

  const startPendingProcessing = useCallback(async () => {
    const workId = processingWorkId ?? workspace.activeWorkId;
    if (!pendingSourceVersionId || !projectId || !workId) return;
    setStage("processing");
    setError(null);
    setProgress(0);
    try {
      const { job } = await startUnderstandWorkflow(pendingSourceVersionId, projectId, transcriptionProfile);
      setActiveJobId(job.id);
      setPendingSourceVersionId(null);
      await loadWork(workId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start processing");
      setStage("error");
    }
  }, [loadWork, pendingSourceVersionId, processingWorkId, projectId, transcriptionProfile, workspace.activeWorkId]);

  const durableWorkVisible = Boolean(
    processingWorkId && workspace.activeWorkId === processingWorkId && workspace.representations.length > 0,
  );
  const showBlockingOverlay = stage === "uploading" || ((stage === "disconnected" || stage === "error") && !durableWorkVisible);
  const showProcessingNotice = durableWorkVisible && ["processing", "disconnected", "error"].includes(stage);

  return (
    <>
      <input
        id="audio-import-input"
        ref={fileInputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void handleFile(file);
        }}
      />
      {showBlockingOverlay && (
        <div className="operation-layer">
          <div className="operation-layer-inner">
            {stage === "uploading" && (
              <div className="piece-processing-card" role="status">
                <span className="piece-processing-filename">{presentableTitle(filename)}</span>
                <progress value={progress} max={100} />
                <span className="piece-processing-stage">Uploading…</span>
              </div>
            )}
            {stage === "disconnected" && (
              <div className="operation-card operation-card-warning" role="alert">
                <strong>Connection interrupted</strong><span>{error}</span>
                <button className="btn btn-primary" onClick={() => void resumeActiveJob()}>Reconnect</button>
              </div>
            )}
            {stage === "error" && (
              <div className="operation-card operation-card-error" role="alert">
                <strong>Couldn’t complete that</strong><span>{error}</span>
                <div className="operation-card-actions">
                  {activeJobId && <button className="btn btn-primary" onClick={() => void retryActiveJob()}>Retry</button>}
                  {!activeJobId && pendingSourceVersionId && <button className="btn btn-primary" onClick={() => void startPendingProcessing()}>Process saved audio</button>}
                  <button className="btn" onClick={() => { setStage("idle"); setError(null); setProgress(0); }}>Dismiss</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {showProcessingNotice && (
        <div className="workspace-notice workspace-processing-notice" role={stage === "processing" ? "status" : "alert"}>
          <span>
            {stage === "processing" && <><strong>Recording saved.</strong> {message || "Understanding audio…"}{progress > 0 ? ` · ${Math.round(progress)}%` : ""}</>}
            {stage === "disconnected" && <><strong>Processing status interrupted.</strong> Your recording is saved. Available views still work.</>}
            {stage === "error" && <><strong>Couldn’t finish understanding this recording.</strong> Your recording is saved. Available views still work.</>}
          </span>
          <div className="operation-card-actions">
            {stage === "processing" && activeJobId && <button className="btn" onClick={() => void cancelActiveJob()}>Cancel</button>}
            {stage === "disconnected" && <button className="btn btn-primary" onClick={() => void resumeActiveJob()}>Reconnect</button>}
            {stage === "error" && activeJobId && <button className="btn btn-primary" onClick={() => void retryActiveJob()}>Retry</button>}
            {stage === "error" && !activeJobId && pendingSourceVersionId && <button className="btn btn-primary" onClick={() => void startPendingProcessing()}>Process saved audio</button>}
            {(stage === "disconnected" || stage === "error") && <button className="btn" onClick={() => { setStage("idle"); setError(null); }}>Dismiss</button>}
          </div>
        </div>
      )}
      {loadWarnings.length > 0 && stage === "success" && (
        <div className="workspace-notice" role="status">
          <span>{loadWarnings.join(" ")}</span>
          <button type="button" className="icon-btn" aria-label="Dismiss notice" onClick={() => setLoadWarnings([])}>×</button>
        </div>
      )}
    </>
  );
}
