"use client";

import { useState, useMemo, useCallback, memo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  type OnChangeFn,
  type Column,
} from "@tanstack/react-table";
import { Search } from "lucide-react";
import type { Article } from "@/types";
import { EmptyState } from "@/components/ui/empty-state";
import {
  M2_TO_PYEONG,
  TRADE_TYPE_COLORS,
  TRADE_TYPE_DEFAULT_COLOR,
  ESTATE_TYPE_COLORS,
  ESTATE_TYPE_DEFAULT_COLOR,
} from "@/lib/constants";
import { formatDateShort, formatMaintenanceCost } from "@/lib/format";
import { COLUMNS, SERVER_SORT_MAP, type ArticleColumnMeta } from "@/components/articleTableColumns";
import ArticleFavoriteButton from "@/components/ArticleFavoriteButton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Props {
  articles: Article[];
  onRowClick?: (articleNo: string) => void;
  onSortChange?: (sortBy: string) => void;
  selectedArticleNos?: Set<string>;
  onSelectionChange?: (articleNo: string, checked: boolean) => void;
  onSelectAll?: (checked: boolean, visibleArticles: Article[]) => void;
  hasActiveFilters?: boolean;
  onResetFilters?: () => void;
}

function ariaSort(column: Column<Article, unknown>): "ascending" | "descending" | "none" {
  const sorted = column.getIsSorted();
  if (sorted === "asc") return "ascending";
  if (sorted === "desc") return "descending";
  return "none";
}

