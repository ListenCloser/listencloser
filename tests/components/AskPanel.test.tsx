import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AskPanel from "@/components/workspace/AskPanel";
import { askMusic } from "@/lib/ask/client";
import type { AskResponse } from "@/lib/ask/types";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider } from "@/lib/stores/transport";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";

vi.mock("@/lib/ask/client", () => ({
  askMusic: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  return (
    <TimelineProvider>
      <TransportProvider>
        <WorkspaceProvider>{children}</WorkspaceProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}

let store: ReturnType<typeof useWorkspace> | null = null;

function Probe() {
  store = useWorkspace();
  return <AskPanel />;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const response: AskResponse = {
  answer: "It's in C major.",
  references: [],
  suggestedActions: [],
};

beforeEach(() => {
  vi.mocked(askMusic).mockReset();
  store = null;
});

async function askOnWorkA(user: ReturnType<typeof userEvent.setup>) {
  act(() => store!.setActiveWorkId("work-a"));
  await user.click(screen.getByText("What is happening harmonically here?"));
}

describe("AskPanel work-switch lifecycle", () => {
  it("discards a stale in-flight response when the work switches", async () => {
    const user = userEvent.setup();
    const d = deferred<AskResponse>();
    vi.mocked(askMusic).mockReturnValue(d.promise);
    render(<Probe />, { wrapper });

    await askOnWorkA(user);
    expect(store!.workspace.askConversation).toHaveLength(1);

    act(() => store!.setActiveWorkId("work-b"));
    expect(store!.workspace.askConversation).toEqual([]);

    await act(async () => {
      d.resolve(response);
      await d.promise;
    });

    expect(store!.workspace.askConversation).toEqual([]);
    expect(screen.queryByText(response.answer)).not.toBeInTheDocument();
  });

  it("does not surface stale error or retry state from a previous work", async () => {
    const user = userEvent.setup();
    const d = deferred<AskResponse>();
    vi.mocked(askMusic).mockReturnValue(d.promise);
    render(<Probe />, { wrapper });

    await askOnWorkA(user);

    act(() => store!.setActiveWorkId("work-b"));

    await act(async () => {
      d.reject(new Error("network"));
    });

    expect(store!.workspace.askConversation).toEqual([]);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Try again")).not.toBeInTheDocument();
  });

  it("appends the assistant response for the current work", async () => {
    const user = userEvent.setup();
    const d = deferred<AskResponse>();
    vi.mocked(askMusic).mockReturnValue(d.promise);
    render(<Probe />, { wrapper });

    await askOnWorkA(user);

    await act(async () => {
      d.resolve(response);
      await d.promise;
    });

    expect(store!.workspace.askConversation).toHaveLength(2);
    expect(screen.getByText(response.answer)).toBeInTheDocument();
  });
});