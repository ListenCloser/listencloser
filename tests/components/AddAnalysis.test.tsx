import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AddAnalysis from "@/components/workspace/AddAnalysis";

describe("AddAnalysis", () => {
  it("keeps capability maturity separate from execution action", () => {
    const onAction = vi.fn();
    const onOpenChange = vi.fn();

    render(
      <AddAnalysis
        open
        onOpenChange={onOpenChange}
        options={[{
          id: "structure-map",
          title: "Structure Map",
          description: "Find rough candidate spans.",
          maturity: "Experimental",
          actionLabel: "Check status",
          onAction,
        }]}
        notice="The job is still saved, but this browser lost contact."
        noticeRole="status"
      />,
    );

    expect(screen.getByText("Structure Map")).toBeInTheDocument();
    expect(screen.getByText("Experimental")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("job is still saved");
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("supports materially different capability actions in one chooser", () => {
    const addStructure = vi.fn();
    const openChanges = vi.fn();

    render(
      <AddAnalysis
        open
        onOpenChange={() => undefined}
        options={[
          {
            id: "structure-map",
            title: "Structure Map",
            description: "Find rough candidate spans.",
            maturity: "Experimental",
            actionLabel: "Add",
            onAction: addStructure,
          },
          {
            id: "measured-changes",
            title: "Changes",
            description: "Open measured change moments in Breakdown.",
            maturity: "Experimental",
            actionLabel: "Open",
            onAction: openChanges,
          },
        ]}
      />,
    );

    expect(screen.getByText("Structure Map")).toBeInTheDocument();
    expect(screen.getByText("Changes")).toBeInTheDocument();
    expect(screen.getAllByText("Experimental")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(addStructure).toHaveBeenCalledOnce();
    expect(openChanges).toHaveBeenCalledOnce();
  });

  it("does not expose a close action while an analysis action is busy", () => {
    render(
      <AddAnalysis
        open
        onOpenChange={() => undefined}
        options={[{
          id: "structure-map",
          title: "Structure Map",
          description: "Find rough candidate spans.",
          maturity: "Experimental",
          actionLabel: "Finding shape…",
          onAction: () => undefined,
          busy: true,
        }]}
      />,
    );

    expect(screen.queryByRole("button", { name: "Close analysis chooser" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finding shape…" })).toBeDisabled();
  });
});
