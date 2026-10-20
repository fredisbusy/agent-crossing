import Phaser from "phaser";
import { TownScene, type SceneCameraState } from "./scenes/town-scene";

/** React가 장면 내부를 몰라도 되도록 노출하는 최소 제어 면. */
export interface TownGameHandle {
  getCameraState: () => SceneCameraState;
  getBubbleText: (residentId: string) => string | null;
  /** 실시간 루프를 멈추고 시계를 수동으로 전환한다. */
  freezeRealtime: () => void;
  /** 수동 시계를 ms만큼 진행한다(그리지 않는다). */
  advanceClock: (ms: number) => void;
  /** 한 프레임을 그린다. */
  render: () => void;
  destroy: () => void;
}

export function createTownGame(parent: HTMLElement): TownGameHandle {
  const scene = new TownScene();
  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent,
    backgroundColor: "#3f6b46",
    pixelArt: true,
    scale: { mode: Phaser.Scale.RESIZE, width: "100%", height: "100%" },
    scene: [scene],
  });

  return {
    getCameraState: () => scene.getCameraState(),
    getBubbleText: (id) => scene.getBubbleText(id),
    freezeRealtime: () => {
      scene.useManualClock();
      game.loop.sleep();
    },
    advanceClock: (ms) => scene.advanceClock(ms),
    render: () => game.step(performance.now(), 0),
    destroy: () => game.destroy(true),
  };
}
