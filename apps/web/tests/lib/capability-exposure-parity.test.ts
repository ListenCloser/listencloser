import { describe, expect, it } from "vitest";

import capabilityRegistry from "../../../../services/backend/config/capabilities.json";
import {
  ASK_EXPOSED_KINDS,
  INSPECTOR_EXPOSED_KINDS,
} from "@/lib/inspector/capabilities";

const capabilities = Object.entries(capabilityRegistry.capabilities);

function sorted(values: string[]): string[] {
  return [...values].sort();
}

describe("capability exposure parity", () => {
  it("keeps the Inspector presentation allowlist equal to backend authority", () => {
    const expected = capabilities
      .filter(([, capability]) => capability.exposure.inspector)
      .map(([kind]) => kind);

    expect(sorted(INSPECTOR_EXPOSED_KINDS)).toEqual(sorted(expected));
  });

  it("keeps the Ask presentation allowlist equal to backend authority", () => {
    const expected = capabilities
      .filter(([, capability]) => capability.exposure.ask)
      .map(([kind]) => kind);

    expect(sorted(ASK_EXPOSED_KINDS)).toEqual(sorted(expected));
  });

  it("keeps withheld and evaluation-only capabilities out of ordinary surfaces", () => {
    for (const [kind, capability] of capabilities) {
      if (capability.status !== "withheld" && capability.status !== "evaluation_only") continue;

      expect(capability.exposure, `${kind} must remain hidden`).toEqual({
        inspector: false,
        annotations: false,
        ask: false,
      });
    }
  });
});
