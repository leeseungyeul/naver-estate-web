"use client";

import { memo, useState } from "react";
import { Search } from "lucide-react";
import type { Article } from "@/types";
import { M2_TO_PYEONG, TRADE_TYPE_COLORS, TRADE_TYPE_DEFAULT_COLOR, ESTATE_TYPE_COLORS, ESTATE_TYPE_DEFAULT_COLOR } from "@/lib/constants";
import { formatMaintenanceCost } from "@/lib/format";
import type { ArticleViewMode } from "@/lib/storage";
import ArticleFavoriteButton from "@/components/ArticleFavoriteButton";
import ArticleCompactRow from "@/components/ArticleCompactRow";
import { EmptyState } from "@/components/ui/empty-state";

interface Props {
  articles: Article[];
  onRowClick?: (articleNo: string) => void;
  selectedArticleNos?: Set<string>;
  onSelectionChange?: (articleNo: string, checked: boolean) => void;
  onSelectAll?: (checked: boolean, visibleArticles: Article[]) => void;
  hasActiveFilters?: boolean;
  onResetFilters?: () => void;
  viewMode?: ArticleViewMode;
}

/** 매물 목록 모바일 카드뷰 (md:hidden) — 데스크톱 ArticleTable의 모바일 대응. viewMode=large(기본 동작 4행) / medium(1·2행만) / compact(별도 1줄 컴포넌트). */
function ArticleCardMobile({ articles, onRowClick, selectedArticleNos, onSelectionChange, onSelectAll, hasActiveFilters, onResetFilters, viewMode = "large" }: Props) {
  if (articles.length === 0) {
    const emptyTitle = hasActiveFilters
      ? "조건에 맞는 매물이 없어요"
      : "표시할 매물이 없어요";
    const emptyDescription = hasActiveFilters
      ? "필터 조건이 너무 좁을 수 있어요"
      : "위의 \"데이터 갱신\" 버튼을 눌러보세요";
    const emptyAction = hasActiveFilters && onResetFilters ? (
      <button
        type="button"
        onClick={onResetFilters}
        className="text-sm text-blue-600 hover:underline py-1"
      >
        필터 초기화
      </button>
    ) : undefined;
    return (
      <EmptyState
        icon={Search}
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
      />
    );
  }

  return (
    <div className="space-y-2">
      {onSelectionChange && (
        <label className="flex items-center gap-2 px-1 text-sm text-gray-500">
          <input
            type="checkbox"
            checked={articles.length > 0 && articles.every(a =>
              (a.group_members ?? [a]).every(member => selectedArticleNos?.has(member.article_no)))}
            onChange={(e) => onSelectAll?.(e.target.checked, articles)}
            className="w-4 h-4 rounded border-gray-300"
          />
          전체 선택
        </label>
      )}
      {articles.map((art) => (
        <MobileGroupItem key={art.article_no} article={art} viewMode={viewMode}
          onClick={onRowClick} selectedArticleNos={selectedArticleNos} onCheck={onSelectionChange} />
      ))}
    </div>
  );
}

export default memo(ArticleCardMobile);

