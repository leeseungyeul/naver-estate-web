/**
 * 정렬 변경이 렌더 중 라우터 갱신을 유발하지 않음 (React setstate-in-render 회귀 가드)
 *
 * dev 서버 로그의 "Cannot update a component (`Router`) while rendering a different
 * component (`ArticleTable`)" 원인: handleSortingChange 가 setSorting updater 함수
 * 내부에서 onSortChange(→ router.replace)를 호출. updater는 렌더/반복 중 실행될 수
 * 있어 부수효과를 넣으면 안 된다.
 *
 * 실행: npx vitest run src/components/__tests__/ArticleTable-render-guard.test.tsx
 */
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import ArticleTable from "../ArticleTable";
import type { Article } from "@/types";

const base: Article = {
  article_no: "A1",
  complex_no: "C1",
  trade_type_name: "매매",
  building_name: "101동",
  numeric_price: 50000,
  area2_m2: 84,
  article_real_estate_type_name: "아파트",
};

describe("ArticleTable 정렬 부수효과 가드", () => {
  it("마운트(렌더) 중 onSortChange/router 갱신을 호출하지 않는다", () => {
    const onSortChange = vi.fn();
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      render(
        <ArticleTable
          articles={[base, { ...base, article_no: "A2", building_name: "102동" }]}
          onSortChange={onSortChange}
        />
      );
      // 렌더 완료 시점까지 정렬 콜백·React 경고가 없어야 한다
      expect(onSortChange).not.toHaveBeenCalled();
      const setStateInRender = spy.mock.calls
        .flat()
        .join("\n")
        .includes("Cannot update a component");
      expect(setStateInRender).toBe(false);
    } finally {
      spy.mockRestore();
    }
  });
});
