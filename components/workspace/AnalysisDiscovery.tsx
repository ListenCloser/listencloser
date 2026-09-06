"use client";

import { useCallback } from "react";

import AddAnalysis, { type AddAnalysisOption } from "@/components/workspace/AddAnalysis";
import {
  ANALYSIS_DISCOVERY_DEFINITIONS,
  type AnalysisDiscoveryId,
} from "@/components/workspace/analysis-product-contract";
import { useWorkspace } from "@/lib/stores/workspace";

export type AnalysisDiscoveryAction = {
  actionLabel: string;
  onAction: () => void;
  busy?: boolean;
  disabled?: boolean;
  ready?: boolean;
};

function optionFor(
  id: AnalysisDiscoveryId,
  action: AnalysisDiscoveryAction,
): AddAnalysisOption {
  const definition = ANALYSIS_DISCOVERY_DEFINITIONS[id];
  return {
    id: definition.id,
    title: definition.title,
    description: action.ready && definition.readyDescription
      ? definition.readyDescription
      : definition.description,
    maturity: "Experimental",
    actionLabel: action.actionLabel,
    onAction: action.onAction,
    busy: action.busy,
    disabled: action.disabled,
  };
}

function hasExactPerformanceSelection(workspace: ReturnType<typeof useWorkspace>["workspace"]): boolean {
  const selectedPassage = workspace.selection?.timeRange;
  return Boolean(
    selectedPassage
    && selectedPassage.domain === "performance"
    && workspace.selection?.provenance.timeExact === true
    && Number.isFinite(selectedPassage.start)
    && Number.isFinite(selectedPassage.end)
    && selectedPassage.start >= 0
    && selectedPassage.end > selectedPassage.start,
  );
}

export default function AnalysisDiscovery({
  open,
  onOpenChange,
  structure,
  pitch,
  layers,
  notice,
  noticeRole = "status",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  structure: AnalysisDiscoveryAction;
  pitch: AnalysisDiscoveryAction;
  layers?: AnalysisDiscoveryAction | null;
  notice?: string | null;
  noticeRole?: "alert" | "status";
}) {
  const { workspace, setInspectorMode, toggleInspector } = useWorkspace();

  const openAnalysisInspector = useCallback(() => {
    setInspectorMode("analysis");
    if (workspace.inspectorCollapsed) toggleInspector();
    onOpenChange(false);
  }, [onOpenChange, setInspectorMode, toggleInspector, workspace.inspectorCollapsed]);

  const options: AddAnalysisOption[] = [
    optionFor("structure-map", structure),
    optionFor("pitch-contour", pitch),
  ];

  if (layers) options.push(optionFor("layers", layers));
  if (hasExactPerformanceSelection(workspace)) {
    options.push(optionFor("similar-moments", {
      actionLabel: "Open",
      onAction: openAnalysisInspector,
    }));
  }
  if (workspace.analysisState !== "idle") {
    options.push(optionFor("measured-changes", {
      actionLabel: "Open",
      onAction: openAnalysisInspector,
    }));
  }

  return (
    <AddAnalysis
      open={open}
      onOpenChange={onOpenChange}
      options={options}
      notice={notice}
      noticeRole={noticeRole}
    />
  );
}
