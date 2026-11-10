import type { MindKind, ResidentSnapshot, WorldSnapshot } from "@agent-crossing/shared";
import { buildFallbackMap } from "../game/map/pure";
import {
  findPath,
  locationAt,
  walkGridFromTiled,
  type WalkGrid,
  type WalkPlace,
} from "../town-layout";
import type { TilePoint } from "../tiled";

/** 시뮬레이션 시각이 틱마다 흐르는 분(가짜 피드 전용). */
export const MOCK_SIM_MINUTES_PER_TICK = 1;
export const MOCK_START_HOUR = 7;
export const MOCK_START_TIME_MS = Date.UTC(2026, 1, 13, MOCK_START_HOUR, 0, 0);
/** 한 틱에 주민이 말할 확률. */
export const MOCK_SPEAK_CHANCE = 0.08;
/** 목적지에 도착한 뒤 머무는 틱 수 범위. */
const MOCK_STAY_TICKS = { min: 5, max: 30 } as const;

export const DEFAULT_MOCK_SEED = 20230213;

interface MockResidentSpec {
  id: string;
  name: string;
  mind: MindKind;
  emoji: string;
}

const MOCK_RESIDENTS: readonly MockResidentSpec[] = [
  { id: "mochi", name: "Mochi", mind: "llm", emoji: "☕" },
  { id: "biscuit", name: "Biscuit", mind: "schedule", emoji: "🎒" },
  { id: "olive", name: "Olive", mind: "schedule", emoji: "🚶" },
  { id: "pip", name: "Pip", mind: "schedule", emoji: "🛒" },
];

const MOCK_LINES: readonly string[] = [
  "좋은 아침이에요!",
  "오늘 날씨 참 좋네요.",
  "카페 벌써 열었어요?",
  "파티 올 거예요?",
  "빵 좀 사러 가야겠다.",
];

/** 같은 시드면 같은 수열을 내는 작은 PRNG (mulberry32). */
export function createRng(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface MockState {
  spec: MockResidentSpec;
  tile: TilePoint;
  path: TilePoint[];
  destination: WalkPlace | null;
  waitTicks: number;
}

/** 내장 대체 마을의 통행 격자. 실제 맵을 못 읽었을 때 쓴다. */
export function fallbackWalkGrid(): WalkGrid {
  const grid = walkGridFromTiled(buildFallbackMap());
  if (grid === null) throw new Error("내장 대체 맵을 통행 격자로 읽지 못했다");
  return grid;
}

function lastSegment(path: string): string {
  return path.split(" > ").pop() ?? path;
}

export interface MockWorld {
  /** 첫 호출은 틱 0 스냅샷, 이후 호출마다 한 틱 진행한다. */
  next: () => WorldSnapshot;
}

/**
 * 결정론적 가짜 마을. 주민은 장소를 골라 통행 격자 위 최단 경로로 한 틱에 한 칸씩 걷고,
 * 도착하면 잠시 머문다. 벽·물·가구·나무 칸에는 들어가지 않는다.
 */
export function createMockWorld(
  seed: number = DEFAULT_MOCK_SEED,
  grid: WalkGrid = fallbackWalkGrid(),
  startHour: number = MOCK_START_HOUR,
): MockWorld {
  const rng = createRng(seed);
  const places = grid.places;
  if (places.length === 0) throw new Error("통행 격자에 목적지가 없다");
  const states: MockState[] = MOCK_RESIDENTS.map((spec, index) => ({
    spec,
    tile: { ...places[index % places.length].tile },
    path: [],
    destination: null,
    waitTicks: 0,
  }));
  let tick = -1;

  function chooseDestination(state: MockState): void {
    const choice = places[Math.floor(rng() * places.length)];
    const path = findPath(grid, state.tile, choice.tile);
    if (path === null || path.length === 0) {
      state.waitTicks = MOCK_STAY_TICKS.min;
      return;
    }
    state.destination = choice;
    state.path = path;
  }

  function advanceResident(state: MockState): ResidentSnapshot {
    const next = state.path.shift();
    if (next) {
      state.tile = next;
      if (state.path.length === 0) {
        const span = MOCK_STAY_TICKS.max - MOCK_STAY_TICKS.min;
        state.waitTicks = MOCK_STAY_TICKS.min + Math.floor(rng() * span);
      }
    } else if (state.waitTicks > 0) {
      state.waitTicks -= 1;
    } else {
      chooseDestination(state);
    }
    const speaks = rng() < MOCK_SPEAK_CHANCE;
    const line = MOCK_LINES[Math.floor(rng() * MOCK_LINES.length)];
    const here = locationAt(grid, state.tile.x, state.tile.y);
    const walking = state.path.length > 0 && state.destination !== null;
    return {
      resident_id: state.spec.id,
      display_name: state.spec.name,
      tile: { ...state.tile },
      location_path: here,
      action_description: walking
        ? `${lastSegment(state.destination?.location_path ?? here)} 쪽으로 걷는 중`
        : `${lastSegment(here)}에서 쉬는 중`,
      emoji: state.spec.emoji,
      utterance_text: speaks ? line : null,
      mind_kind: state.spec.mind,
      current_plan_item: null,
    };
  }

  return {
    next: () => {
      tick += 1;
      const residents = states.map((state) => advanceResident(state));
      const simTime = new Date(MOCK_START_TIME_MS + (startHour - MOCK_START_HOUR) * 3_600_000 + tick * MOCK_SIM_MINUTES_PER_TICK * 60_000);
      return { tick, sim_time: simTime.toISOString(), residents };
    },
  };
}
