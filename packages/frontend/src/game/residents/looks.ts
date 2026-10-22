/** stardewrogue `people.ts`의 `LOOKS` 키 10벌(a..j). 주민 id 해시로 한 벌을 고른다. */
export const VILLAGER_LOOKS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"] as const;
/** id에서 항상 같은 한 벌(a..j)을 고른다. */
export function villagerLookFor(id: string): string {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return VILLAGER_LOOKS[hash % VILLAGER_LOOKS.length];
}
