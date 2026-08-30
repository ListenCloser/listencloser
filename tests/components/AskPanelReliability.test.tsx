import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AskPanel from "@/components/workspace/AskPanel";
import { askMusic } from "@/lib/ask/client";
import type { AskResponse } from "@/lib/ask/types";
import { ApiRequestError } from "@/lib/api";
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

let workspaceStore: ReturnType<typeof useWorkspace> | null = null;

function Probe() {
  workspaceStore = useWorkspace();
  return <AskPanel />;
}

const response: AskResponse = {
  answer: "The passage resolves to the tonic.",
  references: [],
  suggestedActions: [],
};

beforeEach(() => {
  vi.mocked(askMusic).mockReset();
  workspaceStore = null;
});

async function submitQuestion(user: ReturnType<typeof userEvent.setup>) {
  act(() => workspaceStore!.setActiveWorkId("work-a"));
  const textbox = screen.getByRole("textbox", { name: "Ask about the music" });
  await user.type(textbox, "What happens here?");
  await user.click(screen.getByRole("button", { name: "Send question" }));
}

describe("AskPanel reliability states", () => {
  it("keeps timeout failures compact, correlated, and retryable", async () => {
    const user = userEvent.setup();
    vi.mocked(askMusic)
      .mockRejectedValueOnce(new ApiRequestError("Ask timed out.", 504, "ask-timeout-123"))
      .mockResolvedValueOnce(response);

    render(<Probe />, { wrapper });
    await submitQuestion(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Ask took too long to respond. Try again.");
    expect(alert).toHaveTextContent("Reference: ask-timeout-123");
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(await screen.findByText(response.answer)).toBeVisible();
    expect(askMusic).toHaveBeenCalledTimes(2);
  });

  it("renders the shared selection as a dismissible question-context chip", async () => {
    const user = userEvent.setup();
    render(<Probe />, { wrapper });

    act(() => {
      workspaceStore!.setActiveWorkId("work-a");
      workspaceStore!.setSelection({
        timeRange: { start: 4, end: 8, domain: "performance" },
        provenance: {
          origin: "waveform",
          timeExact: true,
          measureApproximate: false,
        },
      });
    });

    expect(screen.getByLabelText(/Question context:/)).toBeVisible();
    expect(screen.getByPlaceholder("Ask a question about this selection…")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Clear question context" }));

    expect(workspaceStore!.workspace.selection).toBeNull();
    expect(screen.queryByRole("button", { name: "Clear question context" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholder("Ask a question about this recording…")).toBeVisible();
  });

  it("maps upstream unavailability to safe copy while preserving the request reference", async () => {
    const user = userEvent.setup();
    vi.mocked(askMusic).mockRejectedValue(
      new ApiRequestError("Processing service unavailable", 502, "proxy-req-456"),
    );

    render(<Probe />, { wrapper });
    await submitQuestion(user);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Ask is temporarily unavailable. Try again.");
    expect(alert).toHaveTextContent("Reference: proxy-req-456");
    expect(alert).not.toHaveTextContent("Processing service unavailable");
  });
});
