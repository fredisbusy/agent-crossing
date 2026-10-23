/** 그리기에 쓰는 캔버스 2D 일부(테스트에서 가짜로 바꾼다). */
export type Painter = Pick<CanvasRenderingContext2D, "fillStyle" | "fillRect">;

/** 색 하나로 사각형을 채운다. */
export function rect(ctx: Painter, color: string, x: number, y: number, w: number, h: number): void {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w, h);
}
