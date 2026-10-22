import type Phaser from "phaser";
import { BIRD_ORIGIN, birdPose, BUTTERFLY_ORIGIN, butterflyPose, type CritterPlan } from "./critters";
import type { ObjectSprite } from "./object-plan";
import {
  clampSignCenter,
  ICON_TOP_OFFSET,
  layoutSign,
  PLANK_CELL,
  PLANK_END_WIDTH,
  PLANK_HEIGHT,
  PLANK_MIDDLE_WIDTH,
  PLANK_TOP_OFFSET,
  type SignPlan,
} from "./signs";

const ATLAS_KEY = "pixel-kit";
/** Phaser `Scenes.Events`와 같은 문자열(런타임 import를 피해 순수 테스트가 Phaser를 읽지 않게 한다). */
const UPDATE_EVENT = "update";
const SHUTDOWN_EVENT = "shutdown";
/** 화면 기준 글자 크기(px). 주민 이름표(`residents/labels/style.ts`)와 같은 11px. */
const SIGN_FONT_PX = 11;
const SIGN_FONT = '"Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", "Noto Sans CJK KR", system-ui, sans-serif';
/** 판자 그림 1px = 화면 2px (이름표와 같은 배율). */
const SIGN_ART_SCALE = 2;
/** 화면 1:1로 놓으므로 2배 그려 선형 축소한다(`Phaser.Textures.FilterMode.LINEAR` = 0). */
const SIGN_TEXT_RESOLUTION = 2;
const SIGN_TEXT_FILTER_LINEAR = 0;
/** 간판은 나무·가구·주민과 밤 틴트(90000)보다 위(밤에도 읽히게), 디버그(100000)보다 아래. */
const SIGN_DEPTH = 90_500;
const SIGN_TEXT_COLOR = "#fff4d6";
/** 판자 그림 세로 가운데가 프레임 위에서 떨어진 px. */
const PLANK_CENTER_OFFSET = PLANK_TOP_OFFSET + 6;
const FLY_DEPTH_LIFT = 64;
const ANIM_FRAME_RATE = 6;
const ANIM_FRAMES: Readonly<Record<string, readonly string[]>> = {
  fountain: ["fountain_0", "fountain_1", "fountain_2"],
};

type Tick = (timeMs: number) => void;

