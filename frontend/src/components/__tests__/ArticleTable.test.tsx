/**
 * ArticleTable 컴포넌트 테스트 - 매물 행 렌더링, 빈 상태, 정렬 토글
 * 실행: npx vitest run src/components/__tests__/ArticleTable.test.tsx
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ArticleTable from "../ArticleTable";
import type { Article } from "@/types";

beforeEach(() => {
  localStorage.clear();
});

const sampleArticle: Article = {
  article_no: "A001",
  complex_no: "C001",
  trade_type_name: "매매",
  building_name: "101동",
  floor_info: "10",
  deal_or_warrant_prc: "5억",
  area2_m2: 84,
  area2_pyeong: 25.4,
  direction: "남향",
  numeric_price: 50000,
  article_real_estate_type_name: "아파트",
  room_count: 3,
  bathroom_count: 2,
  price_per_pyeong: 1500,
  article_confirm_ymd: "20240101",
};

describe("ArticleTable", () => {
  it("매물 행 렌더링", () => {
    render(<ArticleTable articles={[sampleArticle]} />);
    expect(screen.getByText("101동")).toBeInTheDocument();
  });

  describe("ArticleTable — 추가", () => {
    it("층 정보 표시", () => {
      render(<ArticleTable articles={[sampleArticle]} />);
      expect(screen.getByText("10")).toBeInTheDocument();
    });

    it("가격 표시", () => {
      render(<ArticleTable articles={[sampleArticle]} />);
      expect(screen.getByText("5억")).toBeInTheDocument();
    });

    it("면적 헤더 존재", () => {
      render(<ArticleTable articles={[sampleArticle]} />);
      expect(screen.getByText("면적")).toBeInTheDocument();
    });
  });

  it("거래유형 뱃지 표시", () => {
    render(<ArticleTable articles={[sampleArticle]} />);
    expect(screen.getByText("매매")).toBeInTheDocument();
  });

  it("동일 주소 매물이 여럿이면 원본 집계 배지로 알리고 개별 행은 유지", () => {
    render(<ArticleTable articles={[{ ...sampleArticle, same_addr_cnt: 3 }]} />);
    const badge = screen.getByText("동일주소 3건");
    expect(badge).toHaveAttribute("title", expect.stringContaining("동일 매물로 확정"));
    expect(screen.getAllByRole("row", { name: /매물 A001 상세 보기/ })).toHaveLength(1);
  });

  it("추정 묶음을 펼치면 원본 중개사 매물을 보이고 각각 상세를 열 수 있다", () => {
    const onRow = vi.fn();
    const a1 = { ...sampleArticle, realtor_name: "가중개" };
    const a2 = { ...sampleArticle, article_no: "A002", realtor_name: "나중개" };
    render(<ArticleTable articles={[{ ...a1, group_count: 2, group_members: [a1, a2] }]} onRowClick={onRow} />);
    fireEvent.click(screen.getByRole("button", { name: "추정 묶음 2건 펼치기" }));
    expect(onRow).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /원본 매물 A002/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /원본 매물 A002/ }));
    expect(onRow).toHaveBeenCalledWith("A002");
  });

  it("펼친 원본 체크 상태는 대표 매물과 독립이다", () => {
    const a1 = { ...sampleArticle, realtor_name: "가중개" };
    const a2 = { ...sampleArticle, article_no: "A002", realtor_name: "나중개" };
    const onCheck = vi.fn();
    render(<ArticleTable articles={[{ ...a1, group_count: 2, group_members: [a1, a2] }]}
      onSelectionChange={onCheck} selectedArticleNos={new Set(["A002"])} />);
    fireEvent.click(screen.getByRole("button", { name: "추정 묶음 2건 펼치기" }));
    expect(screen.getByRole("checkbox", { name: "묶음 원본 매물 A001 선택" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "묶음 원본 매물 A002 선택" })).toBeChecked();
  });

  it("동일주소 집계가 없거나 1건이면 중복 배지를 표시하지 않는다", () => {
    render(<ArticleTable articles={[sampleArticle, { ...sampleArticle, article_no: "A002", same_addr_cnt: 1 }]} />);
    expect(screen.queryByText(/동일주소/)).not.toBeInTheDocument();
  });

  it("빈 매물 목록 (EmptyState 카피)", () => {
    render(<ArticleTable articles={[]} />);
    expect(
      screen.getByText(/매물이 없어요|매물이 없습니다|결과가 없습니다|No/i)
    ).toBeInTheDocument();
  });

  it("방향 표시", () => {
    render(<ArticleTable articles={[sampleArticle]} />);
    expect(screen.getByText("남향")).toBeInTheDocument();
  });

  it("컬럼 헤더 표시", () => {
    render(<ArticleTable articles={[sampleArticle]} />);
    expect(screen.getByText("거래")).toBeInTheDocument();
    expect(screen.getByText("동")).toBeInTheDocument();
  });

  it("필터 활성 시 필터 초기화 버튼 노출 + 콜백 호출", () => {
    const onReset = vi.fn();
    render(
      <ArticleTable articles={[]} hasActiveFilters onResetFilters={onReset} />
    );
    const btn = screen.getByText("필터 초기화");
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("필터 없을 때는 갱신 안내 표시 (필터 초기화 버튼 없음)", () => {
    render(<ArticleTable articles={[]} />);
    expect(screen.queryByText("필터 초기화")).toBeNull();
    expect(screen.getByText(/데이터 갱신/)).toBeInTheDocument();
  });

  // B-1 Phase 1: 액션 열 (즐겨찾기) 회귀 가드 (메모 폐기 후 즐겨찾기 단독)
  describe("B-1 액션 열 — 즐겨찾기 버튼", () => {
    it("즐겨찾기(☆) 버튼 렌더링", () => {
      render(<ArticleTable articles={[sampleArticle]} />);
      expect(screen.getByLabelText("매물 즐겨찾기 추가")).toBeInTheDocument();
    });

    it("즐겨찾기 클릭 → ★ + 행 onClick 차단", () => {
      const onRow = vi.fn();
      render(<ArticleTable articles={[sampleArticle]} onRowClick={onRow} />);
      fireEvent.click(screen.getByLabelText("매물 즐겨찾기 추가"));
      expect(screen.getByText("★")).toBeInTheDocument();
      expect(onRow).not.toHaveBeenCalled();
    });

    it("complex_name optional 누락 시 graceful (button 정상 렌더)", () => {
      const noName: Article = { ...sampleArticle, complex_name: undefined };
      render(<ArticleTable articles={[noName]} />);
      expect(screen.getByLabelText("매물 즐겨찾기 추가")).toBeInTheDocument();
    });

    it("행 클릭 → onRowClick 정상 동작 (액션 열 외부)", () => {
      const onRow = vi.fn();
      render(<ArticleTable articles={[sampleArticle]} onRowClick={onRow} />);
      fireEvent.click(screen.getByText("101동"));
      expect(onRow).toHaveBeenCalledWith("A001");
    });
  });

  // PR 4d-1: react-table 도입 후 정렬 토글 회귀 가드
  describe("PR 4d-1 — react-table 정렬 토글", () => {
    it("SERVER_SORT_MAP 컬럼 (가격) 헤더 클릭 → onSortChange('price_asc') 호출", () => {
      const onSortChange = vi.fn();
      render(
        <ArticleTable articles={[sampleArticle]} onSortChange={onSortChange} />
      );
      const priceHeader = screen.getByRole("button", { name: /가격/ });
      fireEvent.click(priceHeader);
      expect(onSortChange).toHaveBeenCalledWith("price_asc");
    });

    it("미매핑 컬럼 (방향) 헤더 클릭 → onSortChange 미호출 + 정렬 인디케이터 ▲ 표시", () => {
      const onSortChange = vi.fn();
      render(
        <ArticleTable articles={[sampleArticle]} onSortChange={onSortChange} />
      );
      const directionHeader = screen.getByRole("button", { name: /방향/ });
      fireEvent.click(directionHeader);
      expect(onSortChange).not.toHaveBeenCalled();
      expect(screen.getByText("▲")).toBeInTheDocument();
    });
  });
});
