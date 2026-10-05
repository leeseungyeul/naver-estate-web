/**
 * compare-utils 우위 판정 로직 테스트
 * 실행: npx vitest run src/lib/__tests__/compare-utils.test.ts
 */
import { describe, it, expect } from "vitest";
import {
  getBestIndices,
  parseApprovalDate,
  getAdvantageForRow,
  calcAvgPricePerPyeong,
  ADVANTAGE_ROWS,
} from "../compare-utils";
import type { Complex, PriceStats } from "@/types";

/** 테스트용 단지 팩토리 */
function makeComplex(overrides: Partial<Complex> = {}): Complex {
  return {
    complex_no: "100001",
    complex_name: "테스트 단지",
    ...overrides,
  };
}

describe("getBestIndices", () => {
  it("정상: 4개 값 중 최대 인덱스 반환 (higher)", () => {
    expect(getBestIndices([70, 90, 80, 60], "higher")).toEqual([1]);
  });

  it("정상: 최소값 인덱스 반환 (lower)", () => {
    expect(getBestIndices([70, 90, 50, 60], "lower")).toEqual([2]);
  });

  it("동점: 여러 인덱스 반환", () => {
    expect(getBestIndices([90, 90, 80, 70], "higher")).toEqual([0, 1]);
  });

  it("null 포함: null 무시하고 유효값에서 최대", () => {
    expect(getBestIndices([null, 90, null, 80], "higher")).toEqual([1]);
  });

  it("null 포함 (lower): null 무시하고 최소", () => {
    expect(getBestIndices([null, 30, null, 50], "lower")).toEqual([1]);
  });

  it("전체 null: 빈 배열 반환", () => {
    expect(getBestIndices([null, null, null], "higher")).toEqual([]);
  });

  it("빈 배열: 빈 배열 반환", () => {
    expect(getBestIndices([], "higher")).toEqual([]);
  });

  it("단일 값: 해당 인덱스 반환", () => {
    expect(getBestIndices([42], "higher")).toEqual([0]);
  });

  it("모두 동점: 모든 인덱스 반환", () => {
    expect(getBestIndices([100, 100, 100], "higher")).toEqual([0, 1, 2]);
  });
});

describe("parseApprovalDate", () => {
  it("YYYYMMDD 형식 파싱", () => {
    expect(parseApprovalDate("20200315")).toBe(20200315);
  });

  it("YYYYMM 형식 파싱", () => {
    expect(parseApprovalDate("202003")).toBe(202003);
  });

  it("undefined → null", () => {
    expect(parseApprovalDate(undefined)).toBeNull();
  });

  it("빈 문자열 → null", () => {
    expect(parseApprovalDate("")).toBeNull();
  });

  it("숫자 아닌 값 → null", () => {
    expect(parseApprovalDate("abcdef")).toBeNull();
  });
});

describe("getAdvantageForRow", () => {
  it("세대수 우위 판정: 가장 많은 단지", () => {
    const complexes = [
      makeComplex({ total_household_count: 1200, complex_name: "A" }),
      makeComplex({ total_household_count: 800, complex_name: "B" }),
      makeComplex({ total_household_count: 2000, complex_name: "C" }),
    ];
    expect(getAdvantageForRow("세대수", complexes)).toEqual([2]);
  });

  it("용적률 우위 판정: 낮을수록 우위", () => {
    const complexes = [
      makeComplex({ floor_area_ratio: "250", complex_name: "A" }),
      makeComplex({ floor_area_ratio: "180", complex_name: "B" }),
    ];
    expect(getAdvantageForRow("용적률", complexes)).toEqual([1]);
  });

  it("ADVANTAGE_ROWS에 없는 라벨: 빈 배열", () => {
    const complexes = [makeComplex()];
    expect(getAdvantageForRow("주소", complexes)).toEqual([]);
  });

  it("ADVANTAGE_ROWS 개수 확인", () => {
    expect(ADVANTAGE_ROWS.length).toBe(13);
  });

  it("'최근 6개월 거래' 우위 행 없음 — recent_trades_6m 은 거래 횟수가 아니라 시세 기록 줄 수 (세션 429)", () => {
    expect(ADVANTAGE_ROWS.map((r) => r.label)).not.toContain("최근 6개월 거래");
    expect(ADVANTAGE_ROWS.map((r) => r.label)).toContain("매물수");
  });
});

/** 테스트용 PriceStats 팩토리 */
function makeStats(
  byArea: { label: string; maemae?: number; maemae_count?: number }[],
): PriceStats {
  return {
    complex_no: "100001",
    total_articles: 10,
    by_area: byArea.map((a) => ({ ...a })),
    by_floor: [],
  };
}

describe("calcAvgPricePerPyeong", () => {
  it("정상: 면적별 매매 데이터 → 가중 평균 평당가 반환", () => {
    // 85m² = 약 25.71평, 매매 50000만원 → 평당가 ≈ 1945만
    const stats = makeStats([
      { label: "85m²", maemae: 50000, maemae_count: 3 },
      { label: "60m²", maemae: 35000, maemae_count: 2 },
    ]);
    const result = calcAvgPricePerPyeong(stats);
    expect(result).not.toBeNull();
    expect(result).toBeGreaterThan(1500);
    expect(result).toBeLessThan(2500);
  });

  it("label 파싱 실패 → null 반환", () => {
    const stats = makeStats([
      { label: "N/A", maemae: 50000, maemae_count: 3 },
    ]);
    expect(calcAvgPricePerPyeong(stats)).toBeNull();
  });

  it("빈 by_area → null 반환", () => {
    const stats = makeStats([]);
    expect(calcAvgPricePerPyeong(stats)).toBeNull();
  });
});
