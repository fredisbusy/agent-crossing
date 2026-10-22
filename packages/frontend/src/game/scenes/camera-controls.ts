import Phaser from "phaser";

export const MAX_ZOOM = 4;
const ZOOM_STEP = 0.1;
/** 지도를 화면에 덮는 기본 줌은 이 간격으로 올림해 픽셀이 고르게 보이게 한다. */
const COVER_ZOOM_STEP = 0.125;

/** 지도가 화면을 빈틈없이 덮는 최소 줌(가로·세로 중 큰 쪽 기준, 1/8 간격 올림). */
export function coverZoom(viewWidth: number, viewHeight: number, widthPx: number, heightPx: number): number {
  const exact = Math.max(viewWidth / widthPx, viewHeight / heightPx);
  return Math.min(MAX_ZOOM, Math.ceil(exact / COVER_ZOOM_STEP - 1e-9) * COVER_ZOOM_STEP);
}

export function clampZoom(zoom: number, minZoom = 0.5): number {
  return Math.min(MAX_ZOOM, Math.max(minZoom, zoom));
}

/** 맵 경계 안에서 드래그 이동, 휠 줌. 줌 아래 한계는 지도가 화면보다 작아지지 않는 값. */
export function attachCameraControls(scene: Phaser.Scene, widthPx: number, heightPx: number): void {
  const camera = scene.cameras.main;
  camera.setBounds(0, 0, widthPx, heightPx);
  let minZoom = coverZoom(scene.scale.width, scene.scale.height, widthPx, heightPx);
  camera.setZoom(minZoom);
  camera.centerOn(widthPx / 2, heightPx / 2);

  const onResize = (size: Phaser.Structs.Size): void => {
    minZoom = coverZoom(size.width, size.height, widthPx, heightPx);
    if (camera.zoom < minZoom) camera.setZoom(minZoom);
  };
  scene.scale.on(Phaser.Scale.Events.RESIZE, onResize);
  scene.events.once(Phaser.Scenes.Events.SHUTDOWN, () => scene.scale.off(Phaser.Scale.Events.RESIZE, onResize));

  scene.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
    if (!pointer.isDown) return;
    camera.scrollX -= (pointer.x - pointer.prevPosition.x) / camera.zoom;
    camera.scrollY -= (pointer.y - pointer.prevPosition.y) / camera.zoom;
  });

  scene.input.on("wheel", (_pointer: Phaser.Input.Pointer, _objects: unknown, _dx: number, dy: number) => {
    camera.setZoom(clampZoom(camera.zoom * (1 + (dy > 0 ? -ZOOM_STEP : ZOOM_STEP)), minZoom));
  });
}
