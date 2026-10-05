/**
 * CompareCharts + 차트 컴포넌트 통합 테스트
 * 실행: npx vitest run src/components/__tests__/CompareCharts.test.tsx
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { TestQueryProvider } from "@/test-setup";

import CompareCharts from "../CompareCharts";
import CompareRadarChart, { buildRadarData, formatRadarMissing } from "../CompareRadarChart";
import ComparePriceTrendChart from "../ComparePriceTrendChart";
import ComparePriceBarChart from "../ComparePriceBarChart";
import CompareFloorChart from "../CompareFloorChart";
import type { Complex, PriceHistoryItem, PriceStats } from "@/types";

// CompareCharts 컨테이너용 API mock (자식 차트 테스트에는 영향 0 — 자식은 @/lib/api 미사용)
const mockGetPriceHistory = vi.fn();
const mockGetPriceStats = vi.fn();
const mockGetPyeongDetails = vi.fn();

vi.mock("@/lib/api", () => ({
  getPriceHistory: (...args: unknown[]) => mockGetPriceHistory(...args),
  getPriceStats: (...args: unknown[]) => mockGetPriceStats(...args),
  getPyeongDetails: (...args: unknown[]) => mockGetPyeongDetails(...args),
}));

// Recharts mock (ResizeObserver/SVG 불필요)
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="chart-container">{children}</div>
  ),
  ComposedChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="composed-chart">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  RadarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="radar-chart">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  Area: () => <div data-testid="area" />,
  Bar: () => <div data-testid="bar" />,
  Radar: () => <div data-testid="radar" />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  PolarGrid: () => null,
  PolarAngleAxis: () => null,
  PolarRadiusAxis: () => null,
  Cell: () => null,
  LabelList: () => null,
}));

/** 팩토리 함수 */
function makeComplex(overrides: Partial<Complex> = {}): Complex {
  return {
    complex_no: "100001",
    complex_name: "테스트A",
    total_household_count: 1200,
    high_floor: 25,
    low_floor: 3,
    parking_count_by_household: 1.2,
    jeonse_rate: 55, // BE 저장 단위 = 퍼센트 (crawler/stats.py compute_jeonse_rate = jeonse/sale*100)
    recent_trades_6m: 15,
    article_count: 42,
    nearby_median_price: 90000,
    use_approve_ymd: "20150601",
    ...overrides,
  };
}

function makePriceItem(overrides: Partial<PriceHistoryItem> = {}): PriceHistoryItem {
  return {
    trade_type: "A1",
    trade_type_label: "매매",
    price_upper: 95000,
    price_lower: 85000,
    price_avg: 90000,
    base_month: "202503",
    ...overrides,
  };
}

function makePriceStats(overrides: Partial<PriceStats> = {}): PriceStats {
  return {
    complex_no: "100001",
    total_articles: 10,
    by_area: [
      { label: "59m²", maemae: 50000, jeonse: 30000, wolse: 800, maemae_count: 3, jeonse_count: 2, wolse_count: 1 },
    ],
    by_floor: [
      { label: "저층(1-5)", maemae_avg: 48000, maemae_min: 45000, maemae_max: 51000, maemae_count: 2 },
      { label: "중층(6-15)", maemae_avg: 52000, maemae_min: 49000, maemae_max: 55000, maemae_count: 3 },
      { label: "고층(16+)", maemae_avg: 58000, maemae_min: 55000, maemae_max: 61000, maemae_count: 2 },
    ],
    ...overrides,
  };
}

/* ── CompareRadarChart 테스트 ── */

describe("CompareRadarChart", () => {
  it("2개 단지로 레이더 차트 렌더링", () => {
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "단지A" }),
      makeComplex({ complex_no: "2", complex_name: "단지B", total_household_count: 800 }),
    ];
    render(<CompareRadarChart complexes={complexes} />);
    expect(screen.getByTestId("radar-chart")).toBeInTheDocument();
  });

  it("종합 우위 텍스트 표시", () => {
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "래미안", total_household_count: 2000 }),
      makeComplex({ complex_no: "2", complex_name: "자이", total_household_count: 500 }),
    ];
    render(<CompareRadarChart complexes={complexes} />);
    expect(screen.getByText(/종합 우위:/)).toBeInTheDocument();
  });

  it("1개 단지 → null 반환", () => {
    const { container } = render(
      <CompareRadarChart complexes={[makeComplex()]} />,
    );
    expect(container.innerHTML).toBe("");
  });
});

/* ── CompareRadarChart 빈 값 처리 (세션 429) ── */

