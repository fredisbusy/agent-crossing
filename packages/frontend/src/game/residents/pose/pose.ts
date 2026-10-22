import type { ActionKind } from "./action-kind";
import type { Spot } from "./spots";

/** 아틀라스에 있는 주민 동작 애니(`villager_<벌>_<동작>_<방향>`, 자기는 방향 없음). */
export type PoseAct = "idle" | "walk" | "sit" | "work" | "talk" | "sleep";

export interface Pose {
  act: PoseAct;
  /** 의자가 정한 바라보는 방향. 없으면 지금 방향을 그대로 쓴다. */
  facing: "down" | "up" | "right" | null;
  /** 침대 위에서 자는 중이면 그 침대. */
  bed: Extract<Spot, { kind: "bed" }> | null;
}

/** 손을 움직이는 일을 하는 행동은 일하는 애니를 쓴다. */
const WORK_KINDS: ReadonlySet<ActionKind> = new Set(["work", "cook", "paint", "study", "garden"]);

export interface PoseInput {
  kind: ActionKind | null;
  moving: boolean;
  spot: Spot | null;
}

/**
 * 행동 종류·이동 여부·서 있는 자리에서 포즈를 고른다.
 * 걷는 중 → 걷기, 침대에서 자기 → 자기, 앉는 자리 → 앉기(의자 방향), 일 → 일하기, 대화 → 말하기, 그 외 서기.
 */
export function choosePose({ kind, moving, spot }: PoseInput): Pose {
  if (moving) return { act: "walk", facing: null, bed: null };
  if (spot?.kind === "bed" && kind === "sleep") return { act: "sleep", facing: null, bed: spot };
  if (spot?.kind === "seat") return { act: "sit", facing: spot.facing, bed: null };
  if (kind !== null && WORK_KINDS.has(kind)) return { act: "work", facing: null, bed: null };
  if (kind === "talk") return { act: "talk", facing: null, bed: null };
  return { act: "idle", facing: null, bed: null };
}
