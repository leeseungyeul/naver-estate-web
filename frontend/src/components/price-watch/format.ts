/** 호가 추적 화면 공용 포맷 — 변동률 부호·색(상승=빨강, 하락=파랑: 국내 시세 관례) */

export function formatChangePct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return "—";
  if (pct === 0) return "0.00%";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

export function changeColor(v: number | null | undefined): string {
  if (!v) return "text-gray-600";
  return v > 0 ? "text-red-600" : "text-blue-600";
}

/** "2026-09-15" → "9.15" */
export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [, m, d] = iso.split("-");
  return `${Number(m)}.${Number(d)}`;
}

export function formatArea(area: number | null, pyeong: number | null): string {
  if (area === null) return "전체 평형";
  return `전용 ${area}㎡${pyeong ? ` (${pyeong}평)` : ""}`;
}
