/**
 * 정보 위계 회귀 가드 (PR 3a 신설 + PR 6d 데스크톱 통합 후 갱신)
 *
 * PR 6d 이후 = 데스크톱 시세·차트·단지정보 3 섹션이 ComplexDashboard 박스 4 안으로 흡수.
 * 페이지 H2 = "매물" 1개만. 박스 4 라벨 (시세·실거래가·단지정보·면적별 시세) + 매물 섹션이
 * 새로운 위계.
 *
 * e2e 환경은 BE 단지 데이터가 없으면 ComplexLoadState 상태에 머물러 렌더가 안 나옴.
 * 따라서 useQuery mock 으로 vitest 통합 테스트.
 *
 * 실행: npx vitest run src/app/complex/[no]/__tests__/page-hierarchy.test.tsx
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { TestQueryProvider } from "@/test-setup";

// 모든 API 모킹 — 단지/매물/면적/시세 fresh 응답
vi.mock("@/lib/api", () => ({
  getComplex: vi.fn().mockResolvedValue({
    complex_no: "12345",
    complex_name: "테스트단지",
    real_estate_type_name: "아파트",
    address: "서울시 강남구",
    total_household_count: 500,
    filter_options: {},
  }),
  getArticles: vi.fn().mockResolvedValue({ articles: [], total: 0 }),
  getPyeongDetails: vi.fn().mockResolvedValue({ pyeong_details: [] }),
  getPriceStats: vi.fn().mockResolvedValue({
    complex_no: "12345", total_articles: 0, by_area: [], by_floor: [],
  }),
  getPriceHistory: vi.fn().mockResolvedValue({ complex_no: "12345", items: [] }),
  startPriceCollect: vi.fn().mockResolvedValue({ complex_no: "12345", status: "fresh" }),
  getPriceCollectStatus: vi.fn().mockResolvedValue({
    complex_no: "12345", status: "idle", collected: 0, failed: 0, total: 0,
  }),
}));

// next/navigation: useParams override
vi.mock("next/navigation", async () => {
  const actual = await vi.importActual<typeof import("next/navigation")>("next/navigation");
  return {
    ...actual,
    useParams: () => ({ no: "12345" }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
    usePathname: () => "/complex/12345",
    useSearchParams: () => new URLSearchParams(),
  };
});

// useCrawlAction · useExport · useFilterParams · useFavorites · useSmartBack mock
vi.mock("@/hooks/useCrawlAction", () => ({
  useCrawlAction: () => ({
    crawling: false, message: "", messageType: "", progress: null,
    clearMessage: vi.fn(), handleCrawl: vi.fn(),
  }),
}));
vi.mock("@/hooks/useExport", () => ({
  useExport: () => ({
    exporting: false, exportError: "", clearExportError: vi.fn(), handleExport: vi.fn(),
  }),
}));
vi.mock("@/hooks/useFilterParams", () => ({
  useFilterParams: () => ({
    filters: {}, page: 1, sortBy: "", setFilters: vi.fn(), setPage: vi.fn(), setSortBy: vi.fn(),
  }),
}));
vi.mock("@/hooks/useFavorites", () => ({
  useFavoriteStatus: () => ({ starred: false, toggle: vi.fn() }),
}));
vi.mock("@/hooks/useSmartBack", () => ({
  useSmartBack: () => vi.fn(),
}));
vi.mock("@/hooks/useSessionToken", () => ({
  useSessionToken: () => ({
    sessionToken: undefined,
    tokenReady: true,
    tokenError: false,
    dismissTokenError: vi.fn(),
  }),
}));
vi.mock("@/hooks/useArticleViewPreferences", () => ({
  useArticleViewPreferences: () => ({
    articleViewMode: "medium",
    pageSize: 10,
    setPageSize: vi.fn(),
    handleViewModeChange: vi.fn(),
  }),
}));
vi.mock("@/hooks/usePopstateRefresh", () => ({
  usePopstateRefresh: () => ({ navKey: 0 }),
}));

import ComplexDetailPage from "../page";

function renderPage() {
  return render(<ComplexDetailPage />, { wrapper: TestQueryProvider });
}

describe("ComplexDetailPage 정보 위계 (PR 6d 데스크톱 통합 후)", () => {
  it("H2 1개 (매물) + ComplexDashboard 박스 4개 (시세·실거래가·단지정보·면적별 시세) 렌더링", async () => {
    renderPage();
    await waitFor(() => {
      // H2 = 매물 1개만 (시세·차트·단지정보 3 섹션은 박스 4 안으로 흡수)
      const h2s = screen.getAllByRole("heading", { level: 2 });
      const texts = h2s.map(h => h.textContent);
      expect(texts).toEqual(["매물"]);

      // 박스 4 = aria-label "단지 종합 대시보드" 안의 4 button (시세·실거래가·단지정보·면적별 시세)
      const dashboard = screen.getByLabelText("단지 종합 대시보드");
      const boxButtons = dashboard.querySelectorAll('button[aria-controls="dashboard-content"]');
      expect(boxButtons).toHaveLength(4);
      const labels = Array.from(boxButtons).map(b => b.getAttribute("aria-label"));
      expect(labels).toEqual([
        "시세 메뉴 열기",
        "실거래가 메뉴 열기",
        "단지정보 메뉴 열기",
        "면적별 시세 메뉴 열기",
      ]);
    });
  });

  it("모바일 필터 시트 트리거가 매물 섹션에 임베드 (PR 3b 회귀 가드)", async () => {
    renderPage();
    await waitFor(() => {
      const trigger = screen.getByRole("button", { name: /필터 창 열기/ });
      expect(trigger).toBeInTheDocument();
    });
  });

  it("PR 4e-3: ArticlePageSizeSelect 가 데스크톱·모바일 양쪽에 렌더된다 (빈 결과 시에도 노출)", async () => {
    renderPage();
    await waitFor(() => {
      // 데스크톱 1개 + 모바일 1개 = 2개 인스턴스 (articles.length=0 인 빈 결과 상태에서도 노출)
      const selects = screen.getAllByLabelText("한 페이지당 매물 개수");
      expect(selects.length).toBe(2);
    });
  });

  it("PR 4e-3: 셀렉트 초기값 = localStorage default 10", async () => {
    renderPage();
    await waitFor(() => {
      // 화면에 "10개" 텍스트가 SelectValue 슬롯에 표시 — 데스크톱·모바일 둘 다
      const tens = screen.getAllByText("10개");
      expect(tens.length).toBeGreaterThanOrEqual(2);
    });
  });
});

describe("매물 묶음 총계 (원본 건수는 별도 보존)", () => {
  it("기본은 추정 묶음 수를 표시하고 원본 보기로 전환한다", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.getArticles).mockImplementation(async (_no, _filters, _token, grouped) =>
      grouped
        ? { articles: [], total: 21, raw_total: 75, page: 1, page_size: 10 }
        : { articles: [], total: 75, page: 1, page_size: 10 });
    try {
      renderPage();
      await waitFor(() => expect(screen.getByText("추정 묶음 21개 · 원본 등록 75건")).toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: "원본 매물 보기" }));
      await waitFor(() => expect(screen.getByText("원본 등록 75건")).toBeInTheDocument());
      expect(vi.mocked(api.getArticles)).toHaveBeenCalledWith("12345", expect.any(Object), undefined, false);
    } finally {
      vi.mocked(api.getArticles).mockResolvedValue({ articles: [], total: 0 } as never);
    }
  });
});

describe("매물 페이지네이션 스크롤 복귀 (세션 295)", () => {
  it("'다음' 페이지 클릭 시 매물 섹션으로 scrollIntoView(auto) 호출", async () => {
    const api = await import("@/lib/api");
    vi.mocked(api.getArticles).mockResolvedValue({ articles: [], total: 25 } as never);
    const scrollSpy = vi.fn();
    // test-setup.ts 폴리필이 HTMLElement.prototype 에 박혀 있어 같은 레벨에서 스파이
    const orig = window.HTMLElement.prototype.scrollIntoView;
    window.HTMLElement.prototype.scrollIntoView = scrollSpy;
    try {
      renderPage();
      const nextBtn = await screen.findByRole("button", { name: "다음" });
      scrollSpy.mockClear();
      fireEvent.click(nextBtn);
      // smooth 는 클릭 직후 리렌더에 취소될 수 있어 auto 고정 (메모리 박제 답습)
      expect(scrollSpy).toHaveBeenCalledWith({ behavior: "auto", block: "start" });
    } finally {
      window.HTMLElement.prototype.scrollIntoView = orig;
      vi.mocked(api.getArticles).mockResolvedValue({ articles: [], total: 0 } as never);
    }
  });
});
