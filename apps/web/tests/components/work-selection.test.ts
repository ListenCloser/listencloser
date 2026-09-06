import { describe, expect, it } from "vitest";
import { successorAfterDelete } from "@/lib/work-selection";

const works = [
  { id: "a", title: "First" },
  { id: "b", title: "Second" },
  { id: "c", title: "Third" },
];

describe("successorAfterDelete", () => {
  it("selects the next durable work when deleting from the middle", () => {
    expect(successorAfterDelete(works, "b")?.id).toBe("c");
  });

  it("falls back to the previous work when deleting the last row", () => {
    expect(successorAfterDelete(works, "c")?.id).toBe("b");
  });

  it("returns null only when deleting the sole work", () => {
    expect(successorAfterDelete([{ id: "only" }], "only")).toBeNull();
  });

  it("fails closed when the deleting id is not in the durable list", () => {
    expect(successorAfterDelete(works, "missing")).toBeNull();
  });
});
