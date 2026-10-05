"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPriceWatchBasket, getPriceWatchTargets, getPriceWatchUnits } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { useSessionToken } from "@/hooks/useSessionToken";
import LoadingSpinner from "@/components/LoadingSpinner";
import LockedDataCard, { isAuthGateError } from "@/components/ui/locked-data-card";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TargetManager from "@/components/price-watch/TargetManager";
import UnitChangeTable from "@/components/price-watch/UnitChangeTable";
import BasketTrend from "@/components/price-watch/BasketTrend";
import { formatArea } from "@/components/price-watch/format";

const PERIODS = [
  { days: 30, label: "1개월" },
  { days: 90, label: "3개월" },
  { days: 180, label: "6개월" },
  { days: 365, label: "1년" },
];

function ErrorBox({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="py-6 text-center text-sm">
      <p className="text-red-600">불러오지 못했어요: {error.message}</p>
      <button type="button" onClick={onRetry} className="mt-2 px-3 py-1 rounded-md border border-gray-300">
        다시 시도
      </button>
    </div>
  );
}

/**
 * 관심 단지 매매호가 추적 (V069) — ① 동일 매물(추정) 변동률 ② 여러 단지 평균 변동률.
 * 기록은 관심 단지 매물 수집이 끝까지 성공할 때마다 하루 1번씩 쌓인다(BE services/price_watch.py).
 */
export default function PriceWatchPage() {
  const { sessionToken, tokenReady } = useSessionToken();
  const [days, setDays] = useState(90);
  const [excluded, setExcluded] = useState<Set<number>>(new Set());

  const targetsQ = useQuery({
    queryKey: queryKeys.priceWatchTargets,
    queryFn: () => getPriceWatchTargets(sessionToken!),
    enabled: tokenReady && !!sessionToken,
  });
  const targets = useMemo(() => targetsQ.data?.targets ?? [], [targetsQ.data]);
  const selectedIds = useMemo(() => targets.filter((t) => !excluded.has(t.id)).map((t) => t.id), [targets, excluded]);
  const idsKey = selectedIds.join(",");
  const analysisEnabled = !!sessionToken && selectedIds.length > 0;

  const unitsQ = useQuery({
    queryKey: queryKeys.priceWatchUnits(days, idsKey),
    queryFn: () => getPriceWatchUnits(sessionToken!, days, selectedIds),
    enabled: analysisEnabled,
  });
  const basketQ = useQuery({
    queryKey: queryKeys.priceWatchBasket(days, idsKey),
    queryFn: () => getPriceWatchBasket(sessionToken!, days, selectedIds),
    enabled: analysisEnabled,
  });

  const header = (
    <div className="mb-4">
      <h1 className="text-xl font-bold text-gray-900">관심 단지 호가 추적</h1>
      <p className="mt-1 text-sm text-gray-600">
        단지와 평형을 등록하면 매일 매매호가를 기록해, 같은 집의 호가가 얼마나 내리고 올랐는지와 여러 단지 평균 호가의 변동률을 보여드려요.
      </p>
    </div>
  );

  if (!tokenReady || (sessionToken && targetsQ.isLoading)) {
    return <div className="max-w-6xl mx-auto px-4 py-6">{header}<LoadingSpinner /></div>;
  }
  if (!sessionToken || (targetsQ.isError && isAuthGateError(targetsQ.error))) {
    return <div className="max-w-6xl mx-auto px-4 py-6">{header}<LockedDataCard label="호가 추적" /></div>;
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
      {header}
      {targetsQ.isError ? (
        <Card className="p-4"><ErrorBox error={targetsQ.error} onRetry={() => targetsQ.refetch()} /></Card>
      ) : (
        <TargetManager token={sessionToken} targets={targets} maxTargets={targetsQ.data?.max_targets ?? 20} />
      )}

      {targets.length > 0 && (
        <Card className="p-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex gap-1" role="group" aria-label="분석 기간">
              {PERIODS.map((p) => (
                <button
                  key={p.days}
                  type="button"
                  aria-pressed={days === p.days}
                  onClick={() => setDays(p.days)}
                  className={`px-3 py-1 text-xs rounded-full border ${days === p.days
                    ? "bg-gray-900 text-white border-gray-900" : "border-gray-300 text-gray-700"}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <fieldset className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <legend className="text-xs text-gray-500 mb-1">분석에 넣을 단지·평형</legend>
            {targets.map((t) => (
              <label key={t.id} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={!excluded.has(t.id)}
                  onChange={() => setExcluded((prev) => {
                    const next = new Set(prev);
                    if (next.has(t.id)) next.delete(t.id); else next.add(t.id);
                    return next;
                  })}
                />
                {t.complex_name ?? t.complex_no} <span className="text-xs text-gray-500">{formatArea(t.area_m2, t.pyeong)}</span>
              </label>
            ))}
          </fieldset>

          {selectedIds.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-500">분석할 단지를 하나 이상 골라 주세요.</p>
          ) : (
            <Tabs defaultValue="units">
              <TabsList>
                <TabsTrigger value="units">같은 집 호가 변동</TabsTrigger>
                <TabsTrigger value="basket">단지 묶음 평균 변동</TabsTrigger>
              </TabsList>
              <TabsContent value="units" className="pt-3">
                {unitsQ.isLoading && <LoadingSpinner />}
                {unitsQ.isError && <ErrorBox error={unitsQ.error} onRetry={() => unitsQ.refetch()} />}
                {unitsQ.data && <UnitChangeTable data={unitsQ.data} />}
              </TabsContent>
              <TabsContent value="basket" className="pt-3">
                {basketQ.isLoading && <LoadingSpinner />}
                {basketQ.isError && <ErrorBox error={basketQ.error} onRetry={() => basketQ.refetch()} />}
                {basketQ.data && <BasketTrend data={basketQ.data} />}
              </TabsContent>
            </Tabs>
          )}
          <p className="text-xs text-gray-400">
            기록은 관심 단지의 매물 수집이 끝까지 성공할 때마다 하루 한 번씩 쌓여요(하루 3번 갱신 순번에서 관심 단지를 먼저 챙깁니다). 등록한 날부터 쌓이므로 변동률은 며칠이 지나야 보이기 시작해요.
          </p>
        </Card>
      )}
    </div>
  );
}
