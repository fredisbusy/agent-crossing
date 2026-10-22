import Phaser from "phaser";
import { clampZoom, fitZoom, paddedBounds } from "./camera-fit";

const ZOOM_STEP = 0.1;

/** 맵 경계 안에서 드래그 이동, 휠 줌. 줌 아래 한계는 `fitZoom`(지도 전체 또는 화면 덮기). */
export function attachCameraControls(scene: Phaser.Scene, widthPx: number, heightPx: number): void {
  const camera = scene.cameras.main;
  // 줌이 바뀔 때마다 띠만큼 경계를 다시 잡아 지도가 가운데 머물게 한다.
  const setZoom = (zoom: number): void => {
    camera.setZoom(zoom);
    const b = paddedBounds(scene.scale.width, scene.scale.height, widthPx, heightPx, zoom);
    camera.setBounds(b.x, b.y, b.width, b.height);
  };
  let minZoom = fitZoom(scene.scale.width, scene.scale.height, widthPx, heightPx);
  setZoom(minZoom);
  camera.centerOn(widthPx / 2, heightPx / 2);

  const onResize = (size: Phaser.Structs.Size): void => {
    minZoom = fitZoom(size.width, size.height, widthPx, heightPx);
    setZoom(Math.max(camera.zoom, minZoom));
  };
  scene.scale.on(Phaser.Scale.Events.RESIZE, onResize);
  scene.events.once(Phaser.Scenes.Events.SHUTDOWN, () => scene.scale.off(Phaser.Scale.Events.RESIZE, onResize));

  scene.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
    if (!pointer.isDown) return;
    camera.scrollX -= (pointer.x - pointer.prevPosition.x) / camera.zoom;
    camera.scrollY -= (pointer.y - pointer.prevPosition.y) / camera.zoom;
  });

  scene.input.on("wheel", (_pointer: Phaser.Input.Pointer, _objects: unknown, _dx: number, dy: number) => {
    setZoom(clampZoom(camera.zoom * (1 + (dy > 0 ? -ZOOM_STEP : ZOOM_STEP)), minZoom));
  });
}
