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
          onAction={() => undefined},
          busy: true,
        }]}
      />,
    );

    expect(screen.queryByRole("button", { name: "Close analysis chooser" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finding shape…" })).toBeDisabled();
  });
});
