const RESIDENT_PORTRAITS: Readonly<Record<string, string>> = {
  haeun: "/portraits/haeun.png",
  jiho: "/portraits/jiho.png",
  jungwoo: "/portraits/jungwoo.png",
  minji: "/portraits/minji.png",
  sujin: "/portraits/sujin.png",
  taeo: "/portraits/taeo.png",
};

export function residentPortraitUrl(agentId: string): string | null {
  return RESIDENT_PORTRAITS[agentId.toLocaleLowerCase()] ?? null;
}
