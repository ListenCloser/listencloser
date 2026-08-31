const FALLBACK_UI_FONT = "system-ui, sans-serif";
const FALLBACK_MEASUREMENT_SIZE = "11px";

/**
 * Resolve the shared canvas typography used for measured axes/rulers.
 *
 * Canvas text does not inherit CSS font-family/font-size, so every canvas that
 * paints measurement labels must explicitly consume the same UI tokens as the
 * surrounding application rather than falling back to a renderer-specific or
 * monospace font.
 */
export function canvasMeasurementFont(styles: CSSStyleDeclaration): string {
  const size = styles.getPropertyValue("--fs-xs").trim() || FALLBACK_MEASUREMENT_SIZE;
  const family = styles.getPropertyValue("--font-sans").trim() || FALLBACK_UI_FONT;
  return `${size} ${family}`;
}
