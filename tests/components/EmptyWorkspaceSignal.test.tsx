import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EmptyWorkspaceSignal from "@/components/workspace/EmptyWorkspaceSignal";

describe("EmptyWorkspaceSignal", () => {
  it("stays decorative while presenting the shared-time visual scaffold", () => {
    render(<EmptyWorkspaceSignal />);

    const signal = screen.getByTestId("empty-workspace-signal");
    expect(signal).toHaveAttribute("aria-hidden", "true");
    expect(signal).toHaveTextContent("One recording");
    expect(signal).toHaveTextContent("Shared musical time");
    expect(signal).toHaveTextContent("Audio");
    expect(signal).toHaveTextContent("Notes");
    expect(signal).toHaveTextContent("Notation");
    expect(signal).toHaveTextContent("Evidence");
    expect(signal).not.toHaveTextContent(/analyzing|processing|%/i);
  });
});
