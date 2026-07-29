"use client";

import { useState, useCallback } from "react";
import type { Job, JobStage } from "@/lib/domain.types";

type ProcessingBannerProps = {
  jobs: Job[];
  onCancel: (jobId: string) => void;
  onRetry: (jobId: string) => void;
};

export default function ProcessingBanner({ jobs, onCancel, onRetry }: ProcessingBannerProps) {
  if (jobs.length === 0) return null;

  const active = jobs.find((j) => j.lifecycle.current === "running" || j.lifecycle.current === "claimed");
  const queued = jobs.filter((j) => j.lifecycle.current === "queued");
  const failed = jobs.filter((j) => j.lifecycle.current === "failed");
  const cancelled = jobs.filter((j) => j.lifecycle.current === "cancelled");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--s-1)",
        padding: "var(--s-2) var(--s-4)",
        background: "var(--panel-2)",
        borderTop: "1px solid var(--border)",
        fontSize: "var(--fs-xs)",
      }}
    >
      {active && (
        <ActiveJob
          job={active}
          onCancel={() => onCancel(active.id)}
        />
      )}

      {queued.length > 0 && (
        <QueuedJobs
          count={queued.length}
          jobs={queued}
        />
      )}

      {failed.map((job) => (
        <FailedJob
          key={job.id}
          job={job}
          onRetry={() => onRetry(job.id)}
          onDismiss={() => onCancel(job.id)}
        />
      ))}

      {cancelled.length > 0 && (
        <div style={{ color: "var(--muted)", paddingTop: "var(--s-1)" }}>
          {cancelled.length} cancelled
        </div>
      )}
    </div>
  );
}

function ActiveJob({ job, onCancel }: { job: Job; onCancel: () => void }) {
  const pct = Math.round(job.lifecycle.progress);
  const isRunning = job.lifecycle.current === "running";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--s-3)" }}>
      <span style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)", whiteSpace: "nowrap" }}>
        {job.capability.name}
      </span>

      <div
        style={{
          flex: 1,
          height: 4,
          background: "var(--panel-3)",
          borderRadius: "var(--r-full)",
          overflow: "hidden",
        }}
      >
        <div
          className={isRunning ? "pulse" : ""}
          style={{
            height: "100%",
            width: `${pct}%`,
            background: isRunning ? "var(--grad-accent-2)" : "var(--muted)",
            borderRadius: "var(--r-full)",
            transition: "width 0.3s var(--ease)",
          }}
        />
      </div>

      <span style={{ color: "var(--muted)", fontFamily: "var(--font-mono)", fontSize: "var(--fs-xs)", minWidth: 32, textAlign: "right" }}>
        {pct}%
      </span>

      <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>
        {job.lifecycle.message}
      </span>

      <button
        className="icon-btn ghost danger"
        onClick={onCancel}
        style={{ fontSize: "var(--fs-xs)", padding: "2px 8px" }}
      >
        Cancel
      </button>
    </div>
  );
}

function QueuedJobs({ count, jobs }: { count: number; jobs: Job[] }) {
  const names = jobs.map((j) => j.capability.name).slice(0, 3).join(", ");
  const more = count > 3 ? ` +${count - 3}` : "";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", color: "var(--muted)" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <span
          style={{
            display: "inline-block",
            width: 6,
            height: 6,
            borderRadius: "var(--r-full)",
            background: "var(--accent-2)",
          }}
        />
        Queued
      </span>
      <span style={{ color: "var(--text)", opacity: 0.5 }}>
        {names}{more}
      </span>
      <span style={{ color: "var(--muted)", marginLeft: "auto" }}>
        {count} pending
      </span>
    </div>
  );
}

function FailedJob({ job, onRetry, onDismiss }: { job: Job; onRetry: () => void; onDismiss: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--s-3)", color: "var(--danger)" }}>
      <span style={{ fontWeight: "var(--fw-medium)" }}>Failed</span>
      <span style={{ fontSize: "var(--fs-xs)" }}>{job.capability.name}</span>
      <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {job.error || "Unknown error"}
      </span>
      <button className="icon-btn ghost" onClick={onRetry} style={{ fontSize: "var(--fs-xs)", padding: "2px 8px" }}>
        Retry
      </button>
      <button className="icon-btn ghost" onClick={onDismiss} style={{ fontSize: "var(--fs-xs)", padding: "2px 8px" }}>
        Dismiss
      </button>
    </div>
  );
}
