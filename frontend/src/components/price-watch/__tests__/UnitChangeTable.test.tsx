/** ① 같은 집 호가 변동표 — 요약·정렬·상태 필터·가격 경로 펼치기 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import UnitChangeTable from "../UnitChangeTable";
import type { PriceWatchUnit, PriceWatchUnitsResponse } from "@/types/price-watch";

function makeUnit(over: Partial<PriceWatchUnit>): PriceWatchUnit {
  return {
    unit_key: "101동|12|84.9", complex_no: "1", complex_name: "가단지", building: "101동", floor: "12",
    floor_info: "12/25", area_m2: 84.9, pyeong: 25.7, confidence: "높음",
    first_date: "2026-09-01", first_price: 100000, last_date: "2026-09-15", last_price: 95000,
    change_amount: -5000, change_pct: -5, min_price: 95000, max_price: 100000,
    observations: 3, price_moves: 1, listings_now: 1, status: "active",
    series: [
      { date: "2026-09-01", price: 100000, min: 100000, max: 102000, listings: 2 },
      { date: "2026-09-15", price: 95000, min: 95000, max: 95000, listings: 1 },
    ],
    ...over,
  };
}

function makeData(units: PriceWatchUnit[]): PriceWatchUnitsResponse {
  return {
    period: { start: "2026-08-01", end: "2026-09-20", days: 50 },
    summary: { unit_count: units.length, tracked_count: 2, up_count: 1, down_count: 1, flat_count: 0,
      median_change_pct: -1.5, avg_change_pct: -1.5, gone_count: 1 },
    units,
  };
}

const units = [
  makeUnit({ unit_key: "a", building: "101동", change_pct: 2, change_amount: 2000, last_price: 102000 }),
  makeUnit({ unit_key: "b", building: "102동", change_pct: -5, status: "gone" }),
];

describe("UnitChangeTable", () => {
  it("요약에 중앙값 변동률과 내림/올림 수를 보여준다", () => {
    render(<UnitChangeTable data={makeData(units)} />);
    expect(screen.getByText("-1.50%")).toBeInTheDocument();
    expect(screen.getByText("1 / 1 / 0")).toBeInTheDocument();
  });

  it("기본 정렬은 많이 내린 집이 먼저", () => {
    render(<UnitChangeTable data={makeData(units)} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText(/102동/)).toBeInTheDocument();
  });

  it("상태 필터로 지금 나와 있는 집만 본다", () => {
    render(<UnitChangeTable data={makeData(units)} />);
    fireEvent.change(screen.getByLabelText("상태"), { target: { value: "active" } });
    expect(screen.queryByText(/102동/)).not.toBeInTheDocument();
    expect(screen.getByText(/101동/)).toBeInTheDocument();
  });

  it("행을 누르면 날짜별 호가와 중복 등록 수를 펼친다", () => {
    render(<UnitChangeTable data={makeData([units[1]])} />);
    fireEvent.click(screen.getByText(/102동/));
    expect(screen.getByText(/등록 2건/)).toBeInTheDocument();
  });

  it("기록이 없으면 빈 안내", () => {
    render(<UnitChangeTable data={makeData([])} />);
    expect(screen.getByText("이 기간에 기록된 매매 호가가 없어요.")).toBeInTheDocument();
  });
});
