"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { getPriceHistory, getTradePoints } from "@/lib/api";
import { usePriceCollect } from "@/hooks/usePriceCollect";
import { Button } from "@/components/ui/button";
import Skeleton from "@/components/Skeleton";
import LockedDataCard, { isAuthGateError } from "@/components/ui/locked-data-card";
import type { PyeongDetail } from "@/types";

const LazyPriceHistory = dynamic(() => import("@/components/PriceHistoryChart"), { ssr: false });

interface Props {
  complexNo: string;
  pyeongDetails: PyeongDetail[];
  accessToken?: string;
}

/** 실거래가 추이 섹션 — 면적 선택 + 수집 버튼 + 차트 (페이지 진입 시 자동 수집 1회). */
export default function PriceChartSection({ complexNo, pyeongDetails, accessToken }: Props) {
  const queryClient = useQueryClient();
  const [historyAreaNo, setHistoryAreaNo] = useState<string>("");
  const { collecting, message: collectMessage, messageType: collectMessageType, startCollect, clearPolling } = usePriceCollect();

  const priceHistoryQuery = useQuery({
    queryKey: queryKeys.priceHistory(complexNo, undefined, historyAreaNo || undefined),
    queryFn: () => getPriceHistory(complexNo, undefined, historyAreaNo || undefined, accessToken),
    enabled: !!complexNo,
  });

  // 개별 실거래 점 — 실패해도 평균 차트는 유지되어야 하므로 조용히 생략 (retry 없음)
  const tradePointsQuery = useQuery({
    queryKey: queryKeys.tradePoints(complexNo),
    queryFn: () => getTradePoints(complexNo, undefined, undefined, accessToken),
    enabled: !!complexNo,
    retry: false,
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => clearPolling, [clearPolling]);

  // 페이지 진입 시 1회 자동 수집 (24h TTL — 서버 fresh 판단, AdaptiveThrottle 보호)
  const autoCollectRef = useRef<string>("");
  useEffect(() => {
    if (!accessToken || collecting) return;
    if (autoCollectRef.current === complexNo) return;
    autoCollectRef.current = complexNo;
    startCollect(complexNo, accessToken, () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.priceHistoryAll(complexNo) });
    });
  }, [complexNo, accessToken, collecting, startCollect, queryClient]);

  const historyItems = priceHistoryQuery.data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        {pyeongDetails.length > 0 && (
          <select
            value={historyAreaNo}
            onChange={(e) => setHistoryAreaNo(e.target.value)}
            className="text-sm border rounded px-2 py-1.5 text-gray-700"
            aria-label="실거래가 면적 선택"
          >
            <option value="">전체 면적</option>
            {pyeongDetails.map((pd) => (
              <option key={pd.pyeong_no} value={String(pd.pyeong_no)}>
                {pd.pyeong_name ? `${pd.pyeong_name} (${pd.exclusive_area}㎡)` : `${pd.exclusive_area}㎡`}
              </option>
            ))}
          </select>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={collecting || !accessToken}
          onClick={() => {
            if (!accessToken) return;
            startCollect(complexNo, accessToken, () => {
              queryClient.invalidateQueries({ queryKey: queryKeys.priceHistoryAll(complexNo) });
            });
          }}
          className="no-print"
        >
          {collecting ? "수집 중..." : "실거래가 수집"}
        </Button>
        {!accessToken && (
          <span className="text-xs text-gray-400">로그인 후 수집할 수 있습니다</span>
        )}
        {collectMessage && (
          <span className={`text-xs ${
            collectMessageType === "error" ? "text-red-500" :
            collectMessageType === "info" ? "text-blue-600" :
            "text-green-600"
          }`}>
            {collectMessage}
          </span>
        )}
      </div>
      {priceHistoryQuery.isLoading ? (
        <div role="status" aria-label="로딩 중">
          <span className="sr-only">실거래가 추이 로딩 중...</span>
          <Skeleton className="h-72 w-full" />
        </div>
      ) : priceHistoryQuery.isError ? (
        isAuthGateError(priceHistoryQuery.error) ? (
          <LockedDataCard label="실거래가" />
        ) : (
          <div className="text-center py-4">
            <p className="text-red-500 text-sm">가격 추이를 불러오지 못했습니다</p>
            <button
              type="button"
              onClick={() => priceHistoryQuery.refetch()}
              className="text-xs text-blue-600 hover:underline mt-2"
            >
              다시 시도
            </button>
          </div>
        )
      ) : (
        <LazyPriceHistory items={historyItems} tradePoints={tradePointsQuery.data?.points} />
      )}
    </div>
  );
}
