import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AddAnalysis from "@/components/workspace/AddAnalysis";

describe("Add analysis entrance", () => {
  it("opens the shared chooser without exposing engine vocabulary", () => {
    const onOpenChange = vi.fn();
    render(
      <AddAnalysis
        open={false}
        onOpenChange={onOpenChange}
        options={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "+ Add analysis" }));
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });
});
