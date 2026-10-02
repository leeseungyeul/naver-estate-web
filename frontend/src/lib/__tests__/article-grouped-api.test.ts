import { beforeAll, afterAll, afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

const API = "http://test-api:8000";
const server = setupServer();
let api: typeof import("@/lib/api/articles");

beforeAll(async () => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", API);
  vi.resetModules();
  api = await import("@/lib/api/articles");
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => server.resetHandlers());
afterAll(() => { server.close(); vi.unstubAllEnvs(); });

describe("grouped listing fetch", () => {
  it("requests server-side groups and preserves raw_total", async () => {
    server.use(http.get(`${API}/api/complexes/17538/articles`, ({ request }) => {
      const params = new URL(request.url).searchParams;
      expect(params.get("group_duplicates")).toBe("true");
      expect(params.get("trade_types")).toBe("매매");
      return HttpResponse.json({ articles: [], total: 21, raw_total: 75, page: 1, page_size: 10 });
    }));
    await expect(api.getArticles("17538", { trade_types: "매매", page: 1, page_size: 10 }, "token", true))
      .resolves.toMatchObject({ total: 21, raw_total: 75 });
  });

  it("grouped request failure must not silently fallback to ungrouped direct list", async () => {
    server.use(http.get(`${API}/api/complexes/17538/articles`, () =>
      HttpResponse.json({ detail: "error" }, { status: 500 })));
    await expect(api.getArticles("17538", {}, "token", true)).rejects.toThrow();
  });
});
