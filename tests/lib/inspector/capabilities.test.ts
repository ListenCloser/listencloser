import { describe, expect, it } from "vitest";
import { isInspectorExposed, isExperimental, INSPECTOR_EXPOSED_KINDS } from "@/lib/inspector/capabilities";

/**
 * These tests verify the frontend presentation helpers align with the
 * backend's authoritative capability policy (capabilities.json).
 *
 * The backend is the source of truth. These tests ensure the frontend
 * does not accidentally expose withheld capabilities.
 */

describe("capabilities", () => {
  describe("isInspectorExposed", () => {
    it("returns true for production capabilities with inspector exposure", () => {
      expect(isInspectorExposed("key")).toBe(true);
      expect(isInspectorExposed("chord")).toBe(true);
      expect(isInspectorExposed("roman_numeral")).toBe(true);
      expect(isInspectorExposed("harmonic_function")).toBe(true);
      expect(isInspectorExposed("tempo")).toBe(true);
      expect(isInspectorExposed("audio_tempo")).toBe(true);
      expect(isInspectorExposed("time_signature")).toBe(true);
      expect(isInspectorExposed("rhythm")).toBe(true);
      expect(isInspectorExposed("rhythm_density")).toBe(true);
      expect(isInspectorExposed("rhythm_rests")).toBe(true);
    });

    it("returns true for experimental capabilities with inspector exposure", () => {
      expect(isInspectorExposed("melody")).toBe(true);
      expect(isInspectorExposed("melody_register_peak")).toBe(true);
      expect(isInspectorExposed("melody_register_low")).toBe(true);
    });

    it("returns false for withheld capabilities", () => {
      expect(isInspectorExposed("cadence")).toBe(false);
      expect(isInspectorExposed("key_region")).toBe(false);
      expect(isInspectorExposed("harmonic_rhythm")).toBe(false);
      expect(isInspectorExposed("voice_leading")).toBe(false);
    });

    it("returns false for evaluation-only capabilities", () => {
      expect(isInspectorExposed("section")).toBe(false);
      expect(isInspectorExposed("audio_structure")).toBe(false);
      expect(isInspectorExposed("structure")).toBe(false);
    });

    it("returns false for unknown capability kinds", () => {
      expect(isInspectorExposed("unknown_kind")).toBe(false);
      expect(isInspectorExposed("")).toBe(false);
    });
  });

  describe("isExperimental", () => {
    it("returns true for experimental capabilities", () => {
      expect(isExperimental("melody")).toBe(true);
    });

    it("returns false for production capabilities", () => {
      expect(isExperimental("key")).toBe(false);
      expect(isExperimental("chord")).toBe(false);
    });

    it("returns false for withheld capabilities", () => {
      expect(isExperimental("cadence")).toBe(false);
    });
  });

  describe("INSPECTOR_EXPOSED_KINDS", () => {
    it("includes all production inspector-exposed kinds", () => {
      expect(INSPECTOR_EXPOSED_KINDS).toContain("key");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("chord");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("roman_numeral");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("harmonic_function");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("tempo");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("audio_tempo");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("time_signature");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("rhythm");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("rhythm_density");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("rhythm_rests");
    });

    it("includes experimental inspector-exposed kinds", () => {
      expect(INSPECTOR_EXPOSED_KINDS).toContain("melody");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("melody_register_peak");
      expect(INSPECTOR_EXPOSED_KINDS).toContain("melody_register_low");
    });

    it("excludes withheld kinds", () => {
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("cadence");
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("key_region");
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("harmonic_rhythm");
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("voice_leading");
    });

    it("excludes evaluation-only kinds", () => {
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("section");
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("audio_structure");
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain("structure");
    });
  });

  describe("defense-in-depth: withheld kinds cannot be exposed", () => {
    /**
     * This test verifies the critical invariant: the frontend cannot
     * expose a backend-filtered withheld kind. If the backend sends
     * a withheld kind (bug), the frontend will filter it out.
     */
    const WITHHELD_KINDS = ["cadence", "key_region", "harmonic_rhythm", "voice_leading"];

    it.each(WITHHELD_KINDS)("%s is not exposed in inspector", (kind) => {
      expect(isInspectorExposed(kind)).toBe(false);
    });

    it.each(WITHHELD_KINDS)("%s is not in INSPECTOR_EXPOSED_KINDS", (kind) => {
      expect(INSPECTOR_EXPOSED_KINDS).not.toContain(kind);
    });
  });
});
