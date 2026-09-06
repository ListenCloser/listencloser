const FALLBACK_UI_FONT = "system-ui, sans-serif";
const FALLBACK_MEASUREMENT_SIZE = "10px";
const FALLBACK_MEASUREMENT_WEIGHT = "500";

/**
 * Resolve the shared canvas typography used for measured axes/rulers.
 *
 * Canvas text does not inherit CSS typography. Keep every measured renderer on
 * the same UI family/size/weight contract instead of letting individual
 * canvases silently fall back to browser defaults or renderer-specific fonts.
 */
export function canvasMeasurementFont(styles: CSSStyleDeclaration): string {
  const size = styles.getPropertyValue("--measurement-font-size").trim()
    || FALLBACK_MEASUREMENT_SIZE;
  const weight = styles.getPropertyValue("--measurement-font-weight").trim()
    || FALLBACK_MEASUREMENT_WEIGHT;
  const family = styles.getPropertyValue("--font-sans").trim() || FALLBACK_UI_FONT;
  return `${weight} ${size} ${family}`;
}
