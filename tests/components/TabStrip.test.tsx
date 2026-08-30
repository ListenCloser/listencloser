import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import TabStrip from "@/components/ui/TabStrip";

function Harness() {
  const [value, setValue] = useState<"waveform" | "score" | "analysis">("waveform");
  return (
    <TabStrip
      label="Music representation"
      items={[
        { id: "waveform", label: "Waveform" },
        { id: "score", label: "Score" },
        { id: "analysis", label: "Analysis" },
      ]}
      value={value}
      onChange={setValue}
    />
  );
}

function DisabledHarness() {
  const [value, setValue] = useState<"waveform" | "score" | "analysis">("waveform");
  return (
    <TabStrip
      label="Music representation"
      items={[
        { id: "waveform", label: "Waveform" },
        { id: "score", label: "Score", disabled: true },
        { id: "analysis", label: "Analysis" },
      ]}
      value={value}
      onChange={setValue}
    />
  );
}

describe("TabStrip", () => {
  it("uses a single roving tab stop and arrow-key navigation", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const waveform = screen.getByRole("tab", { name: "Waveform" });
    const score = screen.getByRole("tab", { name: "Score" });
    const analysis = screen.getByRole("tab", { name: "Analysis" });

    expect(waveform).toHaveAttribute("aria-selected", "true");
    expect(waveform).toHaveAttribute("tabindex", "0");
    expect(score).toHaveAttribute("tabindex", "-1");

    waveform.focus();
    await user.keyboard("{ArrowRight}");
    expect(score).toHaveAttribute("aria-selected", "true");
    expect(score).toHaveFocus();

    await user.keyboard("{End}");
    expect(analysis).toHaveAttribute("aria-selected", "true");
    expect(analysis).toHaveFocus();

    await user.keyboard("{ArrowRight}");
    expect(waveform).toHaveAttribute("aria-selected", "true");
    expect(waveform).toHaveFocus();
  });

  it("skips disabled tabs in both directions", async () => {
    const user = userEvent.setup();
    render(<DisabledHarness />);

    const waveform = screen.getByRole("tab", { name: "Waveform" });
    const score = screen.getByRole("tab", { name: "Score" });
    const analysis = screen.getByRole("tab", { name: "Analysis" });

    expect(score).toBeDisabled();
    waveform.focus();
    await user.keyboard("{ArrowRight}");
    expect(analysis).toHaveFocus();
    expect(analysis).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowLeft}");
    expect(waveform).toHaveFocus();
    expect(waveform).toHaveAttribute("aria-selected", "true");
  });
});
