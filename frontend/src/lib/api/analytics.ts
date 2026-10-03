/**
 * 통계/분석 API (DB 통계, 지역, 면적, 가격)
 */

import type { DbStats, Regions, PyeongDetail, PriceStats, PriceHistoryResponse, TradePointsResponse } from "@/types";
import * as direct from "@/lib/api-direct";
import { fetchApi, isBackendAvailable } from "./core";

/** DB 통계 */
export async function getStats() {
  if (!isBackendAvailable()) return direct.getStatsDirect();
  try {
    return await fetchApi<DbStats>(`/api/stats`);
  } catch {
    return direct.getStatsDirect();
  }
}

/** 지역 목록 */
export async function getRegions() {
  if (!isBackendAvailable()) return direct.getRegionsDirect();
  try {
    return await fetchApi<Regions>(`/api/regions`);
  } catch {
    return direct.getRegionsDirect();
  }
}

// ⚠ 아래 3개(getPyeongDetails/getPriceStats/getPriceHistory)는 에러를 빈 데이터로 삼키지 말 것 —
// 삼키면 React Query isError 가 prod 에서 영영 발화하지 않아 모든 retry UI 가 dead code 가 된다
// (회귀 가드: lib/__tests__/analytics-error.test.ts).
const BACKEND_DOWN_MSG = "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.";

/** Authorization 헤더 옵션 생성 (B2 게이트: 승인 중개사 전용 엔드포인트용) */
function authOpts(accessToken?: string) {
  return accessToken ? { headers: { Authorization: `Bearer ${accessToken}` } } : undefined;
}

/** 면적별 상세 (B2 게이트 — accessToken 전달) */
export async function getPyeongDetails(complexNo: string, accessToken?: string) {
  if (!isBackendAvailable()) throw new Error(BACKEND_DOWN_MSG);
  return fetchApi<{ pyeong_details: PyeongDetail[] }>(`/api/complexes/${encodeURIComponent(complexNo)}/pyeong-details`, authOpts(accessToken));
}

/** 가격 통계 (면적별/층수별, 거래유형 구분 포함) — B2 게이트 */
export async function getPriceStats(complexNo: string, accessToken?: string) {
  if (!isBackendAvailable()) throw new Error(BACKEND_DOWN_MSG);
  return fetchApi<PriceStats>(`/api/complexes/${encodeURIComponent(complexNo)}/price-stats`, authOpts(accessToken));
}

/** 단지 가격 추이 (실거래가 + 시세) — B2 게이트 */
export async function getPriceHistory(complexNo: string, tradeType?: string, areaNo?: string, accessToken?: string) {
  if (!isBackendAvailable()) throw new Error(BACKEND_DOWN_MSG);
  const params = new URLSearchParams();
  if (tradeType) params.set("trade_type", tradeType);
  if (areaNo) params.set("area_no", areaNo);
  const qs = params.toString();
  return fetchApi<PriceHistoryResponse>(`/api/complexes/${encodeURIComponent(complexNo)}/price-history${qs ? `?${qs}` : ""}`, { ...authOpts(accessToken), cache: "no-store" });
}

/** 단지 개별 실거래 점 (거래 1건 = 점 1건) — B2 게이트 */
export async function getTradePoints(complexNo: string, tradeType?: string, area2M2?: number, accessToken?: string) {
  if (!isBackendAvailable()) throw new Error(BACKEND_DOWN_MSG);
  const params = new URLSearchParams();
  if (tradeType) params.set("trade_type", tradeType);
  if (area2M2 != null) params.set("area2_m2", String(area2M2));
  const qs = params.toString();
  return fetchApi<TradePointsResponse>(`/api/complexes/${encodeURIComponent(complexNo)}/trade-points${qs ? `?${qs}` : ""}`, { ...authOpts(accessToken), cache: "no-store" });
}
