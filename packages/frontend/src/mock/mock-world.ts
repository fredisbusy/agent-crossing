import type { MindKind, ResidentSnapshot, WorldSnapshot } from "@agent-crossing/shared";
import {
  CAFE_DOOR,
  locationPathAt,
  type TilePoint,
} from "../town-layout";

/** 시뮬레이션 시각이 틱마다 흐르는 분(가짜 피드 전용). */
export const MOCK_SIM_MINUTES_PER_TICK = 1;
export const MOCK_START_TIME_MS = Date.UTC(2023, 1, 13, 7, 0, 0);
/** 한 틱에 주민이 말할 확률. */
export const MOCK_SPEAK_CHANCE = 0.08;

export const DEFAULT_MOCK_SEED = 20230213;

interface MockResidentSpec {
  id: string;
  name: string;
  mind: MindKind;
  emoji: string;
  /** 닫힌 경로. 이어진 두 점(마지막 -> 처음 포함)은 같은 행 또는 열이다. */
  route: readonly TilePoint[];
}

const MOCK_RESIDENTS: readonly MockResidentSpec[] = [
  { id: "mochi", name: "Mochi", mind: "llm", emoji: "☕", route: [{ x: 3, y: 14 }, { x: 36, y: 14 }] },
  { id: "biscuit", name: "Biscuit", mind: "schedule", emoji: "🎒", route: [{ x: 19, y: 4 }, { x: 19, y: 24 }] },
  {
    id: "olive",
    name: "Olive",
    mind: "schedule",
    emoji: "🚶",
    route: [{ x: 9, y: 13 }, { x: 9, y: 14 }, { x: 20, y: 14 }, { x: 20, y: 20 }, { x: 20, y: 14 }, { x: 9, y: 14 }],
  },
  {
    id: "pip",
    name: "Pip",
    mind: "schedule",
    emoji: "🛒",
    route: [{ x: 27, y: 17 }, { x: 27, y: 14 }, { x: 31, y: 14 }, { x: 27, y: 14 }],
  },
];

const MOCK_LINES: readonly string[] = [
  "Good morning!",
  "Lovely weather today.",
  "Is the cafe open yet?",
  "Are you coming to the party?",
  "I need to grab some bread.",
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
  target: number;
}

function stepToward(from: TilePoint, to: TilePoint): TilePoint {
  if (from.x !== to.x) return { x: from.x + Math.sign(to.x - from.x), y: from.y };
  return { x: from.x, y: from.y + Math.sign(to.y - from.y) };
}

export interface MockWorld {
  /** 첫 호출은 틱 0 스냅샷, 이후 호출마다 한 틱 진행한다. */
  next: () => WorldSnapshot;
}

export function createMockWorld(seed: number = DEFAULT_MOCK_SEED): MockWorld {
  const rng = createRng(seed);
  const states: MockState[] = MOCK_RESIDENTS.map((spec) => ({ spec, tile: { ...spec.route[0] }, target: 1 }));
  let tick = -1;

  function advanceResident(state: MockState): ResidentSnapshot {
    const { route } = state.spec;
    const goal = route[state.target % route.length];
    if (state.tile.x === goal.x && state.tile.y === goal.y) {
      state.target = (state.target + 1) % route.length;
    } else {
      state.tile = stepToward(state.tile, goal);
    }
    const speaks = rng() < MOCK_SPEAK_CHANCE;
    const line = MOCK_LINES[Math.floor(rng() * MOCK_LINES.length)];
    const nearCafe = state.tile.x === CAFE_DOOR.x && state.tile.y > CAFE_DOOR.y;
    return {
      resident_id: state.spec.id,
      display_name: state.spec.name,
      tile: { ...state.tile },
      location_path: locationPathAt(state.tile.x, state.tile.y),
      action_description: nearCafe ? "heading into the cafe" : "walking along the road",
      emoji: state.spec.emoji,
      utterance_text: speaks ? line : null,
      mind_kind: state.spec.mind,
    };
  }

  return {
    next: () => {
      tick += 1;
      const residents = states.map((state) => advanceResident(state));
      const simTime = new Date(MOCK_START_TIME_MS + tick * MOCK_SIM_MINUTES_PER_TICK * 60_000);
      return { tick, sim_time: simTime.toISOString(), residents };
    },
  };
}