describe("CompareRadarChart 빈 값 — 0점(꼴찌)으로 그리지 않는다", () => {
  /** 축 이름으로 데이터 줄 찾기 */
  function rowOf(data: ReturnType<typeof buildRadarData>["data"], label: string) {
    const row = data.find((r) => r.axis === label);
    if (!row) throw new Error(`축 없음: ${label}`);
    return row;
  }

  it("'최근 거래' 축이 없다 — 기본 7축, 평당가가 붙으면 8축", () => {
    const complexes = [makeComplex({ complex_no: "1" }), makeComplex({ complex_no: "2" })];
    const base = buildRadarData(complexes);
    expect(base.data.map((r) => r.axis)).not.toContain("최근 거래");
    expect(base.data).toHaveLength(7);
    expect(buildRadarData(complexes, { "1": 3000, "2": 4000 }).data).toHaveLength(8);
  });

  it("한 단지의 전세가율이 null 이면 그 축 그 단지 값은 null (0 아님), 다른 단지는 점수", () => {
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "래미안", jeonse_rate: undefined }),
      makeComplex({ complex_no: "2", complex_name: "자이", jeonse_rate: 60 }),
    ];
    const row = rowOf(buildRadarData(complexes).data, "전세가율");
    expect(row["1"]).toBeNull();
    expect(row["2"]).toBe(100);
  });

  it("평당가가 없는 단지는 평당가 축 값이 null", () => {
    const complexes = [makeComplex({ complex_no: "1" }), makeComplex({ complex_no: "2" })];
    const row = rowOf(buildRadarData(complexes, { "2": 4000 }).data, "평당가");
    expect(row["1"]).toBeNull();
    expect(row["2"]).not.toBeNull();
  });

  it("그래프 아래 줄 = '자료 없음 — 단지명: 축 · 단지명: 축', 같은 단지 여러 축은 쉼표", () => {
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "래미안", jeonse_rate: undefined }),
      makeComplex({ complex_no: "2", complex_name: "자이", parking_count_by_household: undefined }),
    ];
    render(<CompareRadarChart complexes={complexes} />);
    expect(
      screen.getByText("자료 없음 — 래미안: 전세가율 · 자이: 세대당 주차"),
    ).toBeInTheDocument();

    const many = buildRadarData([
      makeComplex({ complex_no: "1", complex_name: "래미안", jeonse_rate: undefined, high_floor: undefined }),
      makeComplex({ complex_no: "2", complex_name: "자이" }),
    ]);
    expect(formatRadarMissing(many.missing)).toBe("자료 없음 — 래미안: 전세가율, 최고층");
  });

  it("빈 값이 없으면 '자료 없음' 줄을 그리지 않는다", () => {
    const complexes = [makeComplex({ complex_no: "1" }), makeComplex({ complex_no: "2" })];
    render(<CompareRadarChart complexes={complexes} />);
    expect(screen.queryByText(/자료 없음/)).toBeNull();
  });

  it("종합 우위는 모두 값이 있는 축만 더한다 — 빈 값을 0 으로 더하면 순위가 뒤집히는 예", () => {
    // 래미안: 세대수 2000(100점), 전세가율 없음 / 자이: 세대수 1000(50점), 전세가율 60(100점)
    // 빈 값을 0 으로 더하면 자이가 +50 앞선다. 모두 값이 있는 축만 보면 래미안이 +50 앞선다.
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "래미안", total_household_count: 2000, jeonse_rate: undefined }),
      makeComplex({ complex_no: "2", complex_name: "자이", total_household_count: 1000, jeonse_rate: 60 }),
    ];
    expect(buildRadarData(complexes).bestName).toBe("래미안");
  });

  it("모두 값이 있는 축이 하나도 없으면 종합 우위 줄을 표시하지 않는다", () => {
    const complexes: Complex[] = [
      { complex_no: "1", complex_name: "래미안", total_household_count: 2000 },
      { complex_no: "2", complex_name: "자이", parking_count_by_household: 1.5 },
    ];
    expect(buildRadarData(complexes).bestName).toBe("");
    render(<CompareRadarChart complexes={complexes} />);
    expect(screen.queryByText(/종합 우위/)).toBeNull();
  });

  it("50년 넘은 단지 신축도는 진짜 0 이고 빈 값 줄에 나오지 않는다", () => {
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "옛단지", use_approve_ymd: "19500101" }),
      makeComplex({ complex_no: "2", complex_name: "새단지", use_approve_ymd: "20200101" }),
    ];
    const result = buildRadarData(complexes);
    expect(rowOf(result.data, "신축도")["1"]).toBe(0);
    expect(result.missing).toEqual([]);
  });

  it("준공일이 없으면 신축도는 빈 값", () => {
    const complexes = [
      makeComplex({ complex_no: "1", complex_name: "옛단지", use_approve_ymd: undefined }),
      makeComplex({ complex_no: "2", complex_name: "새단지" }),
    ];
    const result = buildRadarData(complexes);
    expect(rowOf(result.data, "신축도")["1"]).toBeNull();
    expect(result.missing).toEqual([{ complexName: "옛단지", axes: ["신축도"] }]);
  });
});

