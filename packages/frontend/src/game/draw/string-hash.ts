/** 문자열에서 항상 같은 부호 없는 정수를 만든다(주민 id로 몸 색·옷 한 벌을 고를 때 쓴다). */
export function stringHash(text: string): number {
  let hash = 0;
  for (const char of text) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash;
}
