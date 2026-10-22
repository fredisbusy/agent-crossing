import { walkGridFromTiled, type WalkGrid } from "../town-layout";

/** 화면이 그리는 것과 같은 `town.json`(vite publicDir)을 읽어 통행 격자로 만든다. 실패하면 null. */
export async function loadTownWalkGrid(url: string = "town.json"): Promise<WalkGrid | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    return walkGridFromTiled(await response.json());
  } catch {
    return null;
  }
}