/* ── ComparePriceTrendChart 테스트 ── */

describe("ComparePriceTrendChart", () => {
  it("빈 데이터 시 안내 메시지", () => {
    render(<ComparePriceTrendChart datasets={[]} />);
    expect(screen.getByText(/가격 추이 데이터가 부족/)).toBeInTheDocument();
  });

  it("2개 단지 데이터로 차트 렌더링", () => {
    const datasets = [
      {
        complexNo: "1", complexName: "단지A",
        items: [makePriceItem({ base_month: "202501" }), makePriceItem({ base_month: "202502" })],
      },
      {
        complexNo: "2", complexName: "단지B",
        items: [makePriceItem({ base_month: "202501", price_avg: 80000 })],
      },
    ];
    render(<ComparePriceTrendChart datasets={datasets} />);
    expect(screen.getByTestId("composed-chart")).toBeInTheDocument();
  });

  it("기간 필터 버튼 렌더링", () => {
    const datasets = [{
      complexNo: "1", complexName: "A",
      items: [makePriceItem()],
    }];
    render(<ComparePriceTrendChart datasets={datasets} />);
    expect(screen.getByText("6개월")).toBeInTheDocument();
    expect(screen.getByText("1년")).toBeInTheDocument();
    expect(screen.getByText("2년")).toBeInTheDocument();
    // "전체"는 거래유형 토글 + 기간 필터 양쪽에 존재
    expect(screen.getAllByText("전체").length).toBe(2);
  });

  it("거래유형 토글 버튼 렌더링", () => {
    const datasets = [{
      complexNo: "1", complexName: "A",
      items: [makePriceItem()],
    }];
    render(<ComparePriceTrendChart datasets={datasets} />);
    expect(screen.getByText("매매")).toBeInTheDocument();
    expect(screen.getByText("전세")).toBeInTheDocument();
  });

  it("최근 매매 최고 텍스트 표시", () => {
    const datasets = [
      { complexNo: "1", complexName: "높은단지", items: [makePriceItem({ price_avg: 120000 })] },
      { complexNo: "2", complexName: "낮은단지", items: [makePriceItem({ price_avg: 80000 })] },
    ];
    render(<ComparePriceTrendChart datasets={datasets} />);
    expect(screen.getByText(/최근 매매 최고: 높은단지/)).toBeInTheDocument();
  });
});

/* ── ComparePriceBarChart 테스트 ── */

describe("ComparePriceBarChart", () => {
  it("빈 데이터 시 안내 메시지", () => {
    render(
      <ComparePriceBarChart
        datasets={[{ complexNo: "1", complexName: "A", priceStats: makePriceStats({ by_area: [] }) }]}
      />,
    );
    expect(screen.getByText(/가격 통계 데이터가 부족/)).toBeInTheDocument();
  });

  it("데이터 있을 때 바차트 렌더링", () => {
    render(
      <ComparePriceBarChart
        datasets={[
          { complexNo: "1", complexName: "A", priceStats: makePriceStats() },
          { complexNo: "2", complexName: "B", priceStats: makePriceStats() },
        ]}
      />,
    );
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });
});

/* ── CompareFloorChart 테스트 ── */

describe("CompareFloorChart", () => {
  it("빈 데이터 시 안내 메시지", () => {
    render(
      <CompareFloorChart
        datasets={[{ complexNo: "1", complexName: "A", priceStats: makePriceStats({ by_floor: [] }) }]}
      />,
    );
    expect(screen.getByText(/층별 가격 데이터가 부족/)).toBeInTheDocument();
  });

  it("데이터 있을 때 바차트 렌더링", () => {
    render(
      <CompareFloorChart
        datasets={[
          { complexNo: "1", complexName: "A", priceStats: makePriceStats() },
          { complexNo: "2", complexName: "B", priceStats: makePriceStats() },
        ]}
      />,
    );
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });

  it("층구간별 우위 텍스트 표시", () => {
    render(
      <CompareFloorChart
        datasets={[
          { complexNo: "1", complexName: "단지A", priceStats: makePriceStats() },
          { complexNo: "2", complexName: "단지B", priceStats: makePriceStats({
            by_floor: [
              { label: "저층(1-5)", maemae_avg: 99000, maemae_count: 1 },
              { label: "중층(6-15)", maemae_avg: 99000, maemae_count: 1 },
              { label: "고층(16+)", maemae_avg: 99000, maemae_count: 1 },
            ],
          }) },
        ]}
      />,
    );
    // 단지B가 모든 층에서 최고가
    expect(screen.getByText(/저층 최고: 단지B/)).toBeInTheDocument();
  });
});

