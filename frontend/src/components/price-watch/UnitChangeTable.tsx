"use client";

import { Fragment, useMemo, useState } from "react";
import { formatKoreanPrice } from "@/lib/format";
import type { PriceWatchUnitsResponse, PriceWatchUnit } from "@/types/price-watch";
import { changeColor, formatChangePct, formatShortDate } from "./format";

type SortKey = "change_asc" | "change_desc" | "location";
type StatusFilter = "all" | "active" | "gone";

function SummaryCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-semibold ${tone ?? "text-gray-900"}`}>{value}</p>
    </div>
  );
}

function sortUnits(units: PriceWatchUnit[], key: SortKey): PriceWatchUnit[] {
  const out = [...units];
  if (key === "location") return out;
  const dir = key === "change_asc" ? 1 : -1;
  // 변동률이 없는(한 번만 관측된) 집은 항상 뒤로
  return out.sort((a, b) => {
    if (a.change_pct === null) return 1;
    if (b.change_pct === null) return -1;
    return (a.change_pct - b.change_pct) * dir;
  });
}

/** ① 동일 매물(추정) 호가 변동률 — 집 한 줄 = (단지·동·층·전용면적)이 같은 등록 묶음 */
export default function UnitChangeTable({ data }: { data: PriceWatchUnitsResponse }) {
  const [sortKey, setSortKey] = useState<SortKey>("change_asc");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [open, setOpen] = useState<string | null>(null);
  const s = data.summary;

  const rows = useMemo(
    () => sortUnits(data.units.filter((u) => status === "all" || u.status === status), sortKey),
    [data.units, status, sortKey],
  );

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <SummaryCard label="추적 중인 집(추정)" value={`${s.unit_count}곳`} />
        <SummaryCard label="두 번 이상 관측" value={`${s.tracked_count}곳`} />
        <SummaryCard
          label="변동률 중앙값"
          value={formatChangePct(s.median_change_pct)}
          tone={changeColor(s.median_change_pct)}
        />
        <SummaryCard label="내림 / 올림 / 그대로" value={`${s.down_count} / ${s.up_count} / ${s.flat_count}`} />
      </div>
      <p className="text-xs text-gray-500">
        같은 단지·동·층·전용면적의 매물을 같은 집으로 추정해 묶었어요(중개사별 중복 등록·재등록 포함). 하루에 여러 등록이면 최저 호가를 씁니다.
        같은 층에 같은 면적 집이 둘 이상이면 하나로 합쳐질 수 있어, 그날 가격 범위를 함께 보여드려요.
      </p>

      <div className="flex flex-wrap gap-2 text-sm">
        <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}
          aria-label="정렬" className="rounded-md border border-gray-300 px-2 py-1">
          <option value="change_asc">많이 내린 순</option>
          <option value="change_desc">많이 오른 순</option>
          <option value="location">단지·동·층 순</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)}
          aria-label="상태" className="rounded-md border border-gray-300 px-2 py-1">
          <option value="all">전체</option>
          <option value="active">지금 나와 있는 집</option>
          <option value="gone">사라진 집 ({s.gone_count})</option>
        </select>
      </div>

      {rows.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-500">이 기간에 기록된 매매 호가가 없어요.</p>
      ) : (
        <div className="overflow-x-auto border border-gray-200 rounded-md">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-gray-50 text-xs text-gray-600">
              <tr>
                <th className="px-2 py-2 text-left">단지</th>
                <th className="px-2 py-2 text-left">동·층</th>
                <th className="px-2 py-2 text-left">전용</th>
                <th className="px-2 py-2 text-right">처음 호가</th>
                <th className="px-2 py-2 text-right">최근 호가</th>
                <th className="px-2 py-2 text-right">변동</th>
                <th className="px-2 py-2 text-center">관측</th>
                <th className="px-2 py-2 text-center">상태</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((u) => {
                const id = `${u.complex_no}|${u.unit_key}`;
                const expanded = open === id;
                return (
                  <Fragment key={id}>
                    <tr
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => setOpen(expanded ? null : id)}
                      aria-expanded={expanded}
                    >
                      <td className="px-2 py-2 max-w-[160px] truncate">{u.complex_name ?? u.complex_no}</td>
                      <td className="px-2 py-2">
                        {u.building ?? "?"} {u.floor ? `${u.floor}층` : ""}
                        {u.confidence !== "높음" && (
                          <span className="ml-1 text-[11px] text-amber-700" title="층이 고/중/저로만 나오거나 정보가 빠져 추정이 거칠어요">
                            추정 {u.confidence}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-2">{u.area_m2 ?? "-"}㎡{u.pyeong ? ` (${u.pyeong}평)` : ""}</td>
                      <td className="px-2 py-2 text-right">
                        {formatKoreanPrice(u.first_price)}
                        <span className="block text-[11px] text-gray-400">{formatShortDate(u.first_date)}</span>
                      </td>
                      <td className="px-2 py-2 text-right">
                        {formatKoreanPrice(u.last_price)}
                        <span className="block text-[11px] text-gray-400">{formatShortDate(u.last_date)}</span>
                      </td>
                      <td className={`px-2 py-2 text-right font-medium ${changeColor(u.change_pct)}`}>
                        {u.observations >= 2 ? formatChangePct(u.change_pct) : "—"}
                        {u.change_amount !== 0 && (
                          <span className="block text-[11px]">
                            {u.change_amount > 0 ? "+" : "-"}{formatKoreanPrice(Math.abs(u.change_amount))}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-2 text-center text-xs text-gray-600">{u.observations}일 · {u.price_moves}회 변경</td>
                      <td className="px-2 py-2 text-center text-xs">
                        {u.status === "active"
                          ? <span className="text-green-700">게시 중</span>
                          : <span className="text-gray-400">사라짐</span>}
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="bg-gray-50/60">
                        <td colSpan={8} className="px-3 py-2 text-xs text-gray-700">
                          <ol className="flex flex-wrap gap-x-3 gap-y-1">
                            {u.series.map((p) => (
                              <li key={p.date}>
                                {formatShortDate(p.date)} <b>{formatKoreanPrice(p.price)}</b>
                                {p.listings > 1 && (
                                  <span className="text-gray-500">
                                    {" "}(등록 {p.listings}건{p.max !== p.min ? `, ~${formatKoreanPrice(p.max)}` : ""})
                                  </span>
                                )}
                              </li>
                            ))}
                          </ol>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
