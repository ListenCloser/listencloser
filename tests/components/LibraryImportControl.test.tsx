import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LibraryImportControl from "@/components/workspace/LibraryImportControl";

describe("LibraryImportControl", () => {
  it("preserves local upload and exposes the public library as a second choice", () => {
    const onUpload = vi.fn();
    render(
      <LibraryImportControl
        disabled={false}
        onUpload={onUpload}
        onImport={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recording" }));
    fireEvent.click(screen.getByRole("button", { name: /Upload recording/ }));
    expect(onUpload).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Import recording" }));
    fireEvent.click(screen.getByRole("button", { name: /Explore public library/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Für Elise")).toBeInTheDocument();
    expect(screen.getByText("Reggae Bultron")).toBeInTheDocument();
  });

  it("filters the catalog and imports the selected recording", async () => {
    const onImport = vi.fn().mockResolvedValue(undefined);
    render(
      <LibraryImportControl
        disabled={false}
        onUpload={vi.fn()}
        onImport={onImport}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recording" }));
    fireEvent.click(screen.getByRole("button", { name: /Explore public library/ }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Search public recordings" }), {
      target: { value: "reggae" },
    });

    expect(screen.queryByText("Für Elise")).not.toBeInTheDocument();
    expect(screen.getByText("Reggae Bultron")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => {
      expect(onImport).toHaveBeenCalledTimes(1);
      expect(onImport.mock.calls[0][0].id).toBe("reggae-bultron");
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

    expect(screen.getByRole("button", { name: "Import recording" })).toBeDisabled();
  });
});
