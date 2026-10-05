/** 단지 비교 우위 판정 유틸 — 순수 함수, 테스트 가능 */
import type { Complex, PriceStats } from "@/types";
import { M2_TO_PYEONG } from "@/lib/constants";

export type Direction = "higher" | "lower";

export interface CompareRowMeta {
  label: string;
  getValue: (c: Complex) => number | null;
  direction: Direction;
}

/** 준공일(YYYYMMDD or YYYYMM) → 숫자 변환 (큰 값 = 최신) */
export function parseApprovalDate(ymd?: string): number | null {
  if (!ymd) return null;
  const n = parseInt(ymd, 10);
  return isNaN(n) ? null : n;
}

/** 숫자 비교 가능한 행에만 우위 적용 (주소, 시공사 등 텍스트는 제외) */
export const ADVANTAGE_ROWS: CompareRowMeta[] = [
  { label: "세대수", getValue: (c) => c.total_household_count ?? null, direction: "higher" },
  { label: "동수", getValue: (c) => c.total_dong_count ?? null, direction: "higher" },
  { label: "최고층", getValue: (c) => c.high_floor ?? null, direction: "higher" },
  { label: "최저층", getValue: (c) => c.low_floor ?? null, direction: "higher" },
  { label: "준공일", getValue: (c) => parseApprovalDate(c.use_approve_ymd), direction: "higher" },
  { label: "최대 면적", getValue: (c) => c.max_supply_area_m2 ?? null, direction: "higher" },
  { label: "총 주차", getValue: (c) => c.total_parking_count ?? null, direction: "higher" },
  { label: "세대당 주차", getValue: (c) => c.parking_count_by_household ?? null, direction: "higher" },
  { label: "용적률", getValue: (c) => parseFloat(c.floor_area_ratio || "") || null, direction: "lower" },
  { label: "건폐율", getValue: (c) => parseFloat(c.building_coverage_ratio || "") || null, direction: "lower" },
  { label: "매물수", getValue: (c) => c.article_count ?? null, direction: "higher" },
  { label: "주변 중위가", getValue: (c) => c.nearby_median_price ?? null, direction: "higher" },
  { label: "전세가율", getValue: (c) => c.jeonse_rate ?? null, direction: "higher" },
];

/**
 * 우위 인덱스 반환
 * - direction="higher" → 최대값 인덱스
 * - direction="lower" → 최소값 인덱스
 * - 동점 시 모두 반환, 유효 값 없으면 빈 배열
 */
export function getBestIndices(
  values: (number | null)[],
  direction: Direction,
): number[] {
  const valid = values.map((v, i) => ({ v, i })).filter((x) => x.v != null) as {
    v: number;
    i: number;
  }[];
  if (valid.length === 0) return [];

  const best =
    direction === "higher"
      ? Math.max(...valid.map((x) => x.v))
      : Math.min(...valid.map((x) => x.v));

  return valid.filter((x) => x.v === best).map((x) => x.i);
}

/** PriceStats의 by_area에서 가중 평균 평당가 계산 (만원/평) */
export function calcAvgPricePerPyeong(stats: PriceStats): number | null {
  let sumPrice = 0;
  let sumCount = 0;
  for (const a of stats.by_area) {
    if (a.maemae != null && a.maemae_count && a.maemae_count > 0) {
      const m2 = parseFloat(a.label); // "85m²" → 85
      if (isNaN(m2) || m2 <= 0) continue;
      const pyeong = m2 / M2_TO_PYEONG;
      sumPrice += (a.maemae / pyeong) * a.maemae_count;
      sumCount += a.maemae_count;
    }
  }
  return sumCount > 0 ? Math.round(sumPrice / sumCount) : null;
}

/**
 * 특정 라벨의 ADVANTAGE_ROWS에서 우위 인덱스를 계산
 * - 라벨이 ADVANTAGE_ROWS에 없으면 빈 배열 반환
 */
export function getAdvantageForRow(
  label: string,
  complexes: Complex[],
): number[] {
  const meta = ADVANTAGE_ROWS.find((r) => r.label === label);
  if (!meta) return [];
  const values = complexes.map((c) => meta.getValue(c));
  return getBestIndices(values, meta.direction);
}