/** 간판 판자가 지금 차지하는 월드 사각형(화면 고정 크기라 줌마다 달라진다). 주민 이름표가 비킨다. */
export interface SignRect {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** 애니 스프라이트는 프레임을 직접 바꾼다: Phaser 애니는 프레임을 바꿀 때마다 아틀라스 pivot으로 origin을 되돌린다. */
function drawSprites(scene: Phaser.Scene, sprites: readonly ObjectSprite[], ticks: Tick[]): void {
  for (const sprite of sprites) {
    const image = scene.add.image(sprite.x, sprite.y, ATLAS_KEY, sprite.frame).setOrigin(0, 0).setDepth(sprite.depth);
    const frames = sprite.anim ? ANIM_FRAMES[sprite.anim] : undefined;
    if (!frames) continue;
    ticks.push((time) => {
      image.setFrame(frames[Math.floor((time * ANIM_FRAME_RATE) / 1000) % frames.length], false, false);
    });
  }
}

/** 판자+아이콘+글자를 한 덩어리로 묶어 화면 크기를 고정한다(컨테이너를 1/줌으로 스케일). */
function drawSign(scene: Phaser.Scene, sign: SignPlan, ticks: Tick[]): () => SignRect {
  const text = scene.add
    .text(0, 0, sign.label, {
      fontFamily: SIGN_FONT,
      fontSize: `${SIGN_FONT_PX}px`,
      fontStyle: "bold",
      color: SIGN_TEXT_COLOR,
      resolution: SIGN_TEXT_RESOLUTION,
    })
    .setOrigin(0, 0.5);
  text.texture.setFilter(SIGN_TEXT_FILTER_LINEAR);
  // 판자 그림은 화면에서 SIGN_ART_SCALE배로 보이므로 글자 폭을 그림 px로 환산해 3-patch를 늘린다.
  const layout = layoutSign(text.width / SIGN_ART_SCALE);
  const s = SIGN_ART_SCALE;
  const left = -(layout.width * s) / 2;
  // 아래로 걸 때는 판자 그림 위끝(프레임 위에서 PLANK_TOP_OFFSET 아래)이 가장자리에 오게 내린다.
  const frameTop = sign.below ? -PLANK_TOP_OFFSET * s : -PLANK_CELL * s;
  const piece = (frame: string, x: number, y = frameTop): Phaser.GameObjects.Image =>
    scene.add.image(x, y, ATLAS_KEY, frame).setOrigin(0, 0).setScale(s);
  const children: Phaser.GameObjects.GameObject[] = [piece("sign_plank_l", left)];
  for (let i = 0; i < layout.middleCount; i += 1) {
    children.push(piece("sign_plank_m", left + (PLANK_END_WIDTH + i * PLANK_MIDDLE_WIDTH) * s));
  }
  children.push(piece("sign_plank_r", left + (layout.width - PLANK_END_WIDTH) * s));
  children.push(piece(sign.icon, left + layout.iconX * s, frameTop + (PLANK_TOP_OFFSET - ICON_TOP_OFFSET + 1) * s));
  text.setPosition(left + layout.textX * s, frameTop + PLANK_CENTER_OFFSET * s);
  children.push(text);
  const container = scene.add.container(sign.centerX, sign.edgeY, children).setDepth(SIGN_DEPTH);
  let rect: SignRect = { left: sign.centerX, right: sign.centerX, top: sign.edgeY, bottom: sign.edgeY };
  ticks.push(() => {
    const zoomScale = 1 / scene.cameras.main.zoom;
    const scale = sign.maxScale === null ? zoomScale : Math.min(zoomScale, sign.maxScale);
    const width = layout.width * s * scale;
    container.setScale(scale);
    container.x = clampSignCenter(sign.centerX, width, sign.bounds);
    // 판자 그림은 프레임(16px) 아래쪽 12px만 차 있다.
    const plankTop = sign.edgeY + (frameTop + PLANK_TOP_OFFSET * s) * scale;
    rect = { left: container.x - width / 2, right: container.x + width / 2, top: plankTop, bottom: plankTop + PLANK_HEIGHT * s * scale };
  });
  return () => rect;
}

function drawCritters(scene: Phaser.Scene, critters: CritterPlan, ticks: Tick[]): void {
  const birds = critters.birds.map((bird) => ({
    bird,
    image: scene.add
      .image(bird.x, bird.y, ATLAS_KEY, "bird_idle_0")
      .setOrigin(BIRD_ORIGIN.x, BIRD_ORIGIN.y)
      .setDepth(bird.y),
  }));
  const butterflies = critters.butterflies.map((butterfly) => ({
    butterfly,
    image: scene.add
      .image(butterfly.x, butterfly.y, ATLAS_KEY, "butterfly_0")
      .setOrigin(BUTTERFLY_ORIGIN.x, BUTTERFLY_ORIGIN.y)
      .setDepth(butterfly.y + FLY_DEPTH_LIFT),
  }));
  // 장면 시간(`time`, ms)만 쓴다: 같은 시각이면 같은 모습.
  ticks.push((time) => {
    for (const { bird, image } of birds) {
      const pose = birdPose(bird.seed, time);
      image.setFrame(pose.frame, false, false).setFlipX(pose.flipX);
    }
    for (const { butterfly, image } of butterflies) {
      const pose = butterflyPose(butterfly.seed, time);
      image.setFrame(pose.frame, false, false).setPosition(butterfly.x + pose.dx, butterfly.y + pose.dy);
      image.setFlipX(Math.sin(time * 0.0006 + butterfly.seed) > 0);
    }
  });
}

/**
 * 가구·장식·간판·작은 생물을 장면에 얹는다. 바닥 캔버스는 `drawPixelKit`이 따로 굽는다.
 * 돌려주는 함수는 간판들이 지금 차지하는 사각형(이름표 비키기용)이다.
 */
export function drawPixelKitObjects(
  scene: Phaser.Scene,
  plan: { sprites: readonly ObjectSprite[]; signs: readonly SignPlan[]; critters: CritterPlan },
): () => SignRect[] {
  const ticks: Tick[] = [];
  drawSprites(scene, plan.sprites, ticks);
  const signRects = plan.signs.map((sign) => drawSign(scene, sign, ticks));
  drawCritters(scene, plan.critters, ticks);
  const currentSignRects = (): SignRect[] => signRects.map((rect) => rect());
  if (ticks.length === 0) return currentSignRects;
  const onUpdate = (time: number): void => {
    for (const tick of ticks) tick(time);
  };
  scene.events.on(UPDATE_EVENT, onUpdate);
  scene.events.once(SHUTDOWN_EVENT, () => scene.events.off(UPDATE_EVENT, onUpdate));
  return currentSignRects;
}
