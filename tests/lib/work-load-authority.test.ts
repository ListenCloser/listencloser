import { describe, expect, it } from "vitest";
import { canPublishWorkLoad } from "@/lib/work-load-authority";

describe("work-load publication authority", () => {
  it("rejects a late load for a Work the user has left", () => {
    expect(canPublishWorkLoad({
      workId: "work-a",
      activeWorkId: "work-b",
      sequence: 4,
      latestSequence: 4,
    })).toBe(false);
  });

  it("rejects an older request even when it targets the active Work", () => {
    expect(canPublishWorkLoad({
      workId: "work-a",
      activeWorkId: "work-a",
      sequence: 4,
      latestSequence: 5,
    })).toBe(false);
  });

  it("allows only the latest load for the active Work", () => {
    expect(canPublishWorkLoad({
      workId: "work-a",
      activeWorkId: "work-a",
      sequence: 5,
      latestSequence: 5,
    })).toBe(true);
  });
});
