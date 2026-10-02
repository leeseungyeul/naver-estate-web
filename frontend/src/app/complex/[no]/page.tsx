"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  getComplex,
  getArticles,
  getPyeongDetails,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { useSmartBack } from "@/hooks/useSmartBack";
import { useExport } from "@/hooks/useExport";
import { useFilterParams } from "@/hooks/useFilterParams";
import { useFavoriteStatus } from "@/hooks/useFavorites";
import { useCompare } from "@/hooks/useCompare";
import { useCrawlAction } from "@/hooks/useCrawlAction";
import type { Article, ArticleFilters, FilterOptions, ArticlesResponse } from "@/types";
import FilterBar from "@/components/FilterBar";
import FilterBarMobileSheet from "@/components/FilterBarMobileSheet";
import FilterChipsSummary from "@/components/filter/FilterChipsSummary";
import ArticleTable from "@/components/ArticleTable";
import ArticleCardMobile from "@/components/ArticleCardMobile";
import ArticleViewToggle from "@/components/ArticleViewToggle";
import ArticlePageSizeSelect from "@/components/ArticlePageSizeSelect";
import ArticleDetail from "@/components/ArticleDetail";
import type { ArticlePageSize } from "@/lib/storage";
import { useArticleViewPreferences } from "@/hooks/useArticleViewPreferences";
import { usePopstateRefresh } from "@/hooks/usePopstateRefresh";
import { useSessionToken } from "@/hooks/useSessionToken";
import Pagination from "@/components/Pagination";
import HintIcon from "@/components/HintIcon";
import ComplexHeader from "@/components/complex/ComplexHeader";
import CompareFloatingBar from "@/components/CompareFloatingBar";
import ComplexLoadState from "@/components/complex/ComplexLoadState";
import CrawlMessage from "@/components/complex/CrawlMessage";
import ComplexDashboard from "@/components/complex/ComplexDashboard";
import PrintButton from "@/components/complex/PrintButton";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import LockedDataCard, { isAuthGateError } from "@/components/ui/locked-data-card";

