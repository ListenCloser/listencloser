import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LibraryImportControl from "@/components/workspace/LibraryImportControl";

describe("LibraryImportControl", () => {
  it("preserves local upload and exposes the public library as a second choice", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn();
    render(
      <LibraryImportControl
        disabled={false}
        onUpload={onUpload}
        onImport={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Import audio" }));
    await user.click(screen.getByRole("button", { name: /Upload recording/ }));
    expect(onUpload).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Import audio" }));
    await user.click(screen.getByRole("button", { name: /Explore public library/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Für Elise")).toBeInTheDocument();
    expect(screen.getByText("Jazz Ride Pattern")).toBeInTheDocument();
    expect(screen.getByText("Jesse James")).toBeInTheDocument();
  });

  it("filters the catalog and imports the selected recording", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);
    render(
      <LibraryImportControl
        disabled={false}
        onUpload={vi.fn()}
        onImport={onImport}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Import audio" }));
    await user.click(screen.getByRole("button", { name: /Explore public library/ }));
    await user.type(
      screen.getByRole("searchbox", { name: "Search public recordings" }),
      "jazz",
    );

    expect(screen.queryByText("Für Elise")).not.toBeInTheDocument();
    expect(screen.getByText("Jazz Ride Pattern")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => {
      expect(onImport).toHaveBeenCalledTimes(1);
      expect(onImport.mock.calls[0][0].id).toBe("jazz-ride-pattern");
    });
  });

  it("keeps the import action disabled while the library is unavailable", () => {
    render(
      <LibraryImportControl
        disabled
        onUpload={vi.fn()}
        onImport={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("button", { name: "Import audio" })).toBeDisabled();
  });
});
