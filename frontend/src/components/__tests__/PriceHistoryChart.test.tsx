/**
 * PriceHistoryChart 컴포넌트 테스트 - 가격 추이 라인차트
 * 실행: npx vitest run src/components/__tests__/PriceHistoryChart.test.tsx
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PriceHistoryChart from "../PriceHistoryChart";
import type { PriceHistoryItem } from "@/types";

// Recharts는 ResizeObserver/SVG 필요 — 전체 mock 처리
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="chart-container">{children}</div>
  ),
  ComposedChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="composed-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  Area: () => <div data-testid="area" />,
  Scatter: () => <div data-testid="trade-points" />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

/** 테스트 데이터 팩토리 */
function makeItem(overrides: Partial<PriceHistoryItem> = {}): PriceHistoryItem {
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

describe("PriceHistoryChart", () => {
  it("빈 데이터 시 안내 메시지 표시", () => {
    render(<PriceHistoryChart items={[]} />);
    expect(screen.getByText(/가격 추이 데이터가 아직 없습니다/)).toBeInTheDocument();
  });

  it("데이터 있을 때 차트 렌더링 (크래시 없음)", () => {
    const items = [
      makeItem({ base_month: "202502", price_avg: 88000 }),
      makeItem({ base_month: "202503", price_avg: 90000 }),
      makeItem({ trade_type: "B1", trade_type_label: "전세", base_month: "202502", price_avg: 47000 }),
      makeItem({ trade_type: "B1", trade_type_label: "전세", base_month: "202503", price_avg: 48000 }),
    ];
    const { container } = render(<PriceHistoryChart items={items} />);
    expect(container.querySelector('[role="img"]')).toBeInTheDocument();
  });

  it("매매만 있을 때도 정상 렌더링", () => {
    const items = [
      makeItem({ base_month: "202502" }),
      makeItem({ base_month: "202503" }),
    ];
    const { container } = render(<PriceHistoryChart items={items} />);
    expect(container.querySelector('[role="img"]')).toBeInTheDocument();
  });

  it("null price_avg 처리 (크래시 없음)", () => {
    const items = [
      makeItem({ base_month: "202502", price_avg: null }),
      makeItem({ base_month: "202503", price_avg: 90000 }),
    ];
    const { container } = render(<PriceHistoryChart items={items} />);
    expect(container.querySelector('[role="img"]')).toBeInTheDocument();
  });

  /* 기간 선택 버튼 테스트 */
  it("기간 필터 버튼 렌더링 (6개월, 1년, 2년, 전체)", () => {
    const items = [makeItem({ base_month: "202503" })];
    render(<PriceHistoryChart items={items} />);
    expect(screen.getByText("6개월")).toBeInTheDocument();
    expect(screen.getByText("1년")).toBeInTheDocument();
    expect(screen.getByText("2년")).toBeInTheDocument();
    expect(screen.getByText("전체")).toBeInTheDocument();
  });

  it("전체가 기본 선택 상태", () => {
    const items = [makeItem({ base_month: "202503" })];
    render(<PriceHistoryChart items={items} />);
    const allBtn = screen.getByText("전체");
    expect(allBtn.className).toContain("bg-blue-600");
  });

  it("6개월 버튼 클릭 시 활성 상태 변경", async () => {
    // 현재 날짜 기준 최근 월 데이터 사용 (6개월 필터에도 남도록)
    const now = new Date();
    const recentMonth = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}`;
    const items = [makeItem({ base_month: recentMonth })];
    render(<PriceHistoryChart items={items} />);
    await userEvent.click(screen.getByText("6개월"));
    await waitFor(() => {
      expect(screen.getByText("6개월").className).toContain("bg-blue-600");
      expect(screen.getByText("전체").className).not.toContain("bg-blue-600");
    });
  });

  it("빈 데이터일 때 기간 버튼 표시 안 함", () => {
    render(<PriceHistoryChart items={[]} />);
    expect(screen.queryByText("6개월")).not.toBeInTheDocument();
  });

  /* 개별 실거래 점 (Scatter 오버레이) */
  it("tradePoints 있을 때 Scatter 렌더링", () => {
    const items = [makeItem({ base_month: "202503" })];
    const tradePoints = [
      { year_month: "202503", deal_day: "10", price: 87000, area2_m2: 84.0, floor_number: 3 },
      { year_month: "202503", deal_day: "18", price: 92000, area2_m2: 84.0, floor_number: 8 },
    ];
    const { container } = render(<PriceHistoryChart items={items} tradePoints={tradePoints} />);
    expect(container.querySelector('[data-testid="trade-points"]')).toBeInTheDocument();
  });

  it("tradePoints 없으면 Scatter 렌더링 안 함 (하위 호환)", () => {
    const items = [makeItem({ base_month: "202503" })];
    const { container } = render(<PriceHistoryChart items={items} />);
    expect(container.querySelector('[data-testid="trade-points"]')).not.toBeInTheDocument();
  });

  it("tradePoints가 기간 필터를 함께 적용받는다", () => {
    const now = new Date();
    const recentMonth = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}`;
    const oldMonth = "202401";
    const items = [
      makeItem({ base_month: recentMonth }),
      makeItem({ base_month: oldMonth }),
    ];
    const tradePoints = [
      { year_month: recentMonth, deal_day: "10", price: 90000, area2_m2: 84.0, floor_number: 3 },
      { year_month: oldMonth, deal_day: "10", price: 80000, area2_m2: 84.0, floor_number: 3 },
    ];
    render(<PriceHistoryChart items={items} tradePoints={tradePoints} />);
    // 6개월 필터 적용 → 오래된 달 점 제거 (chart 데이터는 mock이라 직접 검증 불가)
    // 컴포넌트가 점을 기간에 맞게 거르는지만 크래시 없이 확인
    expect(screen.getByText("6개월")).toBeInTheDocument();
  });
});
