/** stardewrogue `src/gfx/autotile.ts`의 `cellHash`와 같은 값(0..99). */
export function cellHash(x: number, y: number): number {
  return (((x * 73856093) ^ (y * 19349663)) >>> 0) % 100;
}

/** stardewrogue `src/gfx/autotile.ts`의 `variantHash`와 같은 값. */
export function variantHash(x: number, y: number): number {
  let h = Math.imul((x * 73856093) ^ (y * 19349663), 0x5bd1e995) >>> 0;
  h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d) >>> 0;
  return h;
}
