import Phaser from "phaser";

export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 4;
const ZOOM_STEP = 0.1;

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** 맵 경계 안에서 드래그 이동, 휠 줌. */
export function attachCameraControls(scene: Phaser.Scene, widthPx: number, heightPx: number): void {
  const camera = scene.cameras.main;
  camera.setBounds(0, 0, widthPx, heightPx);
  const fit = Math.min(camera.width / widthPx, camera.height / heightPx);
  camera.setZoom(clampZoom(Math.max(1, Math.floor(fit * 4) / 4)));
  camera.centerOn(widthPx / 2, heightPx / 2);

  scene.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
    if (!pointer.isDown) return;
    camera.scrollX -= (pointer.x - pointer.prevPosition.x) / camera.zoom;
    camera.scrollY -= (pointer.y - pointer.prevPosition.y) / camera.zoom;
  });

  scene.input.on("wheel", (_pointer: Phaser.Input.Pointer, _objects: unknown, _dx: number, dy: number) => {
    camera.setZoom(clampZoom(camera.zoom * (1 + (dy > 0 ? -ZOOM_STEP : ZOOM_STEP))));
  });
}