export default function ComplexDetailPage() {
  const params = useParams();
  const goBack = useSmartBack();
  const rawNo = params.no;
  const complexNo = Array.isArray(rawNo) ? rawNo[0] : rawNo ?? "";

  // 필터/정렬/페이지 — URL을 단일 소스로 사용
  const { filters, page: currentPage, sortBy: activeSortBy, setFilters, setPage, setSortBy } = useFilterParams();
  const { starred, toggle: toggleFavorite } = useFavoriteStatus(complexNo);
  const compare = useCompare();
  const [selectedArticleNos, setSelectedArticleNos] = useState<Set<string>>(new Set());
  const [filterOpen, setFilterOpen] = useState(true);
  const [groupDuplicates, setGroupDuplicates] = useState(true);
  const [selectedArticle, setSelectedArticle] = useState<string | null>(null);
  const [error, setError] = useState("");
  const { sessionToken, tokenError, tokenReady, dismissTokenError } = useSessionToken();
  const [filterOptions, setFilterOptions] = useState<FilterOptions | undefined>(undefined);
  const { articleViewMode, pageSize, setPageSize, handleViewModeChange } = useArticleViewPreferences();

  // 인쇄 대상 ref — 페이지 본문 전체 (헤더 + 시세 + 매물 + 정보)
  const printRef = useRef<HTMLDivElement>(null);

  // 브라우저 뒤로/앞으로 시에만 FilterBar 리마운트
  const { navKey } = usePopstateRefresh();

  const { exporting, exportError, clearExportError, handleExport: doExport } = useExport();

  const complexQuery = useQuery({
    queryKey: queryKeys.complex(complexNo),
    queryFn: () => getComplex(complexNo),
    enabled: !!complexNo && /^\d+$/.test(complexNo),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (complexQuery.data?.filter_options) {
      setFilterOptions(complexQuery.data.filter_options); // eslint-disable-line react-hooks/set-state-in-effect -- 쿼리 데이터 동기화
    }
  }, [complexQuery.data]);

  const articlesQueryKey = queryKeys.articles(complexNo, {
    ...filters,
    page: currentPage,
    page_size: pageSize,
  }, groupDuplicates);

  const articlesQuery = useQuery<ArticlesResponse>({
    queryKey: articlesQueryKey,
    queryFn: () => getArticles(complexNo, {
      ...filters,
      page: currentPage,
      page_size: pageSize,
    }, sessionToken, groupDuplicates),
    // tokenReady 가드: 토큰 해석 완료 후 실행 — 토큰 도착 전 undefined 로 먼저 쏴서
    // 403→queryKey 불변 refetch 안 됨(승인 중개사 잠금 오인) 차단 (B2 게이트)
    enabled: !!complexNo && /^\d+$/.test(complexNo) && tokenReady,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[3] === groupDuplicates ? keepPreviousData(previous) : undefined,
    staleTime: 30_000,
  });

  const pyeongQuery = useQuery({
    queryKey: queryKeys.pyeongDetails(complexNo),
    queryFn: () => getPyeongDetails(complexNo, sessionToken),
    enabled: !!complexNo && /^\d+$/.test(complexNo) && tokenReady,
    staleTime: 60_000,
  });

  const complex = complexQuery.data ?? null;
  const articles = articlesQuery.data?.articles ?? [];
  const totalCount = articlesQuery.data?.total ?? 0;
  const pyeongDetails = pyeongQuery.data?.pyeong_details ?? [];
  const loading = complexQuery.isLoading;
  const tableLoading = articlesQuery.isFetching && !articlesQuery.isLoading;

  useEffect(() => {
    if (complex) {
      document.title = `${complex.complex_name} - 아파트·오피스텔`;
    }
  }, [complex]);

  useEffect(() => {
    if (complexQuery.isError) {
      setError("단지 정보를 불러올 수 없습니다."); // eslint-disable-line react-hooks/set-state-in-effect -- 에러 상태 동기화
    }
  }, [complexQuery.isError]);

  const {
    crawling,
    message: crawlMessage,
    messageType: crawlMessageType,
    progress: crawlProgress,
    clearMessage: clearCrawlMessage,
    handleCrawl,
  } = useCrawlAction(complexNo, {
    auto: true,
    autoEnabled:
      complexQuery.isSuccess && articlesQuery.isSuccess && pyeongQuery.isSuccess,
  });

  const handleSortChange = useCallback(
    (newSortBy: string) => {
      setSortBy(newSortBy);
      setSelectedArticleNos(new Set());
    },
    [setSortBy]
  );

  const handleFilterChange = useCallback(
    (newFilters: ArticleFilters) => {
      setFilters(newFilters);
      setSelectedArticleNos(new Set());
    },
    [setFilters]
  );

  const hasActiveFilters = Object.keys(filters).some(k => k !== "sort_by");
  const resetFilters = useCallback(() => {
    setFilters({});
    setSelectedArticleNos(new Set());
  }, [setFilters]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      setPage(newPage);
      // 새 페이지 첫 매물이 보이게 목록 상단 복귀 — smooth 는 직후 리렌더에 취소될 수 있어 auto
      document.getElementById("section-articles")?.scrollIntoView({ behavior: "auto", block: "start" });
    },
    [setPage]
  );

  const handlePageSizeChange = useCallback(
    (newSize: ArticlePageSize) => {
      const firstItemIndex = (currentPage - 1) * pageSize;
      const maxPage = Math.max(1, Math.ceil(totalCount / newSize));
      const newPage = Math.min(Math.floor(firstItemIndex / newSize) + 1, maxPage);
      setPageSize(newSize);
      setPage(newPage);
    },
    [currentPage, pageSize, totalCount, setPage, setPageSize]
  );

  const handleSelectionChange = (articleNo: string, checked: boolean) => {
    setSelectedArticleNos(prev => {
      const next = new Set(prev);
      if (checked) next.add(articleNo);
      else next.delete(articleNo);
      return next;
    });
  };

  const handleSelectAll = (checked: boolean, visibleArticles?: Article[]) => {
    if (checked) {
      const targets = visibleArticles ?? articles;
      setSelectedArticleNos(prev => {
        const next = new Set(prev);
        targets.forEach(a => (a.group_members ?? [a]).forEach(member => next.add(member.article_no)));
        return next;
      });
    } else {
      setSelectedArticleNos(new Set());
    }
  };

  const handleExport = () => doExport(complexNo, selectedArticleNos, filters);

  if (!complexNo || !/^\d+$/.test(complexNo)) {
    return <ComplexLoadState kind="invalid" />;
  }

  if (loading) {
    return <ComplexLoadState kind="loading" />;
  }

  if (error || !complex) {
    return <ComplexLoadState kind="error" error={error} />;
  }

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <div ref={printRef} className="max-w-7xl mx-auto px-4 py-6 space-y-8">
      {/* 헤더 + 인쇄 버튼 */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <ComplexHeader
          complex={complex}
          starred={starred}
          onBack={goBack}
          onToggleFavorite={() => toggleFavorite(complex.complex_name, complex.cortar_address)}
          isCompared={compare.isInCompare(complexNo)}
          compareFull={compare.isFull}
          onToggleCompare={() => compare.toggle({ complex_no: complexNo, complex_name: complex.complex_name })}
        />
        <PrintButton contentRef={printRef} documentTitle={complex.complex_name} />
      </div>

      {/* 로그인 세션 경고 */}
      {tokenError && (
        <Card className="bg-amber-50 border-amber-200 text-amber-800 px-3 py-2 no-print">
          <div className="flex justify-between items-center gap-2 text-xs">
            <span>로그인 세션을 확인할 수 없어 일부 기능(실거래가 수집)이 제한됩니다. 새로고침하거나 다시 로그인해 주세요.</span>
            <button
              type="button"
              onClick={dismissTokenError}
              aria-label="닫기"
              className="text-amber-600 hover:text-amber-900 shrink-0"
            >×</button>
          </div>
        </Card>
      )}

      {/* 📱 한눈 대시보드 (PR 6d — 모바일 2×2 + 데스크톱 4×1 단일 컴포넌트) */}
      {complex && (
        <ComplexDashboard
          complex={complex}
          complexNo={complexNo}
          pyeongDetails={pyeongDetails}
          sessionToken={sessionToken}
          onFilterChange={handleFilterChange}
        />
      )}

      {/* 🥈 매물 리스트 (spec L323 정보 위계 2순위) */}
      <section aria-labelledby="section-articles" className="space-y-4">
        <h2 id="section-articles" className="text-lg md:text-xl font-semibold">매물</h2>

        {/* 필터 바 */}
        <div className="no-print">
          {/* 모바일 (< md) — shadcn Sheet 바텀시트 (PR 3b) */}
          <div className="md:hidden">
            <FilterBarMobileSheet key={`mobile-${navKey}`} onChange={handleFilterChange} filterOptions={filterOptions} onSortChange={handleSortChange} initialFilters={filters} />
          </div>
          {/* 데스크탑 (md+) — 기존 7 드롭다운 툴바 유지 */}
          <button
            type="button"
            onClick={() => setFilterOpen(v => !v)}
            className="text-sm text-blue-600 hover:text-blue-800 mb-1 hidden md:flex items-center gap-1"
          >
            {filterOpen ? "▲ 필터 접기" : "▼ 필터 펼치기"}
          </button>
          <div className={filterOpen ? "hidden md:block" : "hidden"}>
            <FilterBar key={navKey} onChange={handleFilterChange} filterOptions={filterOptions} sortBy={activeSortBy} onSortChange={handleSortChange} initialFilters={filters} />
          </div>
        </div>

        {/* 엑셀 내보내기 에러 배너 */}
        {exportError && (
          <Card className="bg-red-50 border-red-200 text-red-600 text-sm px-4 py-2 no-print">
            <div className="flex justify-between items-center">
              <span>{exportError}</span>
              <button type="button" onClick={() => clearExportError()} className="text-red-400 hover:text-red-600" aria-label="닫기">×</button>
            </div>
          </Card>
        )}

        {/* 적용된 필터 한 줄 요약 */}
        {hasActiveFilters && <FilterChipsSummary filters={filters} />}

        {/* 매물 수 + 데이터 갱신 + 엑셀 */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 md:gap-3">
            <span className="text-base md:text-lg font-semibold">
              {articlesQuery.isSuccess
                ? groupDuplicates
                  ? `추정 묶음 ${totalCount}개 · 원본 등록 ${articlesQuery.data?.raw_total ?? totalCount}건`
                  : `원본 등록 ${totalCount}건`
                : "매물 조회 중"}
            </span>
            {tableLoading && (
              <div className="flex items-center gap-1.5" role="status" aria-label="매물 갱신 중">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
                <span className="text-xs text-blue-600">갱신 중</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-1.5 md:gap-2 no-print">
            <Button type="button" variant="outline" size="sm" onClick={() => {
              setGroupDuplicates(v => !v);
              setPage(1);
              setSelectedArticleNos(new Set());
            }}>
              {groupDuplicates ? "원본 매물 보기" : "추정 묶음 보기"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCrawl}
              disabled={crawling}
            >
              {crawling ? "갱신 중..." : "데이터 갱신"}
            </Button>
            <HintIcon text="네이버에서 최신 매물을 다시 가져옵니다 (30초~2분)" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={exporting}
            >
              {exporting
                ? "내보내는 중..."
                : selectedArticleNos.size > 0
                  ? `선택 ${selectedArticleNos.size}건 내보내기`
                  : "엑셀 내보내기"}
            </Button>
          </div>
        </div>

        {groupDuplicates && <p className="text-xs text-gray-500">네이버가 묶은 동일주소 매물 수(그룹 동기화분)와 동·층·면적·가격이 같은 등록의 보수 추정을 함께 반영한 묶음입니다. 동일 호실이 확정된 것은 아니며, 엑셀 내보내기는 원본 등록 기준입니다.</p>}

        <CrawlMessage
          crawling={crawling}
          message={crawlMessage}
          messageType={crawlMessageType}
          progress={crawlProgress}
          onClear={clearCrawlMessage}
        />

        {/* 매물 API 실패 배너 — 403(승인 권한)은 잠금 안내, 그 외는 다시 시도 */}
        {articlesQuery.isError && (
          isAuthGateError(articlesQuery.error) ? (
            <LockedDataCard label="매물 목록" />
          ) : (
            <Card className="bg-red-50 border-red-200 text-red-600 text-sm px-4 py-2">
              <div className="flex justify-between items-center gap-3">
                <span>매물 목록을 불러올 수 없습니다.</span>
                <button
                  type="button"
                  onClick={() => articlesQuery.refetch()}
                  className="text-xs border border-red-300 rounded px-2 py-1 hover:bg-red-100 shrink-0"
                >다시 시도</button>
              </div>
            </Card>
          )
        )}

        {/* 매물 테이블 / 카드 */}
        {!articlesQuery.isLoading && !articlesQuery.isError && (
          <div className={`transition-opacity duration-200 ${tableLoading ? "opacity-50" : "opacity-100"}`}>
            <div className="hidden md:block">
              <div className="flex justify-end mb-2">
                <ArticlePageSizeSelect pageSize={pageSize} onPageSizeChange={handlePageSizeChange} />
              </div>
              <ArticleTable articles={articles} onRowClick={setSelectedArticle} onSortChange={handleSortChange} selectedArticleNos={selectedArticleNos} onSelectionChange={handleSelectionChange} onSelectAll={handleSelectAll} hasActiveFilters={hasActiveFilters} onResetFilters={resetFilters} />
            </div>
            <div className="md:hidden space-y-2">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <ArticlePageSizeSelect pageSize={pageSize} onPageSizeChange={handlePageSizeChange} />
                {articles.length > 0 && (
                  <ArticleViewToggle value={articleViewMode} onChange={handleViewModeChange} />
                )}
              </div>
              <ArticleCardMobile articles={articles} onRowClick={setSelectedArticle} selectedArticleNos={selectedArticleNos} onSelectionChange={handleSelectionChange} onSelectAll={handleSelectAll} hasActiveFilters={hasActiveFilters} onResetFilters={resetFilters} viewMode={articleViewMode} />
            </div>
          </div>
        )}

        {totalPages > 1 && (
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={handlePageChange}
          />
        )}
      </section>

      {/* 비교 플로팅 바 — printRef 내부라 no-print 필수, 모달(아래 조건부)보다 DOM 앞이어야 백드롭이 바를 덮음 */}
      <div className="no-print">
        <CompareFloatingBar list={compare.list} onRemove={compare.remove} onClear={compare.clear} />
        {compare.list.length > 0 && <div className="pb-16" />}
      </div>

      {/* 매물 상세 모달 */}
      {selectedArticle && (
        <ArticleDetail articleNo={selectedArticle} onClose={() => setSelectedArticle(null)} complex={complexQuery.data} />
      )}
    </div>
  );
}
