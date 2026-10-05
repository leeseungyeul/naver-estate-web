"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import {
  addPriceWatchTarget, deletePriceWatchTarget, getPriceWatchAreas, searchComplexesDb,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatKoreanPrice } from "@/lib/format";
import { Card } from "@/components/ui/card";
import type { PriceWatchTarget } from "@/types/price-watch";
import { formatArea, formatShortDate } from "./format";

interface Props {
  token: string;
  targets: PriceWatchTarget[];
  maxTargets: number;
}

/** 관심 대상(단지 + 평형) 등록·삭제. 단지 검색은 DB 검색만(네이버 호출 0). */
export default function TargetManager({ token, targets, maxTargets }: Props) {
  const qc = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [picked, setPicked] = useState<{ no: string; name: string } | null>(null);
  const [area, setArea] = useState<number | null>(null);

  const search = useQuery({
    queryKey: queryKeys.complexSearchDb(submitted),
    queryFn: ({ signal }) => searchComplexesDb(submitted, signal, 20),
    enabled: submitted.length >= 2,
  });
  const areas = useQuery({
    queryKey: queryKeys.priceWatchAreas(picked?.no ?? ""),
    queryFn: () => getPriceWatchAreas(token, picked!.no),
    enabled: !!picked,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: queryKeys.priceWatchTargets });
    qc.invalidateQueries({ queryKey: ["priceWatchUnits"] });
    qc.invalidateQueries({ queryKey: ["priceWatchBasket"] });
  };
  const add = useMutation({
    mutationFn: () => addPriceWatchTarget(token, { complex_no: picked!.no, area_m2: area }),
    onSuccess: () => {
      invalidate();
      setPicked(null);
      setArea(null);
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => deletePriceWatchTarget(token, id),
    onSuccess: invalidate,
  });

  const full = targets.length >= maxTargets;

  return (
    <Card className="p-4 space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-gray-900">관심 단지·평형</h2>
        <span className="text-xs text-gray-500">{targets.length}/{maxTargets}개</span>
      </div>

      {targets.length === 0 ? (
        <p className="text-sm text-gray-500">아직 등록한 단지가 없어요. 아래에서 단지를 찾아 평형과 함께 추가해 주세요.</p>
      ) : (
        <ul className="divide-y divide-gray-100 border border-gray-100 rounded-md">
          {targets.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <div className="min-w-0">
                <p className="font-medium text-gray-900 truncate">{t.complex_name ?? t.complex_no}</p>
                <p className="text-xs text-gray-500">
                  {formatArea(t.area_m2, t.pyeong)} · 기록 {t.snapshot_days}일
                  {t.first_snapshot && ` (${formatShortDate(t.first_snapshot)}~${formatShortDate(t.last_snapshot)})`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => remove.mutate(t.id)}
                disabled={remove.isPending}
                className="p-1.5 text-gray-400 hover:text-red-600 disabled:opacity-50"
                aria-label={`${t.complex_name ?? t.complex_no} ${formatArea(t.area_m2, t.pyeong)} 삭제`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {remove.isError && <p className="text-xs text-red-600">삭제하지 못했어요: {remove.error.message}</p>}

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(keyword.trim());
          setPicked(null);
        }}
      >
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="단지명 검색 (2글자 이상)"
          aria-label="단지명 검색"
          className="flex-1 min-w-0 rounded-md border border-gray-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={keyword.trim().length < 2 || full}
          className="px-4 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          찾기
        </button>
      </form>
      {full && <p className="text-xs text-amber-700">최대 개수에 도달했어요. 추가하려면 먼저 하나를 지워 주세요.</p>}

      {submitted && !picked && (
        <div className="text-sm">
          {search.isLoading && <p className="text-gray-500">검색 중…</p>}
          {search.isError && <p className="text-red-600">검색하지 못했어요: {search.error.message}</p>}
          {search.data && search.data.complexes.length === 0 && <p className="text-gray-500">검색 결과가 없어요.</p>}
          {search.data && search.data.complexes.length > 0 && (
            <ul className="max-h-60 overflow-y-auto divide-y divide-gray-100 border border-gray-100 rounded-md">
              {search.data.complexes.map((c) => (
                <li key={c.complex_no}>
                  <button
                    type="button"
                    onClick={() => { setPicked({ no: c.complex_no, name: c.complex_name }); setArea(null); }}
                    className="w-full text-left px-3 py-2 hover:bg-gray-50"
                  >
                    <span className="font-medium text-gray-900">{c.complex_name}</span>
                    <span className="ml-2 text-xs text-gray-500">{c.cortar_address ?? ""}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {picked && (
        <div className="space-y-2 text-sm border border-blue-100 bg-blue-50/40 rounded-md p-3">
          <p className="font-medium text-gray-900">{picked.name} — 평형 선택</p>
          {areas.isLoading && <p className="text-gray-500">평형 불러오는 중…</p>}
          {areas.isError && <p className="text-red-600">평형을 불러오지 못했어요: {areas.error.message}</p>}
          {areas.data && (
            <fieldset className="space-y-1">
              <legend className="sr-only">평형</legend>
              <label className="flex items-center gap-2">
                <input type="radio" name="pw-area" checked={area === null} onChange={() => setArea(null)} />
                전체 평형
              </label>
              {areas.data.areas.map((a) => (
                <label key={a.area_m2} className="flex items-center gap-2">
                  <input type="radio" name="pw-area" checked={area === a.area_m2} onChange={() => setArea(a.area_m2)} />
                  <span>
                    전용 {a.area_m2}㎡ ({a.pyeong}평){a.supply_pyeong ? ` · 공급 ${a.supply_pyeong}평` : ""}
                    <span className="ml-1 text-xs text-gray-500">
                      매매 {a.count}건 · {formatKoreanPrice(a.min_price)}~{formatKoreanPrice(a.max_price)}
                    </span>
                  </span>
                </label>
              ))}
              {areas.data.areas.length === 0 && (
                <p className="text-xs text-gray-500">
                  지금 저장된 매매 매물이 없어 평형 목록이 비어 있어요. &quot;전체 평형&quot;으로 등록하면 다음 수집부터 기록돼요.
                </p>
              )}
            </fieldset>
          )}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={() => add.mutate()}
              disabled={add.isPending || full}
              className="px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {add.isPending ? "추가 중…" : "추적 시작"}
            </button>
            <button type="button" onClick={() => setPicked(null)} className="px-4 py-2 rounded-md border border-gray-300">
              취소
            </button>
          </div>
          {add.isError && <p className="text-xs text-red-600">추가하지 못했어요: {add.error.message}</p>}
        </div>
      )}
    </Card>
  );
}
