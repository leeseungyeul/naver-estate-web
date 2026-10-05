"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatChartPrice, formatKoreanPrice } from "@/lib/format";
import type { PriceWatchBasketResponse } from "@/types/price-watch";
import { changeColor, formatArea, formatChangePct, formatShortDate } from "./format";

type Metric = "index" | "avg_price" | "avg_ppy";

const METRICS: { key: Metric; label: string }[] = [
  { key: "index", label: "동일 매물 지수" },
  { key: "avg_price", label: "평균 호가" },
  { key: "avg_ppy", label: "전용 3.3㎡당 평균" },
];

function Stat({ label, value, help }: { label: string; value: number | null; help: string }) {
  return (
    <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
      <p className="text-xs text-gray-500" title={help}>{label}</p>
      <p className={`text-lg font-semibold ${changeColor(value)}`}>{formatChangePct(value)}</p>
    </div>
  );
}

/** ② 여러 단지(평형) 매매호가 평균 변동률 */
export default function BasketTrend({ data }: { data: PriceWatchBasketResponse }) {
  const [metric, setMetric] = useState<Metric>("index");
  const s = data.summary;
  const chartData = useMemo(
    () => data.series.map((p) => ({ ...p, label: formatShortDate(p.date) })),
    [data.series],
  );

  if (data.series.length === 0) {
    return <p className="py-8 text-center text-sm text-gray-500">이 기간에 기록된 매매 호가가 없어요.</p>;
  }

  const fmt = (v: number) => (metric === "index" ? v.toFixed(1) : formatChartPrice(v));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat label="평균 호가 변동률" value={s.avg_price_change_pct}
          help="첫 관측일과 마지막 관측일의 평균 호가 비교 — 매물 구성이 바뀌면 함께 출렁여요" />
        <Stat label="3.3㎡당 평균 변동률" value={s.avg_ppy_change_pct}
          help="전용면적 3.3㎡당 평균 호가 비교 — 평형이 섞여 있을 때 평균 호가보다 공정해요" />
        <Stat label="동일 매물 지수 변동률" value={s.same_unit_index_change_pct}
          help="이웃한 두 관측일에 모두 있던 같은 집끼리만 비교해 이어 붙인 값 — 매물이 들고 나는 영향을 뺀 순수 호가 변화" />
        <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
          <p className="text-xs text-gray-500">관측일</p>
          <p className="text-lg font-semibold text-gray-900">{s.observation_days}일</p>
          <p className="text-[11px] text-gray-400">{formatShortDate(s.first_date)} ~ {formatShortDate(s.last_date)}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1" role="group" aria-label="차트 지표">
        {METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setMetric(m.key)}
            aria-pressed={metric === m.key}
            className={`px-3 py-1 text-xs rounded-full border ${metric === m.key
              ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 text-gray-700"}`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={fmt} domain={["auto", "auto"]} width={56} />
            <Tooltip
              formatter={(v) => [fmt(Number(v)), METRICS.find((m) => m.key === metric)?.label ?? ""]}
              labelFormatter={(l, payload) => {
                const p = payload?.[0]?.payload as { unit_count?: number; complex_coverage?: number; complex_count?: number } | undefined;
                return p ? `${l} · 집 ${p.unit_count}곳 · 단지 ${p.complex_coverage}/${p.complex_count}` : String(l);
              }}
            />
            <Line type="monotone" dataKey={metric} stroke="#2563eb" strokeWidth={2} dot={{ r: 2 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="overflow-x-auto border border-gray-200 rounded-md">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="bg-gray-50 text-xs text-gray-600">
            <tr>
              <th className="px-2 py-2 text-left">단지</th>
              <th className="px-2 py-2 text-left">평형</th>
              <th className="px-2 py-2 text-right">처음 평균</th>
              <th className="px-2 py-2 text-right">최근 평균</th>
              <th className="px-2 py-2 text-right">평균 변동률</th>
              <th className="px-2 py-2 text-right">3.3㎡당 변동률</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.targets.map((t) => (
              <tr key={t.target_id}>
                <td className="px-2 py-2">{t.complex_name ?? t.complex_no}</td>
                <td className="px-2 py-2 text-xs">{formatArea(t.area_m2, t.pyeong)}</td>
                <td className="px-2 py-2 text-right">{formatKoreanPrice(t.first_avg_price)}</td>
                <td className="px-2 py-2 text-right">{formatKoreanPrice(t.last_avg_price)}</td>
                <td className={`px-2 py-2 text-right font-medium ${changeColor(t.change_pct)}`}>{formatChangePct(t.change_pct)}</td>
                <td className={`px-2 py-2 text-right ${changeColor(t.ppy_change_pct)}`}>{formatChangePct(t.ppy_change_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-500">
        단지마다 수집일이 다르면 그 단지의 가장 최근 기록(최대 14일 전)을 이어 써서 평균에 빈칸이 생기지 않게 했어요. 같은 집이 여러 중개사에 올라와도 한 번만 셉니다.
      </p>
    </div>
  );
}
