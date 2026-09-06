import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkRow } from "@/components/workspace/LibraryPanel";

function renderRow(overrides: Partial<React.ComponentProps<typeof WorkRow>> = {}) {
  const onPrefetch = vi.fn();
  render(
    <WorkRow
      work={{ id: "work-2", title: "Second recording" }}
      selected={false}
      isLoading={false}
      isDeleting={false}
      onDelete={vi.fn()}
      onOpen={vi.fn()}
      onPrefetch={onPrefetch}
      {...overrides}
    />,
  );
  return { onPrefetch, row: screen.getByRole("button", { name: /^Second recordingReady$/ }) };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Library WorkRow intent prefetch", () => {
  it("waits for deliberate pointer intent and cancels a fly-by", () => {
    vi.useFakeTimers();
    const { onPrefetch, row } = renderRow();

    fireEvent.pointerEnter(row);
    vi.advanceTimersByTime(80);
    fireEvent.pointerLeave(row);
    vi.advanceTimersByTime(100);
    expect(onPrefetch).not.toHaveBeenCalled();

    fireEvent.pointerEnter(row);
    vi.advanceTimersByTime(120);
    expect(onPrefetch).toHaveBeenCalledTimes(1);
  });

  it("prefetches immediately for keyboard focus", () => {
    vi.useFakeTimers();
    const { onPrefetch, row } = renderRow();

    fireEvent.focus(row);
    expect(onPrefetch).toHaveBeenCalledTimes(1);
  });

  it("does not prefetch the already-selected Work", () => {
    vi.useFakeTimers();
    const { onPrefetch, row } = renderRow({ selected: true });

    fireEvent.pointerEnter(row);
    vi.advanceTimersByTime(200);
    fireEvent.focus(row);
    expect(onPrefetch).not.toHaveBeenCalled();
  });
});
