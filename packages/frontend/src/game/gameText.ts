import Phaser from "phaser";

export const GAME_UI_FONT =
  'Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", sans-serif';

const MIN_TEXT_RESOLUTION = 2;
const MAX_TEXT_RESOLUTION = 3;

export function makeCrispText(
  text: Phaser.GameObjects.Text,
): Phaser.GameObjects.Text {
  const resolution = Phaser.Math.Clamp(
    window.devicePixelRatio || 1,
    MIN_TEXT_RESOLUTION,
    MAX_TEXT_RESOLUTION,
  );
  text.setResolution(resolution);
  text.texture.setFilter(Phaser.Textures.FilterMode.LINEAR);
  return text;
}
