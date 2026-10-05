/**
 * 단지 비교 페이지 silent failure 회귀 가드
 * 실행: npx vitest run src/app/__tests__/compare.test.tsx
 *
 * 검증 시나리오:
 * - partial failure: 4개 중 2개 단지 API 실패 → 배너 + 헤더 "(2개 단지 / 선택 4개)"
 * - 전체 fail: 모든 단지 API 실패 → 본문 대체 안내 + 재시도 버튼
 * - 평당가 statsQueries 1개 fail → 해당 단지 평당가 셀에 "불러오기 실패" 표시
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ComparePage from "../compare/page";
import { TestQueryProvider } from "@/test-setup";
import * as api from "@/lib/api";

const mockPush = vi.fn();
const mockSearchParams = vi.fn(() => new URLSearchParams());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => mockSearchParams(),
}));

vi.mock("@/components/CompareCharts", () => ({
  default: () => <div data-testid="compare-charts" />,
}));

function makeComplex(no: string) {
  return {
    complex_no: no,
    complex_name: `단지${no}`,
    address: "서울 강남",
    total_household_count: 500,
    total_dong_count: 5,
    high_floor: 30,
    low_floor: 1,
    parking_count_by_household: 1.2,
    floor_area_ratio: "250",
    building_coverage_ratio: "20",
    jeonse_rate: 67.7, // BE 저장 단위 = 퍼센트 (crawler/stats.py = jeonse/sale*100)
  };
}

function makeStats(no: string) {
  return {
    complex_no: no,
    total_articles: 1,
    by_area: [],
    by_floor: [],
  };
}

vi.mock("@/lib/api", () => ({
  getComplex: vi.fn().mockImplementation((no: string) => Promise.resolve(makeComplex(no))),
  getPriceStats: vi.fn().mockImplementation((no: string) => Promise.resolve(makeStats(no))),
}));

function renderPage(params = "") {
  mockSearchParams.mockReturnValue(new URLSearchParams(params));
  return render(
    <TestQueryProvider>
      <ComparePage />
    </TestQueryProvider>,
  );
}

describe("단지 비교 — 에러 분기", () => {
  beforeEach(() => {
    mockPush.mockClear();
    // 정상 케이스 복원
    vi.mocked(api.getComplex).mockImplementation((no: string) => Promise.resolve(makeComplex(no)));
    vi.mocked(api.getPriceStats).mockImplementation((no: string) => Promise.resolve(makeStats(no)));
  });

  it("4개 중 2개 fail 시 배너 + 헤더 count 가 표시된다", async () => {
    vi.mocked(api.getComplex).mockImplementation((no: string) =>
      no === "B" || no === "D"
        ? Promise.reject(new Error("backend down"))
        : Promise.resolve(makeComplex(no)),
    );
    renderPage("ids=A,B,C,D");
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("2개 단지 정보를 불러오지 못했습니다.");
    });
    expect(screen.getByText(/2개 단지.*\/ 선택 4개/)).toBeInTheDocument();
  });

  it("전체 fail 시 본문 대체 안내 + 재시도 버튼이 표시된다", async () => {
    vi.mocked(api.getComplex).mockImplementation(() =>
      Promise.reject(new Error("backend down")),
    );
    renderPage("ids=A,B");
    await waitFor(() => {
      expect(screen.getByText("비교 단지 정보를 불러오지 못했습니다.")).toBeInTheDocument();
    });
    expect(screen.getByText("다시 시도")).toBeInTheDocument();
  });

  it("statsQueries 1개 fail 시 평당가 셀에 '불러오기 실패' 가 표시된다", async () => {
    vi.mocked(api.getPriceStats).mockImplementation((no: string) =>
      no === "A"
        ? Promise.reject(new Error("stats fail"))
        : Promise.resolve(makeStats(no)),
    );
    renderPage("ids=A,B");
    await waitFor(() => {
      expect(screen.getByText("불러오기 실패")).toBeInTheDocument();
    });
  });

  it("전세가율은 BE 퍼센트값을 그대로 표시 (×100 이중적용 회귀 차단)", async () => {
    // 세션278 발견: BE jeonse_rate=67.7(퍼센트)인데 compare 가 ×100 → 6770% 오표시.
    // makeComplex jeonse_rate:67.7 → toFixed(0) = "68%" 기대, "6770%" 절대 금지.
    renderPage("ids=A,B");
    await waitFor(() => {
      expect(screen.getAllByText("68%").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryByText("6770%")).toBeNull();
  });

  it("결과 헤더의 '다른 단지 검색' 버튼 클릭 시 /search 로 이동한다 (세션294)", async () => {
    const user = userEvent.setup();
    renderPage("ids=A,B");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "다른 단지 검색" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "다른 단지 검색" }));
    expect(mockPush).toHaveBeenCalledWith("/search");
  });

  it("평당가 행이 '건폐율' 바로 다음에 삽입된다 (findIndex 위치 가드 — 세션287)", async () => {
    // 매직넘버 splice(17) → findIndex('건폐율')+1 교체. BASE_ROWS 순서가 바뀌어도
    // 평당가가 건폐율 다음에 오는지 행 라벨 순서로 가드. (데스크톱 테이블 좌측 라벨 th)
    renderPage("ids=A,B");
    await waitFor(() => {
      expect(screen.getAllByText("68%").length).toBeGreaterThanOrEqual(1);
    });
    // 데스크톱 테이블 행의 좌측 라벨(첫 셀) 텍스트를 순서대로 수집
    const labelCells = Array.from(
      document.querySelectorAll("table tbody tr th:first-child, table tbody tr td:first-child"),
    ).map((el) => el.textContent?.trim() ?? "");
    const bcrIdx = labelCells.indexOf("건폐율");
    expect(bcrIdx).toBeGreaterThanOrEqual(0);
    expect(labelCells[bcrIdx + 1]).toBe("평당가");
  });

  it("비교 표에 '최근 6개월 거래' 줄이 없고 매물수 줄은 남는다 (세션 429 — 시세 기록 줄 수를 거래로 보이던 것)", async () => {
    renderPage("ids=A,B");
    await waitFor(() => {
      expect(screen.getAllByText("68%").length).toBeGreaterThanOrEqual(1);
    });
    const labelCells = Array.from(
      document.querySelectorAll("table tbody tr th:first-child, table tbody tr td:first-child"),
    ).map((el) => el.textContent?.trim() ?? "");
    expect(labelCells).toContain("매물수");
    expect(labelCells).not.toContain("최근 6개월 거래");
    expect(screen.queryByText("최근 6개월 거래")).toBeNull();
  });
});

describe("모바일 비교 화면 tablist (Radix Tabs, PR 5b)", () => {
  // PR 5b: raw <div role="tablist"> + <button role="tab"> → shadcn Tabs (Radix) 교체
  // F-mock 정정: renderPage("ids=A,B") 호출이 mockSearchParams 세팅 (기존 답습)
  // F7 정정: jsdom 은 md:hidden/hidden md:block CSS 무시 → desktop·mobile DOM 둘 다 존재
  //          → getByText("난방") 가 desktop 셀에 항상 매칭되어 모바일 탭 미전환도 PASS 위험
  //          → getAllByText.length 카운트 단언으로 차단

  it("초기 활성 탭 = 기본 (data-state=active), 다른 탭 inactive", async () => {
    // 검증 의도: Radix Tabs controlled mode 에서 value="basic" 이 정확히 활성, 가격/시설 inactive
    renderPage("ids=A,B");
    expect(await screen.findByRole("tab", { name: "기본" })).toHaveAttribute("data-state", "active");
    expect(screen.getByRole("tab", { name: "가격" })).toHaveAttribute("data-state", "inactive");
    expect(screen.getByRole("tab", { name: "시설" })).toHaveAttribute("data-state", "inactive");
  });

  it("탭 클릭 시 mobileRows 가 실제 변경 (시설 → 난방 등장 + 주소 사라짐)", async () => {
    // 검증 의도: ROW_CATEGORIES.facility 의 "난방" 등장 + ROW_CATEGORIES.basic 의 "주소" 사라짐 양방향 검증
    // F7: jsdom 은 CSS 무시 → desktop <td>"주소"·"난방" 항상 매칭 → 카운트로 모바일 영역 변경 검증
    // 초기(basic): desktop "난방" 1 + mobile dl "난방" 0 = 1건 / desktop "주소" 1 + mobile dl "주소" 1 = 2건
    // 시설 클릭 후: desktop "난방" 1 + mobile dl "난방" 1 (단지 1개) = 2건 / "주소" mobile dl 사라짐 = 1건
    const user = userEvent.setup();
    renderPage("ids=A,B");
    await user.click(await screen.findByRole("tab", { name: "시설" }));
    // F-it2 정정: 양방향 검증 (등장 + 사라짐 카운트로 silent failure 차단)
    await waitFor(() => {
      expect(screen.getAllByText("난방").length).toBeGreaterThanOrEqual(2);
    });
    expect(screen.getAllByText("주소").length).toBe(1);
  });

  it("키보드 ArrowRight 로 다음 탭 활성화 + 이전 탭 inactive (Radix roving focus)", async () => {
    // 검증 의도: Radix Tabs roving focus = ArrowRight 키 → 다음 TabsTrigger 활성 + 이전 deactive
    const user = userEvent.setup();
    renderPage("ids=A,B");
    const basicTab = await screen.findByRole("tab", { name: "기본" });
    basicTab.focus();
    await user.keyboard("{ArrowRight}");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "가격" })).toHaveAttribute("data-state", "active");
    });
    expect(basicTab).toHaveAttribute("data-state", "inactive");
  });

  it("TabsList className 머지 (w-full + sticky 영역 폭 보존)", async () => {
    // 검증 의도: TabsList 기본 w-fit 을 w-full 로 override + sticky z-10 보존 (F6·F-it4 정정)
    // top-14 = 전역 Header(sticky top-0 z-50 h-14) 아래에 고정 — top-0 이면 헤더에 가려져
    // 핀 상태에서 보이지도 눌리지도 않음 (세션 295, AdminLivePanel top-20 선례)
    renderPage("ids=A,B");
    const tablist = await screen.findByRole("tablist", { name: "비교 항목 분류" });
    expect(tablist).toHaveClass("w-full", "sticky", "top-14", "z-10");
  });
});

describe("인쇄 silent failure 가드 (PR 5c)", () => {
  // PR 5c: 모바일 viewport (< 768px) 에서 인쇄 시 데스크톱 테이블 강제 표시.
  // 현재 = 모바일 카드의 활성 탭 행 (basic=10·price=5·facility=9) 만 인쇄됨 (24행 약속 깨짐).
  // 정정 = globals.css @media print 안에서 .print-show-md/.print-hide-md 룰로 데스크톱 테이블 표시 + 모바일 카드 숨김.
  // jsdom 은 @media print 평가 0 + getComputedStyle 무력 → className 부착만 단언.
  // 진짜 인쇄 시뮬 검증은 Playwright emulateMedia("print") 별도 PR (silent-failure F3 박제).

  it("데스크톱 테이블 wrapper 에 print-show-md 클래스 부착", async () => {
    // 검증 의도: @media print 룰 발화 시 모바일 viewport 에서도 데스크톱 테이블 24행 전체 출력 보장
    renderPage("ids=A,B");
    const table = await screen.findByRole("table");
    const wrapper = table.closest("div.hidden.md\\:block");
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveClass("print-show-md");
  });

  it("모바일 카드 wrapper 에 print-hide-md 클래스 부착", async () => {
    // 검증 의도: @media print 룰 발화 시 모바일 카드 영역 숨김 → 데스크톱 테이블과 중복 출력 방지
    renderPage("ids=A,B");
    const tablist = await screen.findByRole("tablist", { name: "비교 항목 분류" });
    const wrapper = tablist.closest("div.md\\:hidden");
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveClass("print-hide-md");
  });
});
