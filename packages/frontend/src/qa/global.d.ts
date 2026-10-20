/** QA 훅 전역 선언 (SPEC §15). 개발 빌드 또는 QA 빌드의 `?qa=1`에서만 설치된다. */

declare const __QA_HOOKS__: boolean;

interface Window {
  /** 현재 상태를 짧은 JSON 문자열로. */
  render_game_to_text?: () => string;
  /** 실시간 루프를 멈춘 채 고정 스텝으로 ms만큼 진행하고 한 번 그린다. */
  advanceTime?: (ms: number) => void;
}
