/** ② 단지 묶음 평균 변동 — 요약 변동률 3종·단지별 표·빈 상태 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import BasketTrend from "../BasketTrend";
import type { PriceWatchBasketResponse } from "@/types/price-watch";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: ReactNode }) => <div data-testid="chart">{children}</div>,
  Line: () => null, XAxis: () => null, YAxis: () => null, CartesianGrid: () => null, Tooltip: () => null,
}));

function makeData(over: Partial<PriceWatchBasketResponse> = {}): PriceWatchBasketResponse {
  return {
    period: { start: "2026-08-01", end: "2026-09-20", days: 50 },
    summary: { first_date: "2026-09-01", last_date: "2026-09-08", first_avg_price: 100000,
      last_avg_price: 150000, avg_price_change_pct: 50, avg_ppy_change_pct: 12.5,
      same_unit_index_change_pct: 0, observation_days: 2 },
    series: [
      { date: "2026-09-01", avg_price: 100000, avg_ppy: 3900, unit_count: 1, index: 100, complex_coverage: 1, complex_count: 1 },
      { date: "2026-09-08", avg_price: 150000, avg_ppy: 4400, unit_count: 2, index: 100, complex_coverage: 1, complex_count: 1 },
    ],
    targets: [{ target_id: 1, complex_no: "1", complex_name: "가단지", area_m2: 84.9, pyeong: 25.7, label: null,
      first_avg_price: 100000, last_avg_price: 150000, change_pct: 50, ppy_change_pct: 12.5, series: [] }],
    ...over,
  };
}

describe("BasketTrend", () => {
  it("평균·3.3㎡당·동일 매물 지수 변동률을 따로 보여준다", () => {
    render(<BasketTrend data={makeData()} />);
    expect(screen.getAllByText("+50.00%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("+12.50%").length).toBeGreaterThan(0);
    expect(screen.getByText("0.00%")).toBeInTheDocument();
    expect(screen.getByText("가단지")).toBeInTheDocument();
    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });

  it("기록이 없으면 빈 안내", () => {
    render(<BasketTrend data={makeData({ series: [], targets: [] })} />);
    expect(screen.getByText("이 기간에 기록된 매매 호가가 없어요.")).toBeInTheDocument();
  });
});
