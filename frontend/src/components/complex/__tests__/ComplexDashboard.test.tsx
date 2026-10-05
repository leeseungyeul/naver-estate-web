/**
 * ComplexDashboard 회귀 가드 (PR 6c 신설 + PR 6d 데스크톱 통합)
 *
 * 구조: 박스 4개 (모바일 2×2 / 데스크톱 4×1) + 별도 펼침 영역.
 * useComplexArticleAvg mock 의무 (F3 가드).
 *
 * 실행: npx vitest run src/components/complex/__tests__/ComplexDashboard.test.tsx
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ComplexDashboard from "../ComplexDashboard";
import type { Complex, PyeongDetail } from "@/types";

// F3 가드: useComplexArticleAvg mock 의무 (TestQueryProvider 없이 render 가능)
const mockUseComplexArticleAvg = vi.fn(() => ({
  avgPrice: null as number | null,
  count: 0,
  isLoading: false,
  isError: false,
}));

vi.mock("@/hooks/useComplexArticleAvg", () => ({
  useComplexArticleAvg: () => mockUseComplexArticleAvg(),
}));

// 자식 섹션 mock (jsdom 환경 + 외부 의존성 차단)
vi.mock("@/components/complex/ComplexPriceFloorSection", () => ({
  default: () => <div data-testid="mock-price-floor" />,
}));
vi.mock("@/components/complex/ComplexPriceAreaSection", () => ({
  default: () => <div data-testid="mock-price-area" />,
}));
vi.mock("@/components/complex/PriceChartSection", () => ({
  default: () => <div data-testid="mock-price-chart" />,
}));
vi.mock("@/components/ComplexPyeongCard", () => ({
  PyeongDetailsList: () => <div data-testid="mock-pyeong-list" />,
}));
vi.mock("@/components/ComplexBasicInfo", () => ({
  default: () => <div data-testid="mock-basic-info" />,
}));

const baseComplex: Complex = {
  complex_no: "C001",
  complex_name: "테스트단지",
  total_household_count: 1234,
  total_dong_count: 12,
  nearby_median_price: 80000,
  jeonse_rate: 65,
  recent_trades_6m: 42,
};

const samplePyeong: PyeongDetail[] = [
  { pyeong_no: 1, pyeong_name: "84A", exclusive_area: "84.99" },
  { pyeong_no: 2, pyeong_name: "109B", exclusive_area: "109.95" },
];

describe("ComplexDashboard (v2)", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    mockUseComplexArticleAvg.mockReturnValue({
      avgPrice: null,
      count: 0,
      isLoading: false,
      isError: false,
    });
  });

  it("4 박스 라벨 + 핵심 지표 표시 (중요도순)", () => {
    render(
      <ComplexDashboard
        complex={baseComplex}
        complexNo="C001"
        pyeongDetails={samplePyeong}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    // 4 박스 button accessible name (F6 selector 패턴 유지)
    expect(screen.getByRole("button", { name: "시세 메뉴 열기" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "실거래가 메뉴 열기" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "단지정보 메뉴 열기" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "면적별 시세 메뉴 열기" })).toBeInTheDocument();

    // 평형 박스 부재 (Q4 흡수)
    expect(screen.queryByRole("button", { name: "평형 메뉴 열기" })).not.toBeInTheDocument();

    // 핵심 지표
    expect(screen.getByText(/전세가율 65%/)).toBeInTheDocument();
    expect(screen.getByText("매물 0건")).toBeInTheDocument();
    expect(screen.getByText("1,234세대")).toBeInTheDocument();
    expect(screen.getByText("2개 평형")).toBeInTheDocument();
  });

  it("박스 클릭 시 펼침 영역 노출 + aria-expanded toggle", async () => {
    render(
      <ComplexDashboard
        complex={baseComplex}
        complexNo="C001"
        pyeongDetails={samplePyeong}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    const priceCard = screen.getByRole("button", { name: "시세 메뉴 열기" });
    expect(priceCard).toHaveAttribute("aria-expanded", "false");

    // 펼침 영역 초기 부재
    expect(screen.queryByRole("region")).not.toBeInTheDocument();

    await userEvent.click(priceCard);
    expect(priceCard).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region")).toBeInTheDocument();
    expect(screen.getByTestId("mock-price-floor")).toBeInTheDocument();

    // 다시 클릭 → 닫힘
    await userEvent.click(priceCard);
    expect(priceCard).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("NULL fallback: 시세는 '매물 평균', 실거래가는 '매물 N건' (F4 가드)", () => {
    mockUseComplexArticleAvg.mockReturnValue({
      avgPrice: 75000,
      count: 46,
      isLoading: false,
      isError: false,
    });
    const empty: Complex = { complex_no: "C002", complex_name: "값없음단지" };
    render(
      <ComplexDashboard
        complex={empty}
        complexNo="C002"
        pyeongDetails={[]}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    // 시세 박스 = 매물 평균 (formatKoreanPrice(75000))
    expect(screen.getByText(/매물 평균/)).toBeInTheDocument();
    // 실거래가 박스 primary = '매물 46건' + 시세 박스 secondary (jeonse_rate NULL fallback) = '매물 46건'
    // = 2곳 동시 노출 (의도된 fallback 일관성)
    const occurrences = screen.getAllByText("매물 46건");
    expect(occurrences.length).toBeGreaterThanOrEqual(1);
  });

  it("실거래가 칸: recent_trades_6m 이 있어도 '거래 N건'이 아니라 '매물 N건 · 현재 매물' (세션 429)", () => {
    // recent_trades_6m 은 실제 거래 횟수가 아니라 시세 기록 줄 수 — 거래처럼 보이면 안 된다
    mockUseComplexArticleAvg.mockReturnValue({
      avgPrice: null,
      count: 7,
      isLoading: false,
      isError: false,
    });
    render(
      <ComplexDashboard
        complex={{ ...baseComplex, recent_trades_6m: 42 }}
        complexNo="C001"
        pyeongDetails={samplePyeong}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );
    expect(screen.queryByText("42건")).toBeNull();
    expect(screen.queryByText("최근 6개월")).toBeNull();
    expect(screen.getByText("매물 7건")).toBeInTheDocument();
    expect(screen.getByText("현재 매물")).toBeInTheDocument();
  });

  it("면적별 시세 펼친 후 안내 메시지 (평형 0건, F5 가드)", async () => {
    const empty: Complex = { complex_no: "C003", complex_name: "평형없음단지" };
    render(
      <ComplexDashboard
        complex={empty}
        complexNo="C003"
        pyeongDetails={[]}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    // F5: selector = "면적별 시세 메뉴 열기" (구 "평형 메뉴 열기" 제거 답습)
    await userEvent.click(screen.getByRole("button", { name: "면적별 시세 메뉴 열기" }));
    expect(
      await screen.findByText("면적별 정보가 아직 수집되지 않았습니다."),
    ).toBeInTheDocument();
    // 평형 0건이어도 면적별 시세 컴포넌트는 함께 렌더
    expect(screen.getByTestId("mock-price-area")).toBeInTheDocument();
  });

  it("면적별 시세 펼친 후 PyeongDetailsList + ComplexPriceAreaSection 둘 다 렌더 (F11 가드)", async () => {
    render(
      <ComplexDashboard
        complex={baseComplex}
        complexNo="C001"
        pyeongDetails={samplePyeong}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "면적별 시세 메뉴 열기" }));
    expect(screen.getByTestId("mock-pyeong-list")).toBeInTheDocument();
    expect(screen.getByTestId("mock-price-area")).toBeInTheDocument();
  });

  it("avgPrice/count 모두 null/0 → 시세 박스 '-' 표시", () => {
    const empty: Complex = { complex_no: "C004", complex_name: "전체NULL단지" };
    render(
      <ComplexDashboard
        complex={empty}
        complexNo="C004"
        pyeongDetails={[]}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    // 시세 박스 primary = '-' (nearby_median_price NULL + avgPrice null)
    const dashes = screen.getAllByText("-");
    expect(dashes.length).toBeGreaterThanOrEqual(3); // 시세 + 단지정보 + 면적별 시세
  });

  // PR-D: 공시가격·공시가율 행은 ComplexBasicInfo 안에 있으므로, 인쇄 시 그 섹션이
  // 실제로 마운트되는지를 여기서 가드한다 (isPrinting 소유자 = 이 컴포넌트).
  it("인쇄(beforeprint) 시 단지정보 섹션 포함 4 섹션 모두 노출 (PR-D 인쇄 경로 가드)", () => {
    render(
      <ComplexDashboard
        complex={baseComplex}
        complexNo="C001"
        pyeongDetails={samplePyeong}
        sessionToken={undefined}
        onFilterChange={() => {}}
      />,
    );

    // 아무 박스도 안 열린 상태 = 펼침 영역 부재
    expect(screen.queryByTestId("mock-basic-info")).not.toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("beforeprint"));
    });

    // 공시가격·공시가율 행이 사는 단지정보 섹션이 인쇄 시 노출돼야 한다
    expect(screen.getByTestId("mock-basic-info")).toBeInTheDocument();
    expect(screen.getByTestId("mock-price-floor")).toBeInTheDocument();
    expect(screen.getByTestId("mock-price-chart")).toBeInTheDocument();
    expect(screen.getByTestId("mock-pyeong-list")).toBeInTheDocument();

    // 인쇄 종료 시 원래대로 접힘
    act(() => {
      window.dispatchEvent(new Event("afterprint"));
    });
    expect(screen.queryByTestId("mock-basic-info")).not.toBeInTheDocument();
  });
});
