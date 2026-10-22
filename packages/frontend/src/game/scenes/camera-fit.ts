/** 카메라 줌·경계 계산(Phaser 없이 테스트한다). */

export const MAX_ZOOM = 4;
/** 지도를 화면에 덮는 기본 줌은 이 간격으로 올림해 픽셀이 고르게 보이게 한다. */
const COVER_ZOOM_STEP = 0.125;

/** 지도가 화면을 빈틈없이 덮는 최소 줌(가로·세로 중 큰 쪽 기준, 1/8 간격 올림). */
export function coverZoom(viewWidth: number, viewHeight: number, widthPx: number, heightPx: number): number {
  const exact = Math.max(viewWidth / widthPx, viewHeight / heightPx);
  return Math.min(MAX_ZOOM, Math.ceil(exact / COVER_ZOOM_STEP - 1e-9) * COVER_ZOOM_STEP);
}

/**
 * 지도 전체가 들어오는 줌(1/8 간격 내림). 화면이 지도보다 세로로 길면 위아래에 띠가 생긴다.
 */
export function containZoom(viewWidth: number, viewHeight: number, widthPx: number, heightPx: number): number {
  const exact = Math.min(viewWidth / widthPx, viewHeight / heightPx);
  return Math.min(MAX_ZOOM, Math.max(COVER_ZOOM_STEP, Math.floor(exact / COVER_ZOOM_STEP + 1e-9) * COVER_ZOOM_STEP));
}

/** 지도 전체를 담느라 생기는 빈 띠가 이 비율(줌 기준)보다 작으면 덮기 대신 담기를 쓴다. */
const MAX_LETTERBOX = 0.2;

/**
 * 기본(최소) 줌. 데스크톱처럼 화면 비율이 지도와 비슷하면 지도 전체를 담아 양끝 건물이 잘리지 않게 하고,
 * 세로 모바일처럼 차이가 크면 지도로 화면을 덮는다(빈 띠가 너무 커지므로).
 */
export function fitZoom(viewWidth: number, viewHeight: number, widthPx: number, heightPx: number): number {
  const cover = coverZoom(viewWidth, viewHeight, widthPx, heightPx);
  const contain = containZoom(viewWidth, viewHeight, widthPx, heightPx);
  return 1 - contain / cover <= MAX_LETTERBOX ? contain : cover;
}

/** 줌에서 지도가 화면보다 작은 축은 양쪽으로 띠만큼 경계를 넓혀 지도가 가운데 오게 한다. */
export function paddedBounds(
  viewWidth: number,
  viewHeight: number,
  widthPx: number,
  heightPx: number,
  zoom: number,
): { x: number; y: number; width: number; height: number } {
  const padX = Math.max(0, (viewWidth / zoom - widthPx) / 2);
  const padY = Math.max(0, (viewHeight / zoom - heightPx) / 2);
  // `0 - pad`: 띠가 없을 때 -0이 아니라 0이 되게 한다.
  return { x: 0 - padX, y: 0 - padY, width: widthPx + padX * 2, height: heightPx + padY * 2 };
}

export function clampZoom(zoom: number, minZoom = 0.5): number {
  return Math.min(MAX_ZOOM, Math.max(minZoom, zoom));
}
