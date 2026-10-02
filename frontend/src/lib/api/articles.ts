/**
 * 매물 조회/내보내기 API
 */

import type { Article, ArticleFilters, ArticlePriceHistoryItem, ArticlesResponse } from "@/types";
import * as direct from "@/lib/api-direct";
import { fetchApi, isBackendAvailable, getApiBase, ApiError } from "./core";

/** 단지별 매물 조회 (B2 게이트: 승인 중개사 전용 — accessToken 전달) */
export async function getArticles(complexNo: string, filters?: ArticleFilters, accessToken?: string, groupDuplicates = false) {
  if (!isBackendAvailable()) {
    if (groupDuplicates) throw new Error("묶음 조회에는 백엔드 연결이 필요합니다.");
    return direct.getArticlesDirect(complexNo, filters as Record<string, string>);
  }
  try {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          params.set(key, String(value));
        }
      });
    }
    if (groupDuplicates) params.set("group_duplicates", "true");
    const qs = params.toString();
    const opts = accessToken ? { headers: { Authorization: "Bearer " + accessToken } } : undefined;
    return await fetchApi<ArticlesResponse>(
      `/api/complexes/${encodeURIComponent(complexNo)}/articles${qs ? `?${qs}` : ""}`,
      opts
    );
  } catch (err) {
    // 401/403 = 인증·승인 권한 답변 — 폴백(api-direct)으로 "조회 실패"로 뭉개면 안 됨
    // (승인 안내 UX 분기 도달용 rethrow, error-propagation.md / getArticleLive 404 패턴 답습)
    if (groupDuplicates) throw err;
    if (err instanceof ApiError && (err.statusCode === 401 || err.statusCode === 403)) throw err;
    return direct.getArticlesDirect(complexNo, filters as Record<string, string>);
  }
}

/** 매물 상세 실시간 (네이버 API 직접 조회 + DB 저장) */
export async function getArticleLive(articleNo: string) {
  if (!isBackendAvailable()) return direct.getArticleDirect(articleNo);
  try {
    return await fetchApi<Article>(`/api/live/article/${encodeURIComponent(articleNo)}/detail`, { timeoutMs: 30_000 } as RequestInit & { timeoutMs?: number });
  } catch (err) {
    // 404 = backend 의 확정 답변 (매물 삭제/내려감) — 장애가 아니므로 폴백 없이 전파 (ArticleDetail 404 분기 짝꿍)
    if (err instanceof ApiError && err.statusCode === 404) throw err;
    return direct.getArticleDirect(articleNo);
  }
}

/** 매물 가격 변동 이력 조회 */
export async function getArticlePriceHistory(articleNo: string) {
  return await fetchApi<{ article_no: string; history: ArticlePriceHistoryItem[] }>(
    `/api/articles/${encodeURIComponent(articleNo)}/price-history`
  );
}

/** 엑셀 다운로드 (현재 필터 적용) */
export async function exportArticles(complexNo: string, filters?: ArticleFilters, accessToken?: string) {
  const params = new URLSearchParams({ complex_no: complexNo });
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        params.set(key, String(value));
      }
    });
  }
  const url = `${getApiBase()}/api/articles/export?${params.toString()}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  const headers: HeadersInit = {};
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  try {
    const res = await fetch(url, { method: "POST", signal: controller.signal, headers });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "엑셀 내보내기 실패");
    }
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `매물_${complexNo}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("엑셀 내보내기 시간이 초과되었습니다");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}
