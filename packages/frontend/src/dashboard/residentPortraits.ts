const RESIDENT_PORTRAITS: Readonly<Record<string, string>> = {
  byeongyong: "/portraits/byeongyong.png",
  haeun: "/portraits/haeun.png",
  jiho: "/portraits/jiho.png",
  jungwoo: "/portraits/jungwoo.png",
  minji: "/portraits/minji.png",
  sujin: "/portraits/sujin.png",
  taeo: "/portraits/taeo.png",
  wonjun: "/portraits/wonjun.png",
  woosik: "/portraits/woosik.png",
  yongjun: "/portraits/yongjun.png",
};

export function residentPortraitUrl(agentId: string): string | null {
  return RESIDENT_PORTRAITS[agentId.toLocaleLowerCase()] ?? null;
}
