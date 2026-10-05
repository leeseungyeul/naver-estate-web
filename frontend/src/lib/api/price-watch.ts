/**
 * 관심 단지 매매호가 추적 API — BE routers/price_watch.py 짝꿍 (승인 사용자 전용, 네이버 호출 0)
 * ⚠ 에러 삼킴 금지(error-propagation.md) — 실패는 그대로 throw 해 화면의 isError 로 보낸다.
 */
import type {
  PriceWatchAreasResponse,
  PriceWatchBasketResponse,
  PriceWatchTarget,
  PriceWatchTargetsResponse,
  PriceWatchUnitsResponse,
} from "@/types/price-watch";
import { adminHeaders, fetchApi, isBackendAvailable } from "./core";

const BACKEND_DOWN_MSG = "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.";

function guard() {
  if (!isBackendAvailable()) throw new Error(BACKEND_DOWN_MSG);
}

function analysisQuery(days: number, targetIds?: number[]): string {
  const params = new URLSearchParams({ days: String(days) });
  if (targetIds && targetIds.length > 0) params.set("target_ids", targetIds.join(","));
  return params.toString();
}

export async function getPriceWatchTargets(token: string): Promise<PriceWatchTargetsResponse> {
  guard();
  return fetchApi<PriceWatchTargetsResponse>("/api/price-watch/targets", { headers: adminHeaders(token) });
}

export async function addPriceWatchTarget(
  token: string,
  body: { complex_no: string; area_m2: number | null; label?: string },
): Promise<PriceWatchTarget & { initial_recorded: number }> {
  guard();
  return fetchApi("/api/price-watch/targets", {
    method: "POST",
    headers: { ...adminHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deletePriceWatchTarget(token: string, id: number): Promise<{ deleted: number }> {
  guard();
  return fetchApi(`/api/price-watch/targets/${id}`, { method: "DELETE", headers: adminHeaders(token) });
}

export async function getPriceWatchAreas(token: string, complexNo: string): Promise<PriceWatchAreasResponse> {
  guard();
  return fetchApi<PriceWatchAreasResponse>(
    `/api/price-watch/complexes/${encodeURIComponent(complexNo)}/areas`,
    { headers: adminHeaders(token) },
  );
}

export async function getPriceWatchUnits(
  token: string, days: number, targetIds?: number[],
): Promise<PriceWatchUnitsResponse> {
  guard();
  return fetchApi<PriceWatchUnitsResponse>(
    `/api/price-watch/units?${analysisQuery(days, targetIds)}`,
    { headers: adminHeaders(token) },
  );
}

export async function getPriceWatchBasket(
  token: string, days: number, targetIds?: number[],
): Promise<PriceWatchBasketResponse> {
  guard();
  return fetchApi<PriceWatchBasketResponse>(
    `/api/price-watch/basket?${analysisQuery(days, targetIds)}`,
    { headers: adminHeaders(token) },
  );
}
