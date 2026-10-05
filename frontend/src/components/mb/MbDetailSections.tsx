"use client";

import dynamic from "next/dynamic";
import type { MbApartment, MbPrice } from "@/types";
import { formatKoreanPrice, formatYearMonth, freshness } from "@/lib/format";
import { normalizePp } from "@/lib/mb-format";
import { formatHouseType } from "@/lib/mb-house-type";
import { MbCancelRatioBar } from "./MbCancelRatioBar";
import { MbCoverageBar } from "./MbCoverageBar";
import { MbExclusiveRatioBar } from "./MbExclusiveRatioBar";
import { MbFloorAreaRatioBar } from "./MbFloorAreaRatioBar";
import { MbJeonseRateBar } from "./MbJeonseRateBar";
import { MbMaintenanceBar } from "./MbMaintenanceBar";
import { MbMaxFloorBar } from "./MbMaxFloorBar";
import { MbParkingBar } from "./MbParkingBar";
import { MbPirBar } from "./MbPirBar";
import { MbUnitsBar } from "./MbUnitsBar";
import { MbUnsoldRateBar } from "./MbUnsoldRateBar";

const MbTradeStatsCharts = dynamic(() => import("./MbTradeStatsCharts"), { ssr: false });

interface SectionProps {
  apartment: MbApartment;
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="text-sm font-medium text-gray-900">{value ?? "-"}</dd>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-lg shadow-sm border p-4 md:p-6">
      <h3 className="text-base font-bold text-gray-800 mb-4 pb-2 border-b border-gray-200">{title}</h3>
      {children}
    </section>
  );
}

/** 개요 — 기본정보 + 시공사 */
export function OverviewSection({ apartment: a }: SectionProps) {
  const b = a.builder_info;
  return (
    <SectionCard title="개요">
      <dl className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <InfoRow label="단지명" value={a.name} />
        <InfoRow label="주소" value={a.address ?? a.road_address} />
        <InfoRow label="지역" value={`${a.region} ${a.gu ?? ""} ${a.dong ?? ""}`.trim()} />
        <InfoRow label="세대수" value={a.units != null ? <MbUnitsBar value={a.units} /> : undefined} />
        <InfoRow label="완공" value={formatYearMonth(a.completion)} />
        <InfoRow label="준공연도(네이버)" value={a.naver_build_year != null ? `${a.naver_build_year}년` : undefined} />
        <InfoRow label="난방" value={a.heating} />
        <InfoRow label="난방연료" value={a.heat_fuel} />
        <InfoRow label="복도구조" value={a.corridor_type} />
        <InfoRow label="주향" value={a.primary_direction} />
        <InfoRow label="조망" value={a.view} />
        <InfoRow label="최고층" value={a.max_floor != null ? <MbMaxFloorBar value={a.max_floor} /> : undefined} />
        <InfoRow label="세대당 주차" value={a.parking_ratio != null ? <MbParkingBar value={a.parking_ratio} /> : undefined} />
        <InfoRow label="용적률" value={a.floor_area_ratio != null ? <MbFloorAreaRatioBar value={a.floor_area_ratio} /> : undefined} />
        <InfoRow label="건폐율" value={a.building_coverage_ratio != null ? <MbCoverageBar value={a.building_coverage_ratio} /> : undefined} />
        <InfoRow label="전용률" value={a.exclusive_ratio != null ? <MbExclusiveRatioBar value={a.exclusive_ratio} /> : undefined} />
        <InfoRow label="관리비" value={a.avg_maintenance_cost != null ? <MbMaintenanceBar value={a.avg_maintenance_cost} /> : undefined} />
        <InfoRow label="규제지역" value={a.is_regulated ? "예" : a.is_regulated === false ? "아니오" : undefined} />
        <InfoRow label="시공사" value={a.builder} />
        {b && (
          <>
            <InfoRow label="부채비율" value={b.debt_ratio != null ? `${b.debt_ratio}%` : undefined} />
            <InfoRow label="신용등급" value={b.credit_grade} />
            <InfoRow label="HUG 보증" value={b.hug_guarantee ? "가능" : b.hug_guarantee === false ? "불가" : undefined} />
            <InfoRow label="시공사 정보 갱신" value={freshness(b.updated_at)} />
          </>
        )}
        <InfoRow label="네이버 인근 시세" value={a.naver_nearby_median != null ? formatKoreanPrice(a.naver_nearby_median) : undefined} />
        <InfoRow label="네이버 매물 수" value={a.naver_sell_count != null ? `${a.naver_sell_count}건` : undefined} />
        <InfoRow label="네이버 전세가율" value={a.naver_jeonse_rate != null ? `${a.naver_jeonse_rate.toFixed(1)}%` : undefined} />
        <InfoRow label="등록" value={a.created_at ? new Date(a.created_at).toLocaleDateString("ko-KR") : undefined} />
      </dl>
    </SectionCard>
  );
}

