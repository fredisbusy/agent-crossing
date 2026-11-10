import type { ResidentSnapshot } from "@agent-crossing/shared";
import { MOCK_SIM_MINUTES_PER_TICK, MOCK_START_HOUR, MOCK_START_TIME_MS, type MockWorld } from "./mock-world";

interface PoseSpec {
  id: string;
  name: string;
  x: number;
  y: number;
  action: string;
  emoji: string;
  line?: string;
}

/**
 * `?mock=1&scenario=poses`: 실제 마을 가구(`packages/shared/maps/town.json`) 위에 주민을 고정해
 * 행동별 표현(앉기·자기·대화·아이콘)을 한 화면에서 확인하는 검증용 시나리오. 아무도 움직이지 않는다.
 */
const POSE_SPECS: readonly PoseSpec[] = [
  { id: "isabella", name: "Isabella", x: 8, y: 6, action: "drinking coffee at the cafe", emoji: "☕" },
  { id: "klaus", name: "Klaus", x: 9, y: 6, action: "talking with Isabella", emoji: "💬", line: "오늘 밸런타인 파티 올 거야?" },
  { id: "maria", name: "Maria", x: 36, y: 19, action: "sleeping", emoji: "😴" },
  { id: "sam", name: "Sam", x: 54, y: 21, action: "cooking breakfast", emoji: "🍳" },
  { id: "jen", name: "Jennifer", x: 47, y: 23, action: "painting at the easel", emoji: "🎨" },
  { id: "tom", name: "Tom", x: 38, y: 10, action: "drinking beer at the pub", emoji: "🍺" },
  { id: "eddy", name: "Eddy", x: 49, y: 4, action: "studying for class", emoji: "📚" },
  { id: "carmen", name: "Carmen", x: 2, y: 22, action: "resting on the sofa", emoji: "🛋" },
  { id: "john", name: "John", x: 21, y: 8, action: "shopping for groceries", emoji: "🛒" },
  { id: "ayesha", name: "Ayesha", x: 31, y: 26, action: "thinking about the essay", emoji: "🤔" },
  { id: "wen", name: "Wen", x: 8, y: 22, action: "sleeping", emoji: "😴" },
  { id: "abigail", name: "Abigail", x: 3, y: 5, action: "working at the counter", emoji: "💻" },
];

export function createPosesWorld(startHour: number = MOCK_START_HOUR): MockWorld {
  let tick = -1;
  const residents: ResidentSnapshot[] = POSE_SPECS.map((spec) => ({
    resident_id: spec.id,
    display_name: spec.name,
    tile: { x: spec.x, y: spec.y },
    location_path: "Smallville",
    action_description: spec.action,
    emoji: spec.emoji,
    utterance_text: spec.line ?? null,
    mind_kind: "llm",
    current_plan_item: null,
  }));
  return {
    next: () => {
      tick += 1;
      const offsetMs = (startHour - MOCK_START_HOUR) * 3_600_000 + tick * MOCK_SIM_MINUTES_PER_TICK * 60_000;
      return { tick, sim_time: new Date(MOCK_START_TIME_MS + offsetMs).toISOString(), residents };
    },
  };
}
