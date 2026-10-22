/** 시뮬레이션 시각 -> 낮밤 틴트. Phaser를 모르는 순수 함수만 둔다. */

export interface DaylightTint {
  /** MULTIPLY 오버레이의 기준 색(0xRRGGBB). */
  color: number;
  /** 0이면 효과 없음, 1이면 기준 색 그대로 곱한다. */
  alpha: number;
  /** 빛(가로등·창)이 얼마나 켜질지. 0(낮)~1(한밤). */
  darkness: number;
}

interface Keyframe {
  hour: number;
  color: number;
  alpha: number;
}

export const NIGHT_COLOR = 0x1c2c5e;
export const NIGHT_ALPHA = 0.78;
export const DAWN_COLOR = 0xffc6d6;
export const DAWN_ALPHA = 0.4;
export const DUSK_COLOR = 0xff9a4a;
export const DUSK_ALPHA = 0.5;
const CLEAR_COLOR = 0xffffff;

/** 하루를 도는 키프레임. 시(0~24)가 오름차순이고 처음과 끝이 같은 밤이다. */
export const DAYLIGHT_KEYFRAMES: readonly Keyframe[] = [
  { hour: 0, color: NIGHT_COLOR, alpha: NIGHT_ALPHA },
  { hour: 5, color: NIGHT_COLOR, alpha: NIGHT_ALPHA }, // 새벽 시작
  { hour: 6, color: DAWN_COLOR, alpha: DAWN_ALPHA },
  { hour: 7, color: CLEAR_COLOR, alpha: 0 }, // 낮 시작
  { hour: 17, color: CLEAR_COLOR, alpha: 0 }, // 저녁 시작
  { hour: 18, color: DUSK_COLOR, alpha: DUSK_ALPHA },
  { hour: 19, color: NIGHT_COLOR, alpha: NIGHT_ALPHA }, // 밤 시작
  { hour: 24, color: NIGHT_COLOR, alpha: NIGHT_ALPHA },
];

/** ISO 문자열의 시각 부분을 소수 시(0~24)로. 시간대 변환 없이 적힌 그대로 읽는다. */
export function simHourOf(iso: string): number | null {
  const match = /T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(iso);
  if (!match) return null;
  const hour = Number(match[1]) + Number(match[2]) / 60 + Number(match[3] ?? 0) / 3600;
  return hour >= 0 && hour < 24 ? hour : null;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpColor(a: number, b: number, t: number): number {
  const channel = (shift: number) => Math.round(lerp((a >> shift) & 0xff, (b >> shift) & 0xff, t));
  return (channel(16) << 16) | (channel(8) << 8) | channel(0);
}

/** 시(0~24)에 해당하는 틴트. 키프레임 사이는 선형 보간한다. */
export function daylightAt(hour: number): DaylightTint {
  const h = ((hour % 24) + 24) % 24;
  let next = DAYLIGHT_KEYFRAMES.findIndex((frame) => frame.hour > h);
  if (next < 1) next = DAYLIGHT_KEYFRAMES.length - 1;
  const from = DAYLIGHT_KEYFRAMES[next - 1];
  const to = DAYLIGHT_KEYFRAMES[next];
  const t = (h - from.hour) / (to.hour - from.hour);
  const alpha = lerp(from.alpha, to.alpha, t);
  // 효과 없는(알파 0) 쪽과 섞일 때 흰색이 번지지 않게, 알파가 있는 쪽 색을 쓴다.
  const color = from.alpha === 0 ? to.color : to.alpha === 0 ? from.color : lerpColor(from.color, to.color, t);
  return { color, alpha, darkness: Math.min(1, alpha / NIGHT_ALPHA) };
}

/** `sim_time`(ISO)에서 바로 틴트를. 읽지 못하면 낮으로 본다. */
export function daylightForSimTime(iso: string): DaylightTint {
  const hour = simHourOf(iso);
  return hour === null ? { color: CLEAR_COLOR, alpha: 0, darkness: 0 } : daylightAt(hour);
}

/** 흰색과 `color`를 `alpha`만큼 섞은, 알파 1로 곱할 때의 실제 색. */
export function multiplyColorOf(tint: DaylightTint): number {
  return lerpColor(CLEAR_COLOR, tint.color, tint.alpha);
}

/** 달(밤)을 보여줄 시각인지. 헤더 표시용. */
export function isNightHour(hour: number): boolean {
  return hour >= 19 || hour < 5;
}
