import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import AskPanel from "@/components/workspace/AskPanel";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider } from "@/lib/stores/transport";
import { WorkspaceProvider } from "@/lib/stores/workspace";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <TimelineProvider>
      <TransportProvider>
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}

describe("AskPanel polish", () => {
  it("explains useful question scope and keeps the send affordance compact", () => {
    render(<AskPanel />, { wrapper });

    expect(screen.getByText(/Ask about harmony, rhythm, structure, or a selected passage/)).toBeVisible();
    expect(screen.getByText(/Answers use the evidence currently available for this recording/)).toBeVisible();

    const send = screen.getByRole("button", { name: "Send question" });
    expect(send).toBeDisabled();
    expect(send).toHaveStyle({ borderRadius: "6px" });
    expect(send.querySelector("svg")).toHaveAttribute("width", "14");
    expect(send.querySelector("svg")).toHaveAttribute("height", "14");
  });
});
