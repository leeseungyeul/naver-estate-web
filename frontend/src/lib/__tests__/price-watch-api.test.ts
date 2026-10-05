/**
 * 호가 추적 API 래퍼 — 실패를 빈 데이터로 삼키지 않고 reject 하는지(error-propagation.md 룰 3),
 * 분석 요청에 기간·대상 id 가 실리는지 검증한다.
 */
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const API = "http://test-api:8000";
const server = setupServer();
let api: typeof import("@/lib/api/price-watch");

beforeAll(async () => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", API);
  vi.resetModules();
  api = await import("@/lib/api/price-watch");
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => server.resetHandlers());
afterAll(() => { server.close(); vi.unstubAllEnvs(); });

const fail = () => HttpResponse.json({ detail: "error" }, { status: 500 });

describe("price-watch api", () => {
  it("분석 요청에 기간과 대상 id 를 싣는다", async () => {
    server.use(http.get(`${API}/api/price-watch/units`, ({ request }) => {
      const q = new URL(request.url).searchParams;
      expect(q.get("days")).toBe("30");
      expect(q.get("target_ids")).toBe("1,2");
      return HttpResponse.json({ period: {}, summary: { unit_count: 0 }, units: [] });
    }));
    await expect(api.getPriceWatchUnits("t", 30, [1, 2])).resolves.toMatchObject({ units: [] });
  });

  it.each([
    ["targets", () => api.getPriceWatchTargets("t"), "get", "/api/price-watch/targets"],
    ["add", () => api.addPriceWatchTarget("t", { complex_no: "1", area_m2: null }), "post", "/api/price-watch/targets"],
    ["delete", () => api.deletePriceWatchTarget("t", 3), "delete", "/api/price-watch/targets/3"],
    ["areas", () => api.getPriceWatchAreas("t", "1"), "get", "/api/price-watch/complexes/1/areas"],
    ["units", () => api.getPriceWatchUnits("t", 90), "get", "/api/price-watch/units"],
    ["basket", () => api.getPriceWatchBasket("t", 90), "get", "/api/price-watch/basket"],
  ] as const)("%s: 5xx 는 reject 된다", async (_name, call, method, path) => {
    server.use(http[method](`${API}${path}`, fail));
    await expect(call()).rejects.toThrow();
  });
});
