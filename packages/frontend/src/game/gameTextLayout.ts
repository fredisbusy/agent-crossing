import type { GameTextOverlay } from "./gameText";

interface TextRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

const CHARACTER_LABEL_PREFIXES = ["agent:", "indoor-agent:", "resident:"];
const LABEL_GAP = 6;

export function resolveCharacterTextOverlaps(
  overlays: readonly GameTextOverlay[],
): GameTextOverlay[] {
  const occupied: TextRect[] = [];
  return overlays.map((overlay) => {
    if (!isCharacterLabel(overlay)) return overlay;

    let adjusted = overlay;
    let bounds = estimateTextBounds(adjusted);
    for (let attempt = 0; attempt < 16; attempt += 1) {
      if (!occupied.some((candidate) => intersects(bounds, candidate))) break;
      adjusted = {
        ...adjusted,
        top: adjusted.top - boundsHeight(bounds) - LABEL_GAP,
      };
      bounds = estimateTextBounds(adjusted);
    }
    occupied.push(bounds);
    return adjusted;
  });
}

function isCharacterLabel(overlay: GameTextOverlay): boolean {
  return (
    (overlay.tone === "bubble" || overlay.tone === "nameplate") &&
    CHARACTER_LABEL_PREFIXES.some((prefix) => overlay.id.startsWith(prefix))
  );
}

function estimateTextBounds(overlay: GameTextOverlay): TextRect {
  const characterWidth = overlay.tone === "bubble" ? 7 : 8;
  const horizontalPadding = overlay.tone === "bubble" ? 22 : 14;
  const maxWidth = overlay.maxWidth ?? Number.POSITIVE_INFINITY;
  const width = Math.min(
    maxWidth,
    Math.max(
      48,
      Array.from(overlay.text).length * characterWidth + horizontalPadding,
    ),
  );
  const contentWidth = Math.max(width - horizontalPadding, 1);
  const lines =
    overlay.tone === "bubble"
      ? Math.max(
          1,
          Math.ceil(
            (Array.from(overlay.text).length * characterWidth) / contentWidth,
          ),
        )
      : 1;
  const height = lines * 18 + (overlay.tone === "bubble" ? 14 : 8);

  let left = overlay.left - width / 2;
  let top = overlay.top - height / 2;
  if (overlay.anchor === "bottom") top = overlay.top - height;
  if (overlay.anchor === "top") top = overlay.top;
  if (overlay.anchor === "left-top") {
    left = overlay.left;
    top = overlay.top;
  }
  if (overlay.anchor === "right-top") {
    left = overlay.left - width;
    top = overlay.top;
  }
  return { left, top, right: left + width, bottom: top + height };
}

function intersects(left: TextRect, right: TextRect): boolean {
  return !(
    left.right + LABEL_GAP <= right.left ||
    right.right + LABEL_GAP <= left.left ||
    left.bottom + LABEL_GAP <= right.top ||
    right.bottom + LABEL_GAP <= left.top
  );
}

function boundsHeight(bounds: TextRect): number {
  return bounds.bottom - bounds.top;
}