/* ── CompareCharts 컨테이너 — 에러 분기 다시 시도 (세션 298 dead-end 해소) ── */

describe("CompareCharts — 에러 분기 다시 시도 (실패 쿼리만 재조회)", () => {
  const complexes = [
    { complex_no: "1", complex_name: "단지A" },
    { complex_no: "2", complex_name: "단지B" },
  ];
  const fullComplexes = [
    makeComplex({ complex_no: "1", complex_name: "단지A" }),
    makeComplex({ complex_no: "2", complex_name: "단지B" }),
  ];

  function renderCharts() {
    return render(
      <CompareCharts complexes={complexes} fullComplexes={fullComplexes} expandAll />,
      { wrapper: TestQueryProvider },
    );
  }

  /** mock 호출 중 특정 단지번호로 들어온 횟수 */
  const callsFor = (mock: ReturnType<typeof vi.fn>, no: string) =>
    mock.mock.calls.filter((c) => c[0] === no).length;

  beforeEach(() => {
    mockGetPriceHistory.mockReset();
    mockGetPriceStats.mockReset();
    mockGetPyeongDetails.mockReset();
    mockGetPriceHistory.mockResolvedValue({ complex_no: "X", items: [makePriceItem()] });
    mockGetPriceStats.mockResolvedValue(makePriceStats());
    mockGetPyeongDetails.mockResolvedValue({ pyeong_details: [] });
  });

  it("history 1개 실패 → '다시 시도' 클릭 시 실패한 단지만 재조회", async () => {
    mockGetPriceHistory.mockImplementation((no: string) =>
      no === "1"
        ? Promise.reject(new Error("fail"))
        : Promise.resolve({ complex_no: no, items: [makePriceItem()] }),
    );
    renderCharts();
    await waitFor(() => {
      expect(screen.getByText("가격 추이를 불러오지 못했습니다.")).toBeInTheDocument();
    });
    const failedBefore = callsFor(mockGetPriceHistory, "1");
    const okBefore = callsFor(mockGetPriceHistory, "2");
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await waitFor(() => {
      expect(callsFor(mockGetPriceHistory, "1")).toBe(failedBefore + 1);
    });
    expect(callsFor(mockGetPriceHistory, "2")).toBe(okBefore);
  });

  it("stats 1개 실패 → 평균가/층별/면적별표 3곳에 '다시 시도' 노출, 클릭 시 실패 쿼리만 재조회", async () => {
    mockGetPriceStats.mockImplementation((no: string) =>
      no === "2" ? Promise.reject(new Error("fail")) : Promise.resolve(makePriceStats()),
    );
    renderCharts();
    await waitFor(() => {
      expect(screen.getByText("가격 통계를 불러오지 못했습니다.")).toBeInTheDocument();
    });
    const buttons = screen.getAllByRole("button", { name: "다시 시도" });
    expect(buttons.length).toBe(3);
    const failedBefore = callsFor(mockGetPriceStats, "2");
    const okBefore = callsFor(mockGetPriceStats, "1");
    fireEvent.click(buttons[0]);
    await waitFor(() => {
      expect(callsFor(mockGetPriceStats, "2")).toBe(failedBefore + 1);
    });
    expect(callsFor(mockGetPriceStats, "1")).toBe(okBefore);
  });

  it("pyeong 1개 실패 → 관리비/세대구성 2곳에 '다시 시도' 노출, 클릭 시 실패 쿼리만 재조회", async () => {
    mockGetPyeongDetails.mockImplementation((no: string) =>
      no === "1" ? Promise.reject(new Error("fail")) : Promise.resolve({ pyeong_details: [] }),
    );
    renderCharts();
    await waitFor(() => {
      expect(screen.getByText("관리비를 불러오지 못했습니다.")).toBeInTheDocument();
    });
    const buttons = screen.getAllByRole("button", { name: "다시 시도" });
    expect(buttons.length).toBe(2);
    const failedBefore = callsFor(mockGetPyeongDetails, "1");
    const okBefore = callsFor(mockGetPyeongDetails, "2");
    fireEvent.click(buttons[0]);
    await waitFor(() => {
      expect(callsFor(mockGetPyeongDetails, "1")).toBe(failedBefore + 1);
    });
    expect(callsFor(mockGetPyeongDetails, "2")).toBe(okBefore);
  });
});
