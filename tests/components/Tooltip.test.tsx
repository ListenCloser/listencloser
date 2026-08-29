import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Tooltip from "@/components/ui/Tooltip";

describe("Tooltip", () => {
  it("links the trigger to the tooltip without changing its accessible name", () => {
    render(
      <Tooltip content="Play recording">
        <button type="button" aria-label="Play">Play</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Play" });
    const tooltip = screen.getByRole("tooltip", { name: "Play recording" });

    expect(trigger).toHaveAttribute("aria-describedby", tooltip.id);
    expect(trigger).not.toHaveAttribute("title");
  });

  it("preserves an existing description relationship", () => {
    render(
      <>
        <span id="existing-help">Existing help</span>
        <Tooltip content="Loop selected region">
          <button type="button" aria-describedby="existing-help">Region</button>
        </Tooltip>
      </>,
    );

    const trigger = screen.getByRole("button", { name: "Region" });
    const tooltip = screen.getByRole("tooltip", { name: "Loop selected region" });

    expect(trigger.getAttribute("aria-describedby")?.split(" ")).toEqual(["existing-help", tooltip.id]);
  });

  it("supports a side placement without changing tooltip semantics", () => {
    render(
      <Tooltip content="Delete recording" placement="left">
        <button type="button" aria-label="Delete recording">Delete</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Delete recording" });
    const tooltip = screen.getByRole("tooltip", { name: "Delete recording" });

    expect(trigger).toHaveAttribute("aria-describedby", tooltip.id);
    expect(tooltip.className).toContain("tooltipLeft");
  });
});
