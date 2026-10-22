import type { MapSprite } from "../../map/objects";
import { TILE_SIZE } from "../../../town-layout";

export type SeatFacing = "down" | "up" | "right";

/** 주민이 앉을 수 있는 칸: 의자(방향 있음)·소파·벤치(아래를 본다). */
export interface SeatSpot {
  kind: "seat";
  facing: SeatFacing;
}

/** 침대 칸. `bottomPx`는 침대 그림 아랫변(월드 px)으로, 자는 그림의 발밑을 여기에 맞춘다. */
export interface BedSpot {
  kind: "bed";
  bottomPx: number;
}

export type Spot = SeatSpot | BedSpot;

const CHAIR_FACING: Readonly<Record<string, SeatFacing>> = {
  furn_chair_down: "down",
  furn_chair_up: "up",
  furn_chair_right: "right",
};
/** 맵 decor 중 앉을 수 있는 것(`scripts/maps/town_decor.py`의 `bench_h`). */
const BENCH_FRAME = "bench_h";
const SOFA_FRAME = "furn_sofa";
const BED_FRAMES: ReadonlySet<string> = new Set(["furn_bed", "furn_bed_double"]);

function seatFor(frame: string): SeatSpot | null {
  const chair = CHAIR_FACING[frame];
  if (chair) return { kind: "seat", facing: chair };
  if (frame === BENCH_FRAME || frame === SOFA_FRAME) return { kind: "seat", facing: "down" };
  return null;
}

/** 칸 좌표 → 앉기·눕기 자리. 가구·장식 객체 목록만 보고 만든다(맵 로직과 독립). */
export class SpotMap {
  private readonly spots = new Map<string, Spot>();

  constructor(furniture: readonly MapSprite[], decor: readonly MapSprite[]) {
    for (const sprite of [...furniture, ...decor]) this.add(sprite);
  }

  spotAt(tileX: number, tileY: number): Spot | null {
    return this.spots.get(`${tileX},${tileY}`) ?? null;
  }

  private add(sprite: MapSprite): void {
    const spot: Spot | null = BED_FRAMES.has(sprite.frame)
      ? { kind: "bed", bottomPx: sprite.y + sprite.height }
      : seatFor(sprite.frame);
    if (spot === null) return;
    const firstX = Math.floor(sprite.x / TILE_SIZE);
    const firstY = Math.floor(sprite.y / TILE_SIZE);
    const cols = Math.max(1, Math.round(sprite.width / TILE_SIZE));
    const rows = Math.max(1, Math.round(sprite.height / TILE_SIZE));
    for (let dy = 0; dy < rows; dy += 1) {
      for (let dx = 0; dx < cols; dx += 1) this.spots.set(`${firstX + dx},${firstY + dy}`, spot);
    }
  }
}
