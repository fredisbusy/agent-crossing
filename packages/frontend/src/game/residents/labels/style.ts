import Phaser from "phaser";

/** 이름표·말풍선 조각 그림을 화면에서 몇 배로 키울지(그림 1px = 화면 2px). */
export const ART_SCALE = 2;
/** 화면 기준 글자 최소 크기(px). 카메라 줌과 상관없이 이 크기로 읽혀야 한다. */
export const MIN_TEXT_PX = 10;
export const NAME_FONT_PX = MIN_TEXT_PX;
export const SPEECH_FONT_PX = 12;
/** 글자 캔버스 해상도 배율. 줌 역보정으로 화면 1:1에 놓으므로 2배 그려 선형 축소해 또렷하게 한다. */
export const TEXT_RESOLUTION = 2;
export const LABEL_FONT = '"Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", "Noto Sans CJK KR", system-ui, sans-serif';

/** 글자 캔버스를 선형 필터로 바꿔, 화면 1:1보다 크게 그린 글자가 부드럽게 줄어들게 한다. */
export function smoothTextTexture(text: Phaser.GameObjects.Text): void {
  const holder = text as unknown as { texture?: Phaser.Textures.Texture };
  holder.texture?.setFilter(Phaser.Textures.FilterMode.LINEAR);
}
