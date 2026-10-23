/** 머리 위 아이콘 이름이자 행동 종류(아틀라스 `act_<종류>`). */
export const ACTION_KINDS = [
  "sleep",
  "eat",
  "cook",
  "coffee",
  "work",
  "study",
  "read",
  "paint",
  "talk",
  "walk",
  "shop",
  "drink",
  "music",
  "garden",
  "think",
  "rest",
] as const;
export type ActionKind = (typeof ACTION_KINDS)[number];

type Rule = readonly [ActionKind, RegExp];

/**
 * 행동 문구 키워드(영어·한국어). 위에서부터 먼저 맞는 것을 고른다.
 * 구체적인 행동이 앞, 두루뭉술한 `walk`·`rest`는 이모지 뒤(`GENERIC_TEXT_RULES`)에 둔다.
 */
const SPECIFIC_TEXT_RULES: readonly Rule[] = [
  ["sleep", /sleep|\bnap(?:ping|s)?\b|asleep|bedtime|잠들|잠자|잠을|자는|자고|취침|수면|낮잠|꿈나라/i],
  ["cook", /cook|bak(?:e|ing)|kitchen|요리|조리|굽는|끓이|부엌|주방/i],
  ["paint", /paint|draw|sketch|easel|그림|그리는|그리고|스케치|화가|물감/i],
  ["study", /study|class|homework|lesson|learn|school|공부|수업|숙제|학습|배우|시험/i],
  ["read", /read|book|library|독서|읽는|읽고|책을|책 |도서/i],
  ["coffee", /coffee|latte|espresso|cafe|café|커피|라떼|에스프레소|카페/i],
  ["drink", /beer|wine|drink|pub|cheers|tavern|술|맥주|와인|한잔|건배|마시는|마시고/i],
  ["eat", /\beat|meal|lunch|dinner|breakfast|snack|bread|pastry|식사|먹는|먹고|점심|저녁|아침|간식|빵/i],
  ["shop", /shop|buy|market|store|purchas|쇼핑|장을|장보|사러|사는|구매|시장|상점/i],
  ["music", /music|sing|guitar|piano|song|concert|음악|노래|연주|기타|피아노|공연/i],
  ["garden", /garden|plant(?:ing)?|water(?:ing)?|flower|farm|정원|화단|꽃|식물|물을 주|가꾸|텃밭|농사/i],
  ["work", /work|desk|office|typ(?:e|ing)|writ(?:e|ing)|repair|fix|build|업무|일하|일을|작업|근무|사무|글을|수리|정리/i],
  ["think", /think|ponder|wonder|plan|생각|고민|궁리|계획/i],
  ["talk", /talk|chat|convers|discuss|대화|이야기|수다|얘기|말을 걸|잡담/i],
];

const GENERIC_TEXT_RULES: readonly Rule[] = [
  ["walk", /walk|stroll|head(?:ing)? (?:to|toward)|걷는|걷고|산책|이동|가는 중|향해|쪽으로/i],
  ["rest", /rest|relax|idle|chill|\bsit|쉬는|쉬고|휴식|앉아|멍/i],
];

const EMOJI_RULES: readonly Rule[] = [
  ["sleep", /😴|💤|🛌|🛏/u],
  ["cook", /🍳|🥘|🔥|🍲/u],
  ["coffee", /☕|🍵/u],
  ["drink", /🍺|🍻|🍷|🥂|🍸|🍹/u],
  ["eat", /🍽|🍴|🍞|🥐|🍰|🍪|🍎|🥪|🍜|🍚/u],
  ["paint", /🎨|🖌|🖼/u],
  ["study", /📚|✏|📝|🎓|🎒/u],
  ["read", /📖|📕|📗|📘/u],
  ["work", /💻|💼|🔧|🔨|⚒|🖥|📊/u],
  ["music", /🎵|🎶|🎸|🎹|🎤|🎻/u],
  ["garden", /🌱|🌻|🌿|🪴|🌷|🌸|🌳|🚿|💧/u],
  ["shop", /🛒|🛍|💰|🏪/u],
  ["think", /🤔|💭|❓/u],
  ["talk", /💬|🗣|🗨/u],
  ["walk", /🚶|🏃|👣/u],
  ["rest", /🛋|😌|🧘/u],
];

function firstMatch(rules: readonly Rule[], text: string): ActionKind | null {
  for (const [kind, pattern] of rules) if (pattern.test(text)) return kind;
  return null;
}

export interface ActionInput {
  action_description: string | null;
  emoji: string | null;
  /** 지금 말풍선이 떠 있다(말하는 중). */
  talking: boolean;
  /** 화면에서 실제로 걷고 있다. */
  moving: boolean;
}

/**
 * 행동 문구·이모지·상태로 행동 종류를 고른다. 걷는 중이 가장 우선, 그다음 말하는 중.
 * 문구의 구체적 키워드 → 이모지 → 두루뭉술한 문구(걷기·쉬기) 순이다. 아무것도 안 맞으면 null.
 */
export function classifyAction(input: ActionInput): ActionKind | null {
  if (input.moving) return "walk";
  if (input.talking) return "talk";
  return classifyText(input.action_description ?? "", input.emoji ?? "");
}

/** 정규식 수십 개를 프레임마다 돌리지 않도록 (문구, 이모지)별 결과를 기억한다. */
const TEXT_CACHE_LIMIT = 512;
const textCache = new Map<string, ActionKind | null>();

function classifyText(text: string, emoji: string): ActionKind | null {
  const key = `${text}\u0000${emoji}`;
  const cached = textCache.get(key);
  if (cached !== undefined) return cached;
  const kind = firstMatch(SPECIFIC_TEXT_RULES, text) ?? firstMatch(EMOJI_RULES, emoji) ?? firstMatch(GENERIC_TEXT_RULES, text);
  if (textCache.size >= TEXT_CACHE_LIMIT) textCache.clear();
  textCache.set(key, kind);
  return kind;
}
