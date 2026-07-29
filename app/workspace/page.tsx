"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { TransportProvider, useTransport } from "@/lib/stores/transport";
import { SelectionProvider } from "@/lib/stores/selection";
import { TimelineProvider, useTimeline } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";
import { createProject, createWork, uploadArtifact, startUnderstandWorkflow, getJob, getEntities, startCorrectWorkflow, startCompareWorkflow, getInsights } from "@/lib/api-client";
import { getPublicUrl } from "@/lib/storage";
import TransportBar from "@/components/workspace/TransportBar";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import InspectorPanel from "@/components/workspace/InspectorPanel";
import ComparePanel from "@/components/workspace/ComparePanel";
import Link from "next/link";
import type { Entity, Insight } from "@/lib/domain.types";

type UploadStage = "idle" | "uploading" | "processing" | "success" | "error";

type DiffNote = {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
  status: "unchanged" | "added" | "removed" | "modified";
  counterpart?: { pitch: number; start: number; end: number; velocity: number };
};

function WorkspaceApp() {
  const { addRepresentation } = useWorkspace();
  const { setActiveSource } = useTransport();
  const { setBpm, setTimeSignature } = useTimeline();

  const [stage, setStage] = useState<UploadStage>("idle");
  const [uploadFilename, setUploadFilename] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStage, setJobStage] = useState("");
  const [jobProgress, setJobProgress] = useState(0);
  const [jobMessage, setJobMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [outputVersionIds, setOutputVersionIds] = useState<string[]>([]);

  const [workspaceMode, setWorkspaceMode] = useState<"explore" | "correct" | "compare">("explore");
  const [editingVersionId, setEditingVersionId] = useState<string | null>(null);
  const [correctedNotes, setCorrectedNotes] = useState<Array<{pitch: number; start: number; end: number; velocity: number}> | null>(null);
  const [originalNotes, setOriginalNotes] = useState<Array<{pitch: number; start: number; end: number; velocity: number}> | null>(null);
  const [correctionJobId, setCorrectionJobId] = useState<string | null>(null);
  const [correctionStage, setCorrectionStage] = useState<"idle" | "processing" | "success" | "error">("idle");
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  const [compareVersionA, setCompareVersionA] = useState<string | null>(null);
  const [compareVersionB, setCompareVersionB] = useState<string | null>(null);
  const [compareEntitiesA, setCompareEntitiesA] = useState<Entity[] | null>(null);
  const [compareEntitiesB, setCompareEntitiesB] = useState<Entity[] | null>(null);
  const [compareJobId, setCompareJobId] = useState<string | null>(null);
  const [compareInsight, setCompareInsight] = useState<Insight | null>(null);
  const [compareStage, setCompareStage] = useState<"idle" | "loading" | "processing" | "success" | "error">("idle");
  const [compareError, setCompareError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const comparePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const diffNotesFromInsight = useMemo((): DiffNote[] | null => {
    if (!compareInsight) return null;
    const evidence = compareInsight.evidence;
    const diffArr = evidence.diff;
    if (Array.isArray(diffArr) && diffArr.length > 0) {
      const sample = diffArr[0];
      if (sample && typeof sample === "object" && "pitch" in sample && "status" in sample) {
        return diffArr as DiffNote[];
      }
    }
    return null;
  }, [compareInsight]);

  const handleFile = useCallback(
    async (file: File) => {
      setStage("uploading");
      setUploadFilename(file.name);
      setError(null);

      try {
        const name = file.name.replace(/\.[^.]+$/, "");

        const project = await createProject(name);
        setProjectId(project.id);

        const work = await createWork(project.id, name);

        const { version } = await uploadArtifact(project.id, file, work.id);
        const url = getPublicUrl(version.storage_bucket, version.storage_key);
        setAudioUrl(url);

        const { job } = await startUnderstandWorkflow(version.id, project.id);
        setJobId(job.id);
        setJobStage(job.lifecycle.current);
        setJobProgress(job.lifecycle.progress);
        setJobMessage(job.lifecycle.message);
        setStage("processing");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong");
        setStage("error");
      }
    },
    [],
  );

  useEffect(() => {
    document.title = "hello-ai — Workspace";
  }, []);

  useEffect(() => {
    if (!jobId) return;
    if (jobStage === "succeeded" || jobStage === "failed" || jobStage === "cancelled") return;

    const interval = setInterval(async () => {
      try {
        const job = await getJob(jobId);
        setJobStage(job.lifecycle.current);
        setJobProgress(job.lifecycle.progress);
        setJobMessage(job.lifecycle.message);

        if (job.lifecycle.current === "succeeded") {
          clearInterval(interval);
          setOutputVersionIds(job.output_version_ids);

          if (job.lifecycle.completed_at) {
            const meta = (job as { provenance?: { metadata?: Record<string, unknown> } }).provenance?.metadata;
            if (meta) {
              if (typeof meta.bpm === "number") setBpm(meta.bpm);
              if (typeof meta.time_signature_numerator === "number" && typeof meta.time_signature_denominator === "number") {
                setTimeSignature(meta.time_signature_numerator as number, meta.time_signature_denominator as number);
              }
            }
          }

          if (audioUrl) {
            addRepresentation({
              kind: "waveform",
              label: "Waveform",
              sourceUrl: audioUrl,
              sourceLabel: uploadFilename || "Original",
              confidence: null,
              provenance: "upload",
            });

            setActiveSource({
              id: "enhanced-audio",
              label: uploadFilename || "Audio",
              url: audioUrl,
              kind: "audio",
            });
          }

          if (job.output_version_ids.length > 0) {
            try {
              const entities = await getEntities(job.output_version_ids[0]);
              const noteCount = entities.filter((e: Entity) => e.kind === "note").length;
              addRepresentation({
                kind: "piano_roll",
                label: "Piano Roll",
                sourceUrl: `/api/v1/versions/${job.output_version_ids[0]}/entities`,
                sourceLabel: `${noteCount} notes`,
                confidence: null,
                provenance: "transcription",
              });
            } catch {
              addRepresentation({
                kind: "piano_roll",
                label: "Piano Roll",
                sourceUrl: `/api/v1/versions/${job.output_version_ids[0]}/entities`,
                sourceLabel: "Transcribed",
                confidence: null,
                provenance: "transcription",
              });
            }
          }

          setStage("success");
        } else if (job.lifecycle.current === "failed") {
          clearInterval(interval);
          setError(job.error || "Job failed");
          setStage("error");
        } else if (job.lifecycle.current === "cancelled") {
          clearInterval(interval);
          setError("Job was cancelled");
          setStage("error");
        }
      } catch (err) {
        clearInterval(interval);
        setError(err instanceof Error ? err.message : "Polling failed");
        setStage("error");
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, jobStage, audioUrl, uploadFilename, addRepresentation, setActiveSource, setBpm, setTimeSignature]);

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }

  function enterCorrectMode() {
    if (outputVersionIds.length === 0) return;
    setEditingVersionId(outputVersionIds[0]);
    setWorkspaceMode("correct");
    setCorrectionStage("idle");
    setCorrectionError(null);

    clearCompareState();

    getEntities(outputVersionIds[0])
      .then((entities) => {
        const notes = entities
          .filter((e: Entity) => e.kind === "note")
          .map((e) => ({
            pitch: e.note?.pitch ?? 60,
            start: e.note?.start_seconds ?? 0,
            end: e.note?.end_seconds ?? 0.5,
            velocity: e.note?.velocity ?? 64,
          }));
        setOriginalNotes(notes);
        setCorrectedNotes(notes);
      })
      .catch(() => {});
  }

  function exitCorrectMode() {
    setWorkspaceMode("explore");
    setEditingVersionId(null);
    setCorrectedNotes(null);
    setOriginalNotes(null);
    setCorrectionStage("idle");
    setCorrectionError(null);
    clearCompareState();
  }

  async function acceptCorrection() {
    if (!correctedNotes || !editingVersionId || !projectId) return;
    setCorrectionStage("processing");
    setCorrectionError(null);

    try {
      const { job } = await startCorrectWorkflow(editingVersionId, projectId, correctedNotes);
      setCorrectionJobId(job.id);

      const interval = setInterval(async () => {
        try {
          const j = await getJob(job.id);
          if (j.lifecycle.current === "succeeded") {
            clearInterval(interval);
            setCorrectionStage("success");
            const newVersionId = j.output_version_ids[0];
            if (newVersionId) {
              const entities = await getEntities(newVersionId);
              const noteCount = entities.filter((e: Entity) => e.kind === "note").length;
              addRepresentation({
                kind: "piano_roll",
                label: "Piano Roll (Corrected)",
                sourceUrl: `/api/v1/versions/${newVersionId}/entities`,
                sourceLabel: `${noteCount} notes`,
                confidence: null,
                provenance: "correction",
              });
              setOutputVersionIds([newVersionId, ...outputVersionIds]);
            }
          } else if (j.lifecycle.current === "failed") {
            clearInterval(interval);
            setCorrectionStage("error");
            setCorrectionError(j.error || "Correction job failed");
          } else if (j.lifecycle.current === "cancelled") {
            clearInterval(interval);
            setCorrectionStage("error");
            setCorrectionError("Correction was cancelled");
          }
        } catch {
          clearInterval(interval);
          setCorrectionStage("error");
          setCorrectionError("Failed to poll correction status");
        }
      }, 2000);
    } catch (err) {
      setCorrectionStage("error");
      setCorrectionError(err instanceof Error ? err.message : "Correction failed");
    }
  }

  function clearCompareState() {
    if (comparePollRef.current) {
      clearInterval(comparePollRef.current);
      comparePollRef.current = null;
    }
    setCompareVersionA(null);
    setCompareVersionB(null);
    setCompareEntitiesA(null);
    setCompareEntitiesB(null);
    setCompareJobId(null);
    setCompareInsight(null);
    setCompareStage("idle");
    setCompareError(null);
  }

  async function enterCompareMode() {
    if (outputVersionIds.length < 2) return;

    setEditingVersionId(null);
    setCorrectedNotes(null);
    setOriginalNotes(null);
    setCorrectionStage("idle");
    setCorrectionError(null);

    const vA = outputVersionIds[0];
    const vB = outputVersionIds[1];

    setCompareVersionA(vA);
    setCompareVersionB(vB);
    setCompareJobId(null);
    setCompareInsight(null);
    setCompareStage("loading");
    setCompareError(null);
    setWorkspaceMode("compare");

    try {
      const [entitiesA, entitiesB] = await Promise.all([
        getEntities(vA),
        getEntities(vB),
      ]);
      setCompareEntitiesA(entitiesA);
      setCompareEntitiesB(entitiesB);

      if (!projectId) return;

      setCompareStage("processing");
      const { job } = await startCompareWorkflow(vA, vB, projectId);
      setCompareJobId(job.id);

      if (comparePollRef.current) clearInterval(comparePollRef.current);

      const interval = setInterval(async () => {
        try {
          const j = await getJob(job.id);
          if (j.lifecycle.current === "succeeded") {
            clearInterval(interval);
            comparePollRef.current = null;

            try {
              const insights = await getInsights(vA);
              const found = insights.find(
                (i: Insight) => i.kind === "comparison" || i.kind === "diff",
              );
              if (found) setCompareInsight(found);
            } catch {}

            setCompareStage("success");
          } else if (j.lifecycle.current === "failed") {
            clearInterval(interval);
            comparePollRef.current = null;
            setCompareStage("success");
            setCompareError(j.error || "Comparison job failed");
          } else if (j.lifecycle.current === "cancelled") {
            clearInterval(interval);
            comparePollRef.current = null;
            setCompareStage("success");
            setCompareError("Comparison was cancelled");
          }
        } catch {
          clearInterval(interval);
          comparePollRef.current = null;
          setCompareStage("success");
          setCompareError("Failed to poll comparison status");
        }
      }, 2000);

      comparePollRef.current = interval;
    } catch (err) {
      setCompareStage("error");
      setCompareError(err instanceof Error ? err.message : "Failed to load entities");
    }
  }

  function selectVersionA() {
    if (outputVersionIds.length <= 1) return;
    const next = outputVersionIds.find((id) => id !== compareVersionA && id !== compareVersionB)
      ?? outputVersionIds.find((id) => id !== compareVersionA);
    if (!next || next === compareVersionA) return;
    setCompareVersionA(next);
    getEntities(next).then(setCompareEntitiesA).catch(() => {});
    setCompareJobId(null);
    setCompareInsight(null);
    setCompareStage("idle");
  }

  function selectVersionB() {
    if (outputVersionIds.length <= 1) return;
    const next = outputVersionIds.find((id) => id !== compareVersionB && id !== compareVersionA)
      ?? outputVersionIds.find((id) => id !== compareVersionB);
    if (!next || next === compareVersionB) return;
    setCompareVersionB(next);
    getEntities(next).then(setCompareEntitiesB).catch(() => {});
    setCompareJobId(null);
    setCompareInsight(null);
    setCompareStage("idle");
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault();
    dropRef.current?.classList.add("drag-over");
  }

  function onDragLeave() {
    dropRef.current?.classList.remove("drag-over");
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    dropRef.current?.classList.remove("drag-over");
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg)",
        color: "var(--text)",
        fontFamily: "var(--font-sans)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-4)",
          padding: "var(--s-2) var(--s-4)",
          background: "var(--panel)",
          borderBottom: "1px solid var(--border)",
          minHeight: 44,
        }}
      >
        <div className="brand" style={{ fontSize: "var(--fs-sm)", flexShrink: 0 }}>
          <span className="brand-dot" />
          hello-ai
        </div>

        {stage !== "idle" && (
          <span style={{ fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
            {uploadFilename}
          </span>
        )}

        <Link
          href="/"
          className="btn btn-ghost"
          style={{ marginLeft: "auto", fontSize: "var(--fs-xs)" }}
        >
          Back
        </Link>
      </div>

      {stage === "idle" && (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "var(--s-5)",
          }}
        >
          <div
            ref={dropRef}
            className="drop-zone"
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{ maxWidth: 420, width: "100%" }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.musicxml,.mid,.midi"
              onChange={onFileChange}
              style={{ display: "none" }}
            />
            <span className="drop-icon">+</span>
            <span className="muted">Drop an audio file to start</span>
            <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
              WAV · MP3 · M4A · FLAC · MusicXML · MIDI
            </span>
          </div>
        </div>
      )}

      {(stage === "uploading" || stage === "processing" || stage === "error") && (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "var(--s-4)",
            padding: "var(--s-5)",
          }}
        >
          {stage === "uploading" && (
            <>
              <div className="spinner" />
              <div style={{ textAlign: "center" }}>
                <div style={{ fontWeight: "var(--fw-medium)", fontSize: "var(--fs-md)" }}>
                  Uploading {uploadFilename}
                </div>
                <div className="muted">Creating project and uploading artifact…</div>
              </div>
            </>
          )}

          {stage === "processing" && (
            <>
              <div className="spinner" />
              <div style={{ textAlign: "center", maxWidth: 360 }}>
                <div style={{ fontWeight: "var(--fw-medium)", fontSize: "var(--fs-md)", marginBottom: "var(--s-3)" }}>
                  Processing {uploadFilename}
                </div>

                <div
                  style={{
                    width: "100%",
                    height: 6,
                    background: "var(--panel-3)",
                    borderRadius: "var(--r-full)",
                    overflow: "hidden",
                    marginBottom: "var(--s-2)",
                  }}
                >
                  <div
                    className="pulse"
                    style={{
                      height: "100%",
                      width: `${jobProgress}%`,
                      background: "var(--grad-accent-2)",
                      borderRadius: "var(--r-full)",
                      transition: "width 0.3s var(--ease)",
                    }}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--fs-xs)", marginBottom: "var(--s-1)" }}>
                  <span style={{ color: "var(--muted)" }}>{jobStage}</span>
                  <span style={{ color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
                    {jobProgress}%
                  </span>
                </div>

                <div className="muted">{jobMessage}</div>
              </div>
            </>
          )}

          {stage === "error" && (
            <>
              <div style={{ color: "var(--danger)", fontSize: 28, lineHeight: 1 }}>!</div>
              <div style={{ textAlign: "center", maxWidth: 360 }}>
                <div style={{ fontWeight: "var(--fw-medium)", fontSize: "var(--fs-md)", color: "var(--danger)", marginBottom: "var(--s-2)" }}>
                  Processing Failed
                </div>
                <div className="muted" style={{ marginBottom: "var(--s-4)" }}>{error}</div>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setStage("idle");
                    setJobId(null);
                    setError(null);
                    setUploadFilename("");
                  }}
                >
                  Try Again
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {stage === "success" && (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--s-2)",
              padding: "var(--s-1) var(--s-4)",
              background: "var(--panel-2)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <button
              className={`btn ${workspaceMode === "explore" ? "btn-primary" : "btn-ghost"}`}
              onClick={exitCorrectMode}
              style={{ fontSize: "var(--fs-xs)" }}
            >
              Explore
            </button>
            <button
              className={`btn ${workspaceMode === "correct" ? "btn-primary" : "btn-ghost"}`}
              onClick={enterCorrectMode}
              disabled={outputVersionIds.length === 0}
              style={{ fontSize: "var(--fs-xs)" }}
            >
              Correct
            </button>
            <button
              className={`btn ${workspaceMode === "compare" ? "btn-primary" : "btn-ghost"}`}
              onClick={enterCompareMode}
              disabled={outputVersionIds.length < 2}
              style={{ fontSize: "var(--fs-xs)" }}
            >
              Compare
            </button>

            {workspaceMode === "correct" && correctedNotes && originalNotes && (
              <>
                <div style={{ flex: 1 }} />
                <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                  {correctedNotes.length} notes
                </span>
                {JSON.stringify(correctedNotes) !== JSON.stringify(originalNotes) && (
                  <>
                    <button
                      className="btn btn-ghost"
                      onClick={() => setCorrectedNotes([...originalNotes])}
                      style={{ fontSize: "var(--fs-xs)" }}
                    >
                      Reset
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={acceptCorrection}
                      disabled={correctionStage === "processing"}
                      style={{ fontSize: "var(--fs-xs)" }}
                    >
                      {correctionStage === "processing" ? "Saving…" : "Accept Changes"}
                    </button>
                  </>
                )}
              </>
            )}

            {workspaceMode === "compare" && (
              <span className="muted" style={{ fontSize: "var(--fs-xs)", marginLeft: "auto" }}>
                {compareEntitiesA && compareEntitiesB
                  ? `${compareEntitiesA.filter((e) => e.kind === "note").length} vs ${compareEntitiesB.filter((e) => e.kind === "note").length} notes`
                  : ""}
              </span>
            )}
          </div>

          {workspaceMode === "correct" && correctionStage === "processing" && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--panel)",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                fontSize: "var(--fs-xs)",
              }}
            >
              <div className="spinner" />
              <span>Saving corrections…</span>
            </div>
          )}

          {workspaceMode === "correct" && correctionStage === "error" && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--danger-bg)",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                fontSize: "var(--fs-xs)",
                color: "var(--danger)",
              }}
            >
              <span>{correctionError}</span>
              <button className="btn btn-ghost" onClick={exitCorrectMode} style={{ fontSize: "var(--fs-xs)" }}>
                Dismiss
              </button>
            </div>
          )}

          {workspaceMode === "correct" && correctionStage === "success" && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--success-bg)",
                borderBottom: "1px solid var(--border)",
                fontSize: "var(--fs-xs)",
                color: "var(--success)",
              }}
            >
              Correction saved as a new version.
            </div>
          )}

          {workspaceMode === "compare" && compareStage === "loading" && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--panel)",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                fontSize: "var(--fs-xs)",
              }}
            >
              <div className="spinner" />
              <span>Loading entities for comparison…</span>
            </div>
          )}

          {workspaceMode === "compare" && compareStage === "processing" && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--panel)",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                fontSize: "var(--fs-xs)",
              }}
            >
              <div className="spinner" />
              <span>Running comparison…</span>
            </div>
          )}

          {workspaceMode === "compare" && compareError && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--danger-bg)",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                fontSize: "var(--fs-xs)",
                color: "var(--danger)",
              }}
            >
              <span>{compareError}</span>
              <button className="btn btn-ghost" onClick={exitCorrectMode} style={{ fontSize: "var(--fs-xs)" }}>
                Dismiss
              </button>
            </div>
          )}

          {workspaceMode === "compare" && compareStage === "error" && (
            <div
              style={{
                padding: "var(--s-2) var(--s-4)",
                background: "var(--danger-bg)",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                fontSize: "var(--fs-xs)",
                color: "var(--danger)",
              }}
            >
              <span>{compareError ?? "Failed to load comparison data"}</span>
              <button className="btn btn-ghost" onClick={exitCorrectMode} style={{ fontSize: "var(--fs-xs)" }}>
                Dismiss
              </button>
            </div>
          )}

          <TransportBar />
          <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
            {workspaceMode === "compare" ? (
              <ComparePanel
                versionA={compareVersionA && compareEntitiesA ? { id: compareVersionA, label: "Original", entities: compareEntitiesA } : null}
                versionB={compareVersionB && compareEntitiesB ? { id: compareVersionB, label: "Corrected", entities: compareEntitiesB } : null}
                onSelectVersionA={selectVersionA}
                onSelectVersionB={selectVersionB}
                diffNotes={diffNotesFromInsight}
              />
            ) : (
              <RepresentationStack
                mode={workspaceMode}
                correctedNotes={correctedNotes}
                onCorrectedNotesChange={workspaceMode === "correct" ? setCorrectedNotes : undefined}
              />
            )}
            <InspectorPanel />
          </div>
        </>
      )}
    </div>
  );
}

export default function WorkspacePage() {
  return (
    <TransportProvider>
      <SelectionProvider>
        <TimelineProvider>
          <WorkspaceProvider>
            <WorkspaceApp />
          </WorkspaceProvider>
        </TimelineProvider>
      </SelectionProvider>
    </TransportProvider>
  );
}
