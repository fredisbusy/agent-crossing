/** 벽 겉면 재질. `wall` 계열 위벽 프레임(place-style.ts)과 어울리게 고른다. */
export type FacadeMaterial = "log" | "plank" | "brick" | "plaster";

/** 창 모양: 집은 덧문 창, 가게는 차양 진열창, 술집은 작은 창과 등불, 학교는 높은 아치 창. */
export type FacadeKind = "house" | "shop" | "pub" | "civic";

export interface FacadeStyle {
  material: FacadeMaterial;
  kind: FacadeKind;
  /** 벽 바탕색(재질 무늬는 이 색의 밝고 어두운 단계로 그린다). */
  wall: string;
  /** 처마(지붕 끝) 색. */
  roof: string;
  /** 모서리 기둥·창틀 색. */
  trim: string;
  /** 집 덧문 색. 없으면 덧문을 달지 않는다. */
  shutter: string | null;
  /** 가게 차양 줄무늬 두 색. 없으면 차양을 달지 않는다. */
  awning: readonly [string, string] | null;
  /** 창 아래 꽃상자. */
  flowerBox: boolean;
}

const HOUSE_TRIM = "#f4ead2";
const DARK_TRIM = "#5a3a24";

/** 건물 이름(location_path 2단계) → 정면 모양. 집마다 지붕·벽·덧문 색을 달리해 줄지은 상자로 보이지 않게 한다. */
export const FACADE_STYLES: Readonly<Record<string, FacadeStyle>> = {
  "Hobbs Cafe": {
    material: "plaster", kind: "shop", wall: "#f1dfb8", roof: "#c0573a", trim: DARK_TRIM,
    shutter: null, awning: ["#d8473b", "#fbf1dc"], flowerBox: true,
  },
  "The Willows Market": {
    material: "plank", kind: "shop", wall: "#7fa0b0", roof: "#56677a", trim: HOUSE_TRIM,
    shutter: null, awning: ["#3f8a4a", "#fbf1dc"], flowerBox: false,
  },
  "The Rose and Crown Pub": {
    material: "brick", kind: "pub", wall: "#8a3f35", roof: "#3f5e3a", trim: DARK_TRIM,
    shutter: null, awning: null, flowerBox: false,
  },
  "Oak Hill College": {
    material: "brick", kind: "civic", wall: "#b0574a", roof: "#4a5a78", trim: HOUSE_TRIM,
    shutter: null, awning: null, flowerBox: false,
  },
  "Moore Family House": {
    material: "log", kind: "house", wall: "#9c6a3e", roof: "#b34a3a", trim: DARK_TRIM,
    shutter: "#4f8a3c", awning: null, flowerBox: true,
  },
  "Isabella's Apartment": {
    material: "plaster", kind: "house", wall: "#efd9c4", roof: "#3e7f7a", trim: HOUSE_TRIM,
    shutter: "#4a78a8", awning: null, flowerBox: true,
  },
  "Dorm for Oak Hill College": {
    material: "brick", kind: "house", wall: "#a65a44", roof: "#556070", trim: HOUSE_TRIM,
    shutter: null, awning: null, flowerBox: false,
  },
  "Artist's Co-living Space": {
    material: "plank", kind: "house", wall: "#d9a441", roof: "#7a4f7e", trim: HOUSE_TRIM,
    shutter: "#3f8a86", awning: null, flowerBox: true,
  },
  "Lin Family House": {
    material: "plank", kind: "house", wall: "#e3d6bf", roof: "#8c4b2f", trim: DARK_TRIM,
    shutter: "#b8453a", awning: null, flowerBox: true,
  },
};

/** 표에 없는 건물은 수수한 나무집. */
export const DEFAULT_FACADE_STYLE: FacadeStyle = {
  material: "plank", kind: "house", wall: "#b07a4a", roof: "#8c4b2f", trim: DARK_TRIM,
  shutter: null, awning: null, flowerBox: false,
};