/** 분양 정보 — 혜택 + 분양가 */
export function PresaleSection({ apartment: a }: SectionProps) {
  const prices = a.prices;
  return (
    <SectionCard title="분양 정보">
      <dl className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
        <InfoRow label="분양 최저가" value={a.presale_min_price != null ? formatKoreanPrice(a.presale_min_price) : undefined} />
        <InfoRow label="분양 최고가" value={a.presale_max_price != null ? formatKoreanPrice(a.presale_max_price) : undefined} />
        <InfoRow label="평당가" value={normalizePp(a.presale_pp) != null ? formatKoreanPrice(a.presale_pp!) : undefined} />
        <InfoRow label="분양유형" value={a.presale_type} />
        <InfoRow label="분양단계" value={a.presale_stage} />
        <InfoRow label="입주시기" value={a.presale_move_in} />
        <InfoRow label="할인율" value={a.discount_pct != null ? `${a.discount_pct}%` : undefined} />
        <InfoRow label="미분양률" value={a.unsold_rate != null ? <MbUnsoldRateBar value={a.unsold_rate} /> : undefined} />
        <InfoRow label="미분양 세대수" value={a.unsold != null ? `${a.unsold.toLocaleString()}세대` : undefined} />
        <InfoRow label="발코니 무상" value={a.balcony_free ? "O" : a.balcony_free === false ? "X" : undefined} />
        <InfoRow label="옵션 무상" value={a.option_free ? "O" : a.option_free === false ? "X" : undefined} />
        <InfoRow label="캐시백" value={a.cashback != null ? formatKoreanPrice(a.cashback) : undefined} />
        <InfoRow label="청약 경쟁률" value={a.competition_rate != null ? `${a.competition_rate.toLocaleString()}:1` : undefined} />
        <InfoRow label="청약 신청자" value={a.competition_applicants != null ? `${a.competition_applicants.toLocaleString()}명` : undefined} />
        <InfoRow label="청약 공급세대" value={a.competition_supply != null ? `${a.competition_supply.toLocaleString()}세대` : undefined} />
      </dl>

      {prices && prices.length > 0 ? (
        <div className="overflow-x-auto border rounded-md">
          {/* 열 6개가 전부 보이는 표라 최소 너비가 없으면 좁은 화면에서 셀이 눌려 머리글이 세로로
              한 글자씩 꺾인다(390px 실측). 최소 너비를 주면 넘치는 만큼 위 div 가 가로 스크롤한다. */}
          <table className="w-full min-w-140 text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-3 py-2 text-left text-gray-600">타입</th>
                <th className="px-3 py-2 text-right text-gray-600">전용면적</th>
                <th className="px-3 py-2 text-right text-gray-600">공급면적</th>
                <th className="px-3 py-2 text-right text-gray-600">분양가</th>
                <th className="px-3 py-2 text-right text-gray-600">평당가</th>
                <th className="px-3 py-2 text-right text-gray-600">세대수</th>
              </tr>
            </thead>
            <tbody>
              {prices.map((p: MbPrice) => (
                <tr key={p.id} className="border-b last:border-b-0">
                  <td className="px-3 py-1.5">{formatHouseType(p.house_type)}</td>
                  <td className="px-3 py-1.5 text-right">{p.area != null ? `${p.area}㎡` : "-"}</td>
                  <td className="px-3 py-1.5 text-right">{p.supply_area != null ? `${p.supply_area}㎡` : "-"}</td>
                  <td className="px-3 py-1.5 text-right font-medium">{p.price != null ? formatKoreanPrice(p.price) : "-"}</td>
                  <td className="px-3 py-1.5 text-right">{normalizePp(p.pp) != null ? formatKoreanPrice(p.pp!) : "-"}</td>
                  <td className="px-3 py-1.5 text-right">{p.supply_count ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {prices[0]?.recorded_at && (
            <p className="px-3 py-1.5 text-xs text-gray-400 border-t bg-gray-50">분양가 {freshness(prices[0].recorded_at)}</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-400">분양가 데이터가 없습니다.</p>
      )}
    </SectionCard>
  );
}

/** re-export — 기존 import 호환 유지 */
export { EnvironmentSection } from "./MbEnvironmentSection";

/** 거래 통계 */
export function TradeStatsSection({ apartment: a }: SectionProps) {
  const ts = a.trade_stats;
  if (!ts) {
    return (
      <SectionCard title="거래 통계">
        <p className="text-sm text-gray-400">거래 통계 데이터가 없습니다.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="거래 통계">
      <dl className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
        <InfoRow label="인근 시세 중위값" value={ts.nearby_median != null ? formatKoreanPrice(ts.nearby_median) : undefined} />
        <InfoRow label="최근 6개월 거래" value={ts.recent_trades_6m != null ? `${ts.recent_trades_6m}건` : undefined} />
        <InfoRow label="전세율" value={ts.jeonse_rate != null ? <MbJeonseRateBar value={ts.jeonse_rate} /> : undefined} />
        <InfoRow label="PIR" value={ts.pir != null ? <MbPirBar value={ts.pir} /> : undefined} />
        <InfoRow label="PSR" value={ts.psr != null ? ts.psr.toFixed(1) : undefined} />
        <InfoRow label="평균층" value={ts.avg_floor != null ? `${ts.avg_floor.toFixed(1)}층` : undefined} />
        <InfoRow label="층 범위" value={ts.floor_range} />
        <InfoRow label="6개월 취소율" value={<MbCancelRatioBar value={ts.cancel_ratio_6m} />} />
        <InfoRow label="통계 갱신" value={freshness(ts.updated_at)} />
      </dl>
      <MbTradeStatsCharts tradeStats={ts} />
    </SectionCard>
  );
}
