/**
 * analytics 래퍼 에러 전파 가드 (세션 298) — getPriceStats/getPriceHistory/getPyeongDetails 가
 * 실패를 빈 데이터로 삼키면 React Query isError 가 prod 에서 영영 발화하지 않아
 * 모든 retry UI 가 dead code 가 된다 (세션 297 getArticleLive 404 삼킴과 동일 패턴).
 * 실행: npx vitest run src/lib/__tests__/analytics-error.test.ts
 */
import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const API = "http://test-api:8000";

// getStats/getRegions 의 Supabase 폴백 경로 차단 (본 테스트 범위 밖)
vi.mock("@/lib/api-direct", () => ({
  getStatsDirect: vi.fn(),
  getRegionsDirect: vi.fn(),
}));

const server = setupServer(
  http.get(`${API}/api/complexes/ERR/price-stats`, () =>
    HttpResponse.json({ detail: "Server error" }, { status: 500 }),
  ),
  http.get(`${API}/api/complexes/ERR/price-history`, () =>
    HttpResponse.json({ detail: "Server error" }, { status: 500 }),
  ),
  http.get(`${API}/api/complexes/ERR/pyeong-details`, () =>
    HttpResponse.json({ detail: "Server error" }, { status: 500 }),
  ),
  http.get(`${API}/api/complexes/OK/price-stats`, () =>
    HttpResponse.json({ complex_no: "OK", total_articles: 1, by_area: [], by_floor: [] }),
  ),
);

// HAS_BACKEND 가 core.ts 모듈 로드 시점 상수라 env 스텁 후 fresh import 필수
let analytics: typeof import("@/lib/api/analytics");

beforeAll(async () => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", API);
  vi.resetModules();
  analytics = await import("@/lib/api/analytics");
  server.listen({ onUnhandledRequest: "bypass" });
});

afterEach(() => server.resetHandlers());

afterAll(() => {
  server.close();
  vi.unstubAllEnvs();
});

describe("analytics 래퍼 — 실패 시 빈 데이터 삼킴 방지", () => {
  it("getPriceStats: 500 이면 reject 한다 (빈 PriceStats 반환 금지)", async () => {
    await expect(analytics.getPriceStats("ERR")).rejects.toThrow();
  });

  it("getPriceHistory: 500 이면 reject 한다 (빈 items 반환 금지)", async () => {
    await expect(analytics.getPriceHistory("ERR")).rejects.toThrow();
  });

  it("getPriceHistory: 수집 직후 기존 HTTP 캐시를 재사용하지 않는다", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    server.use(http.get(`${API}/api/complexes/OK/price-history`, () =>
      HttpResponse.json({ complex_no: "OK", items: [{ base_month: "202609" }] }),
    ));
    try {
      await expect(analytics.getPriceHistory("OK")).resolves.toMatchObject({ complex_no: "OK" });
      expect(fetchSpy).toHaveBeenCalledWith(
        `${API}/api/complexes/OK/price-history`,
        expect.objectContaining({ cache: "no-store" }),
      );
    } finally {
      fetchSpy.mockRestore();
    }
  });

  it("getPyeongDetails: 500 이면 reject 한다 (빈 pyeong_details 반환 금지)", async () => {
    await expect(analytics.getPyeongDetails("ERR")).rejects.toThrow();
  });

  it("getPriceStats: 정상 응답은 그대로 반환한다", async () => {
    await expect(analytics.getPriceStats("OK")).resolves.toMatchObject({ complex_no: "OK" });
  });
});