function MobileGroupItem({ article: art, viewMode, onClick, selectedArticleNos, onCheck }: {
  article: Article;
  viewMode: ArticleViewMode;
  onClick?: (articleNo: string) => void;
  selectedArticleNos?: Set<string>;
  onCheck?: (articleNo: string, checked: boolean) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div>
      {viewMode === "compact" ? (
        <ArticleCompactRow article={art} onClick={onClick}
          selected={selectedArticleNos?.has(art.article_no)} onCheck={onCheck} />
      ) : (
        <ArticleCardItem article={art} onClick={onClick}
          selected={selectedArticleNos?.has(art.article_no)} onCheck={onCheck} viewMode={viewMode} />
      )}
      {art.group_count != null && art.group_count > 1 && (
        <div className="rounded-b border border-t-0 bg-blue-50/50 px-3 py-1.5 text-xs">
          <button type="button" className="text-blue-700 font-semibold"
            aria-label={`추정 묶음 ${art.group_count}건 ${expanded ? "접기" : "펼치기"}`}
            aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>
            추정 묶음 {art.group_count}건 {expanded ? "▲" : "▼"}
          </button>
          {expanded && (
            <div className="space-y-1 mt-2">
              <p className="text-gray-600">동일 호실 확정 아님 · 원본 등록 {art.group_members?.length ?? art.group_count}건</p>
              {art.group_members?.map(member => (
                <div key={member.article_no} className="flex items-center gap-2 rounded bg-white p-1">
                  {onCheck && <input type="checkbox" aria-label={`묶음 원본 매물 ${member.article_no} 선택`}
                    checked={!!selectedArticleNos?.has(member.article_no)}
                    onChange={e => onCheck(member.article_no, e.target.checked)} />}
                  <button type="button" className="text-blue-700" onClick={() => onClick?.(member.article_no)}
                    aria-label={`원본 매물 ${member.article_no} ${member.realtor_name || "중개사 미상"} 상세 보기`}>
                    {member.realtor_name || "중개사 미상"} · {member.deal_or_warrant_prc || "가격 미상"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const ArticleCardItem = memo(function ArticleCardItem({ article: art, onClick, selected, onCheck, viewMode }: {
  article: Article; onClick?: (no: string) => void; selected?: boolean; onCheck?: (articleNo: string, checked: boolean) => void; viewMode: "large" | "medium";
}) {
  const isRent = art.trade_type_name === "월세" || art.trade_type_name === "단기임대";
  const price = isRent
    ? `${art.deal_or_warrant_prc ?? "-"} / ${art.rent_prc ?? "-"}`
    : art.deal_or_warrant_prc ?? "-";

  const areaM2 = art.area2_m2 ?? art.area1_m2;
  const areaTxt = areaM2
    ? `${areaM2}㎡(${Math.round(areaM2 / M2_TO_PYEONG * 10) / 10}평)`
    : null;

  const rooms = art.room_count != null && art.bathroom_count != null
    ? `${art.room_count}/${art.bathroom_count}`
    : art.room_count != null ? `${art.room_count}/-` : null;

  const maint = formatMaintenanceCost(art.maintenance_cost, art.numeric_maintenance_cost);

  return (
    <div
      className="relative bg-white rounded-lg shadow-sm border p-3 pr-10 cursor-pointer hover:bg-blue-50 active:bg-blue-100 transition-colors"
      onClick={() => onClick?.(art.article_no)}
    >
      {/* 1행: 체크+거래유형+가격+가격변동+즐겨찾기★ */}
      <div className="flex items-center gap-2">
        {onCheck && (
          <input
            type="checkbox"
            checked={!!selected}
            onChange={(e) => onCheck(art.article_no, e.target.checked)}
            onClick={(e) => e.stopPropagation()}
            className="w-4 h-4 rounded border-gray-300 shrink-0"
          />
        )}
        <span className={`px-2 py-1 rounded text-sm font-medium shrink-0 ${
          TRADE_TYPE_COLORS[art.trade_type_name ?? ""] ?? TRADE_TYPE_DEFAULT_COLOR
        }`}>
          {art.trade_type_name ?? "-"}
        </span>
        {art.article_real_estate_type_name && art.article_real_estate_type_name !== "아파트" && (
          <span className={`px-1.5 py-1 rounded text-sm border shrink-0 ${
            ESTATE_TYPE_COLORS[art.article_real_estate_type_name] ?? ESTATE_TYPE_DEFAULT_COLOR
          }`}>{art.article_real_estate_type_name}</span>
        )}
        <span className="font-semibold text-gray-900 text-sm">{price}</span>
        {art.previous_price != null && art.numeric_price != null && art.previous_price !== art.numeric_price && (
          <span className={`text-sm ${art.numeric_price < art.previous_price ? "text-blue-600" : "text-red-600"}`}>
            {art.numeric_price < art.previous_price ? "↓" : "↑"}
            {Math.abs(art.numeric_price - art.previous_price).toLocaleString()}
          </span>
        )}
        <span className="ml-auto shrink-0" onClick={(e) => e.stopPropagation()}>
          <ArticleFavoriteButton
            articleNo={art.article_no}
            complexNo={art.complex_no}
            complexName={art.complex_name}
            tradeTypeName={art.trade_type_name}
            price={art.deal_or_warrant_prc}
          />
        </span>
      </div>

      {/* 2행: 면적·동·층 */}
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 mt-1.5 text-sm text-gray-600">
        {areaTxt && <span>{areaTxt}</span>}
        {art.building_name && <><span className="text-gray-300">·</span><span>{art.building_name}</span></>}
        {art.floor_info && <><span className="text-gray-300">·</span><span>{art.floor_info}층</span></>}
      </div>

      {viewMode === "large" && (
        <>
          {/* 3행: 방/욕·방향·입주·관리비 */}
          <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 mt-1 text-sm text-gray-500">
            {rooms && <span>{rooms}</span>}
            {art.direction && <><span className="text-gray-300">·</span><span>{art.direction}</span></>}
            {art.move_in_date && <><span className="text-gray-300">·</span><span>{art.move_in_date}</span></>}
            {maint !== "-" && <><span className="text-gray-300">·</span><span>관리비 {maint}</span></>}
            {art.monthly_rent_yield != null && <><span className="text-gray-300">·</span><span className={`px-1.5 py-0.5 rounded text-sm font-semibold ${art.monthly_rent_yield >= 10 ? "bg-blue-100 text-blue-700" : art.monthly_rent_yield >= 5 ? "bg-emerald-100 text-emerald-700" : art.monthly_rent_yield < 3 ? "bg-yellow-100 text-yellow-700" : "bg-emerald-50 text-emerald-600"}`}>수익 {art.monthly_rent_yield}%</span></>}
            {art.article_jeonse_ratio != null && <><span className="text-gray-300">·</span><span className={`px-1.5 py-0.5 rounded text-sm font-semibold ${art.article_jeonse_ratio > 80 ? "bg-red-100 text-red-700" : "bg-blue-50 text-blue-600"}`}>전세 {art.article_jeonse_ratio}%</span></>}
          </div>

          {/* 4행: 특징 (truncate) */}
          {art.article_feature_desc && (
            <p className="mt-1.5 text-sm text-gray-400 truncate">{art.article_feature_desc}</p>
          )}
        </>
      )}
    </div>
  );
});
