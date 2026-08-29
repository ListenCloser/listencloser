import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AskPanel from "@/components/workspace/AskPanel";
import { askMusic } from "@/lib/ask/client";
import type { AskResponse } from "@/lib/ask/types";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider, useTransport } from "@/lib/stores/transport";
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
let transportStore: ReturnType<typeof useTransport> | null = null;

function Probe() {
  store = useWorkspace();
  transportStore = useTransport();
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
  transportStore = null;
});

async function askOnWorkA(user: ReturnType<typeof userEvent.setup>) {
  act(() => store!.setActiveWorkId("work-a"));
  await user.type(screen.getByRole("textbox", { name: "Ask about the music" }), "What key is detected?");
  await user.click(screen.getByRole("button", { name: "Send question" }));
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

describe("AskPanel blocked action help", () => {
  it("keeps cross-domain actions and references focusable, explained, and inert", async () => {
    const user = userEvent.setup();
    render(<Probe />, { wrapper });

    act(() => {
      store!.setActiveWorkId("work-a");
      transportStore!.replaceSources([
        {
          id: "original-audio",
          label: "Original audio",
          url: "data:audio/wav;base64,audio",
          kind: "audio",
          role: "original",
        },
      ], "original-audio");
      store!.appendAskMessage({
        id: "assistant-blocked",
        role: "assistant",
        response: {
          answer: "This answer contains a notation-time suggestion while performance audio is active.",
          references: [{ type: "time", start: 4, end: 8, domain: "notation" }],
          suggestedActions: [{ type: "loop", start: 4, end: 8, domain: "notation" }],
        },
      });
    });

    const blockedReference = screen.getByRole("button", { name: "0:04–0:08" });
    const blockedAction = screen.getByRole("button", { name: "Loop passage" });

    expect(blockedReference).toHaveAttribute("aria-disabled", "true");
    expect(blockedAction).toHaveAttribute("aria-disabled", "true");
    expect(blockedReference).not.toBeDisabled();
    expect(blockedAction).not.toBeDisabled();
    expect(blockedReference).not.toHaveAttribute("title");
    expect(blockedAction).not.toHaveAttribute("title");

    const referenceDescription = blockedReference.getAttribute("aria-describedby");
    const actionDescription = blockedAction.getAttribute("aria-describedby");
    expect(referenceDescription).toBeTruthy();
    expect(actionDescription).toBeTruthy();
    expect(document.getElementById(referenceDescription!)).toHaveTextContent("This reference uses a different timeline than the active source.");
    expect(document.getElementById(actionDescription!)).toHaveTextContent("This matches a different timeline than the active source.");

    blockedAction.focus();
    expect(blockedAction).toHaveFocus();

    const positionBefore = transportStore!.transport.position;
    expect(transportStore!.transport.loopEnabled).toBe(false);
    await user.click(blockedReference);
    await user.click(blockedAction);
    expect(transportStore!.transport.position).toBe(positionBefore);
    expect(transportStore!.transport.loopEnabled).toBe(false);
  });
});
