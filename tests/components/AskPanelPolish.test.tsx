import { fireEvent, render, screen } from "@testing-library/react";
import { useEffect, type ReactNode } from "react";
import { describe, expect, it } from "vitest";
import AskPanel, { askErrorMessage } from "@/components/workspace/inspector/AskPanel";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider } from "@/lib/stores/transport";
import { useWorkspace, WorkspaceProvider } from "@/lib/stores/workspace";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <TimelineProvider>
      <TransportProvider>
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}

function AskPanelWithSelection() {
  const { setSelection } = useWorkspace();
  useEffect(() => {
    setSelection({
      timeRange: { start: 6, end: 12, domain: "performance" },
      provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
    });
  }, [setSelection]);
  return <AskPanel />;
}

describe("AskPanel polish", () => {
  it("explains useful question scope and keeps the send affordance compact", () => {
    render(<AskPanel />, { wrapper });

    expect(screen.getByText(/Ask about harmony, rhythm, structure, or a selected passage/)).toBeVisible();
    expect(screen.getByText(/Answers use the evidence currently available for this recording/)).toBeVisible();

    const send = screen.getByRole("button", { name: "Send question" });
    expect(send).toBeDisabled();
    expect(send.querySelector("svg")).toHaveAttribute("width", "14");
    expect(send.querySelector("svg")).toHaveAttribute("height", "14");
  });

  it("lets a selected Ask scope be dismissed directly", async () => {
    render(<AskPanelWithSelection />, { wrapper });

    const clear = await screen.findByRole("button", { name: "Clear question context" });
    fireEvent.click(clear);

    expect(screen.queryByRole("button", { name: "Clear question context" })).not.toBeInTheDocument();
  });

  it("keeps known Ask failures concise and specific", () => {
    expect(askErrorMessage(new Error("Ask timed out."))).toBe("Ask took too long.");
    expect(askErrorMessage(new Error("Ask provider unavailable."))).toBe("Ask is temporarily unavailable.");
    expect(askErrorMessage(new Error("Ask is not configured."))).toBe("Ask is not configured for this workspace.");
    expect(askErrorMessage(new Error("unexpected"))).toBe("Ask is unavailable right now.");
  });
});