function ArticleTable({
  articles,
  onRowClick,
  onSortChange,
  selectedArticleNos,
  onSelectionChange,
  onSelectAll,
  hasActiveFilters,
  onResetFilters,
}: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<Article>[]>(() => COLUMNS, []);

  const handleSortingChange = useCallback<OnChangeFn<SortingState>>(
    (updater) => {
      // updater(=setState 함수) 내부에서 onSortChange(→ router.replace)를 호출하면
      // 렌더 중 Router 갱신 경고("Cannot update a component...")가 발생한다.
      // 부수효과는 updater 밖, 현재 state 기준으로 계산해 실행한다.
      setSorting((prev) => (typeof updater === "function" ? updater(prev) : updater));
      const next = typeof updater === "function" ? updater(sorting) : updater;
      const first = next[0];
      if (first && onSortChange) {
        const serverSort = SERVER_SORT_MAP[first.id];
        if (serverSort) {
          onSortChange(first.desc ? serverSort.desc : serverSort.asc);
        }
      }
    },
    [onSortChange, sorting]
  );

  const table = useReactTable({
    data: articles,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    state: { sorting },
    onSortingChange: handleSortingChange,
    sortDescFirst: false,
  });

  const sortedRows = table.getRowModel().rows;

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
        className="text-xs text-blue-600 hover:underline"
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
    <Table className="bg-white rounded-lg shadow-sm border text-sm">
      <TableHeader className="bg-gray-100 border-b-2 border-gray-300 sticky top-0 z-10">
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow key={headerGroup.id} className="hover:bg-transparent">
            {onSelectionChange && (
              <TableHead scope="col" className="px-2 py-2 w-8 h-auto">
                <input
                  type="checkbox"
                  checked={
                    sortedRows.length > 0 &&
                    sortedRows.every((r) => (r.original.group_members ?? [r.original])
                      .every((a) => selectedArticleNos?.has(a.article_no)))
                  }
                  onChange={(e) =>
                    onSelectAll?.(e.target.checked, sortedRows.map((r) => r.original))
                  }
                  className="w-4 h-4 rounded border-gray-300"
                  title="전체 선택"
                />
              </TableHead>
            )}
            <TableHead
              scope="col"
              className="px-2 py-2 w-16 h-auto text-center text-xs text-gray-700"
              aria-label="메모/즐겨찾기 액션"
            >
              액션
            </TableHead>
            {headerGroup.headers.map((header) => {
              const col = header.column;
              const meta = col.columnDef.meta as ArticleColumnMeta | undefined;
              const className = `px-2 py-2.5 h-auto text-xs font-semibold text-gray-700 whitespace-nowrap border-r border-gray-200 last:border-r-0 ${meta?.className ?? ""}`;
              return (
                <TableHead
                  key={header.id}
                  scope="col"
                  aria-sort={ariaSort(col)}
                  className={className}
                >
                  {col.getCanSort() ? (
                    <button
                      type="button"
                      onClick={col.getToggleSortingHandler()}
                      className="flex items-center gap-0.5 cursor-pointer hover:text-blue-600"
                      title={meta?.headerTitle ?? "클릭하여 정렬"}
                    >
                      <span>{col.columnDef.header as string}</span>
                      {col.getIsSorted() && (
                        <span className="text-blue-600 text-[10px]">
                          {col.getIsSorted() === "asc" ? "▲" : "▼"}
                        </span>
                      )}
                    </button>
                  ) : (
                    <span>{col.columnDef.header as string}</span>
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {sortedRows.map((row, idx) => (
          <ArticleRow
            key={row.original.article_no}
            article={row.original}
            index={idx + 1}
            onClick={onRowClick}
            selected={selectedArticleNos?.has(row.original.article_no)}
            selectedArticleNos={selectedArticleNos}
            onCheck={onSelectionChange}
          />
        ))}
      </TableBody>
    </Table>
  );
}

const ArticleRow = memo(function ArticleRow({
  article: art,
  index,
  onClick,
  selected,
  selectedArticleNos,
  onCheck,
}: {
  article: Article;
  index: number;
  onClick?: (no: string) => void;
  selected?: boolean;
  selectedArticleNos?: Set<string>;
  onCheck?: (articleNo: string, checked: boolean) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const price =
    art.trade_type_name === "월세" || art.trade_type_name === "단기임대"
      ? `${art.deal_or_warrant_prc || "-"} / ${art.rent_prc || "-"}`
      : art.deal_or_warrant_prc || "-";

  const areaM2 = art.area2_m2 || art.area1_m2;
  const area = areaM2
    ? `${areaM2}㎡ (${Math.round((areaM2 / M2_TO_PYEONG) * 10) / 10}평)`
    : "-";

  const ppyeong = art.price_per_pyeong ? `${art.price_per_pyeong.toLocaleString()}` : "-";

  const rooms =
    art.room_count != null && art.bathroom_count != null
      ? `${art.room_count}/${art.bathroom_count}`
      : art.room_count != null
      ? `${art.room_count}/-`
      : "-";

  let moveIn = art.move_in_date || "-";
  if (moveIn.length === 8) moveIn = formatDateShort(moveIn);

  const maint = formatMaintenanceCost(art.maintenance_cost, art.numeric_maintenance_cost);

  let confirm = art.article_confirm_ymd || "-";
  if (confirm.length === 8) confirm = formatDateShort(confirm);

  return (
    <>
    <TableRow
      onClick={() => onClick?.(art.article_no)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(art.article_no);
        }
      }}
      tabIndex={0}
      role="row"
      aria-label={`매물 ${art.article_no} 상세 보기`}
      className={`hover:bg-blue-50 cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400 border-b border-gray-200 ${
        index % 2 === 0 ? "bg-gray-50/50" : "bg-white"
      }`}
    >
      {onCheck && (
        <Td className="text-center border-r border-gray-100" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={!!selected}
            onChange={(e) => onCheck(art.article_no, e.target.checked)}
            className="w-4 h-4 rounded border-gray-300"
            aria-label={`매물 ${art.article_no} 선택`}
          />
        </Td>
      )}
      <Td className="text-center border-r border-gray-100" onClick={(e) => e.stopPropagation()}>
        <span className="ml-1">
          <ArticleFavoriteButton
            articleNo={art.article_no}
            complexNo={art.complex_no}
            complexName={art.complex_name}
            tradeTypeName={art.trade_type_name}
            price={art.deal_or_warrant_prc}
          />
        </span>
      </Td>
      <Td className="text-gray-400 text-center">{index}</Td>
      <Td>
        <span
          className={`px-1.5 py-0.5 rounded text-xs font-medium ${
            TRADE_TYPE_COLORS[art.trade_type_name || ""] || TRADE_TYPE_DEFAULT_COLOR
          }`}
        >
          {art.trade_type_name || "-"}
        </span>
        {art.article_real_estate_type_name &&
          art.article_real_estate_type_name !== "아파트" && (
            <span
              className={`ml-1 px-1 py-0.5 rounded text-xs border ${
                ESTATE_TYPE_COLORS[art.article_real_estate_type_name] ??
                ESTATE_TYPE_DEFAULT_COLOR
              }`}
            >
              {art.article_real_estate_type_name}
            </span>
          )}
      </Td>
      <Td>
        {art.building_name || "-"}
        {art.group_count != null && art.group_count > 1 && (
          <button
            type="button"
            className="ml-1 rounded bg-blue-50 px-1 py-0.5 text-[10px] text-blue-700 hover:bg-blue-100"
            aria-label={`추정 묶음 ${art.group_count}건 ${expanded ? "접기" : "펼치기"}`}
            aria-expanded={expanded}
            onClick={(e) => { e.stopPropagation(); setExpanded(v => !v); }}
          >
            추정 묶음 {art.group_count}건 {expanded ? "▲" : "▼"}
          </button>
        )}
        {art.same_addr_cnt != null && art.same_addr_cnt > 1 && (
          <span
            className="ml-1 rounded bg-amber-50 px-1 py-0.5 text-[10px] text-amber-800"
            title="네이버가 제공한 동일 주소 매물 수입니다. 동일 매물로 확정된 건수는 아니며 목록에서 자동 제외하지 않습니다."
          >
            동일주소 {art.same_addr_cnt}건
          </span>
        )}
      </Td>
      <Td>{art.floor_info || "-"}</Td>
      <Td className="text-right font-semibold text-gray-900">
        {price}
        {art.previous_price != null &&
          art.numeric_price != null &&
          art.previous_price !== art.numeric_price && (
            <span
              className={`ml-1 text-xs font-normal ${
                art.numeric_price < art.previous_price ? "text-blue-600" : "text-red-600"
              }`}
            >
              {art.numeric_price < art.previous_price ? "↓" : "↑"}
              {Math.abs(art.numeric_price - art.previous_price).toLocaleString()}
            </span>
          )}
      </Td>
      <Td className="text-right">{area}</Td>
      <Td className="text-right">{ppyeong}</Td>
      <Td className="text-right">
        {art.monthly_rent_yield != null ? (
          <span
            className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
              art.monthly_rent_yield >= 10
                ? "bg-blue-100 text-blue-700"
                : art.monthly_rent_yield >= 5
                ? "bg-emerald-100 text-emerald-700"
                : art.monthly_rent_yield < 3
                ? "bg-yellow-100 text-yellow-700"
                : "bg-emerald-50 text-emerald-600"
            }`}
          >
            {art.monthly_rent_yield}%
          </span>
        ) : art.article_jeonse_ratio != null ? (
          <span
            className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
              art.article_jeonse_ratio > 80
                ? "bg-red-100 text-red-700"
                : "bg-blue-50 text-blue-600"
            }`}
          >
            {art.article_jeonse_ratio}%
          </span>
        ) : (
          "-"
        )}
      </Td>
      <Td className="text-center">{rooms}</Td>
      <Td className="text-center">{moveIn}</Td>
      <Td className="text-right">{maint}</Td>
      <Td className="text-center">{art.direction || "-"}</Td>
      <Td className="max-w-62.5 truncate" title={art.article_feature_desc || ""}>
        {art.article_feature_desc || "-"}
      </Td>
      <Td>{art.realtor_name || "-"}</Td>
      <Td className="text-center">{confirm}</Td>
    </TableRow>
    {expanded && art.group_members && art.group_members.length > 1 && (
      <TableRow className="bg-blue-50/50">
        <TableCell colSpan={COLUMNS.length + 1 + (onCheck ? 1 : 0)} className="p-3">
          <div className="text-xs font-semibold text-gray-700 mb-2">추정 묶음의 원본 등록 {art.group_members.length}건 — 동일 호실 확정 아님</div>
          <div className="flex flex-wrap gap-2">
            {art.group_members.map(member => (
              <div key={member.article_no} className="flex items-center gap-1 border rounded bg-white px-2 py-1">
                {onCheck && (
                  <input type="checkbox" aria-label={`묶음 원본 매물 ${member.article_no} 선택`}
                    checked={!!selectedArticleNos?.has(member.article_no)}
                    onChange={(e) => onCheck(member.article_no, e.target.checked)} />
                )}
                <button type="button" className="text-xs text-blue-700 hover:underline"
                  onClick={() => onClick?.(member.article_no)}
                  aria-label={`원본 매물 ${member.article_no} ${member.realtor_name || "중개사 미상"} 상세 보기`}>
                  {member.realtor_name || "중개사 미상"} · {member.deal_or_warrant_prc || "가격 미상"}
                </button>
              </div>
            ))}
          </div>
        </TableCell>
      </TableRow>
    )}
    </>
  );
});

export default memo(ArticleTable);

function Td({
  children,
  className = "",
  title,
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
  onClick?: (e: React.MouseEvent<HTMLTableCellElement>) => void;
}) {
  return (
    <TableCell
      className={`px-2 py-1.5 whitespace-nowrap text-xs text-gray-700 border-r border-gray-100 last:border-r-0 ${className}`}
      title={title}
      onClick={onClick}
    >
      {children}
    </TableCell>
  );
}
