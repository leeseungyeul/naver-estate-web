import type { ArticleFilters } from "@/types";

export const queryKeys = {
  // Public
  stats: ["stats"] as const,
  regions: ["regions"] as const,

  // Search
  search: (keyword: string, types?: string) =>
    ["search", keyword, types] as const,
  /** DB 단지명 검색 (/api/complexes/search) — 라이브 크롤 search 키와 분리 */
  complexSearchDb: (keyword: string) => ["complexSearchDb", keyword] as const,
  regionSearch: (
    sido: string,
    sigungu?: string,
    dong?: string,
    types?: string,
  ) => ["regionSearch", sido, sigungu, dong, types] as const,

  // Complex
  complex: (no: string) => ["complex", no] as const,
  articles: (no: string, filters?: ArticleFilters, grouped?: boolean) =>
    ["articles", no, filters, grouped] as const,
  /** invalidation prefix — 해당 단지의 모든 articles 쿼리 무효화용 */
  articlesAll: (no: string) => ["articles", no] as const,
  pyeongDetails: (no: string) => ["pyeongDetails", no] as const,
  officialPrices: (no: string) => ["officialPrices", no] as const,
  complexSubway: (no: string) => ["complexSubway", no] as const,
  /** 단지 공동주택 관리비 (K-apt) — 데이터 없는 단지는 null 캐시 */
  complexKapt: (no: string) => ["complexKapt", no] as const,
  priceStats: (no: string) => ["priceStats", no] as const,
  priceHistory: (no: string, tradeType?: string, areaNo?: string) =>
    ["priceHistory", no, tradeType, areaNo] as const,
  /** invalidation prefix — 해당 단지의 모든 priceHistory 쿼리 무효화용 */
  priceHistoryAll: (no: string) => ["priceHistory", no] as const,
  /** 개별 실거래 점 (거래 1건 = 점 1건) */
  tradePoints: (no: string, tradeType?: string, area2M2?: number) =>
    ["tradePoints", no, tradeType, area2M2] as const,

  // Article detail
  articleLive: (articleNo: string) => ["articleLive", articleNo] as const,
  articlePriceHistory: (articleNo: string) => ["articlePriceHistory", articleNo] as const,

  // Crawl status (polling)
  crawlStatus: (no: string) => ["crawlStatus", no] as const,
  priceCollectStatus: (no: string) => ["priceCollectStatus", no] as const,

  // Admin (token excluded from keys for security)
  admin: {
    stats: () => ["admin", "stats"] as const,
    users: (params?: Record<string, unknown>) =>
      ["admin", "users", params] as const,
    // params 없이 부르면 접두 키 ["admin","crawlJobs"] — 무효화할 때 모든 목록 키를 부분 일치로 잡는다.
    // (3번째 칸이 undefined 이면 {status,page} 가 든 목록 키와 일치하지 않아 취소 뒤 목록이 안 새로고침됐다)
    crawlJobs: (params?: Record<string, unknown>) =>
      params === undefined
        ? (["admin", "crawlJobs"] as const)
        : (["admin", "crawlJobs", params] as const),
    auditLogs: (params?: Record<string, unknown>) =>
      ["admin", "auditLogs", params] as const,
    schedulerStatus: () => ["admin", "schedulerStatus"] as const,
    schedulerCalendar: (year: number, month: number, mode: string) =>
      ["admin", "schedulerCalendar", year, month, mode] as const,
    verifications: (params?: Record<string, unknown>) =>
      ["admin", "verifications", params] as const,
    errorStats: (days: number) => ["admin", "errorStats", days] as const,
    naverCalls: () => ["admin", "naverCalls"] as const,
    traffic: () => ["admin", "traffic"] as const,
    dataFreshness: () => ["admin", "dataFreshness"] as const,
    crawlFailures: (hours: number = 24) => ["admin", "crawlFailures", hours] as const,
    quotaStatus: () => ["admin", "quotaStatus"] as const,
  },

  // 중개사 검증
  verification: {
    status: () => ["verification", "status"] as const,
  },

  // 빌링키 자동결제 (등록 카드 목록)
  billing: {
    cards: () => ["billing", "cards"] as const,
  },

  // 미분양 (mibunyang)
  mb: {
    guList: (region: string) => ["mb", "guList", region] as const,
    apartments: (region: string, gu?: string, page?: number, sortBy?: string, keyword?: string) =>
      ["mb", "apartments", region, gu, page, ...(sortBy ? [sortBy] : []), ...(keyword ? [keyword] : [])] as const,
    apartmentDetail: (id: string) => ["mb", "apartment", id] as const,
    unsold: (region: string, gu?: string, page?: number, sortBy?: string, keyword?: string) =>
      ["mb", "unsold", region, gu, page, ...(sortBy ? [sortBy] : []), ...(keyword ? [keyword] : [])] as const,
    unsoldHistory: (id: string) => ["mb", "unsoldHistory", id] as const,
    regions: (region: string, gu?: string) =>
      ["mb", "regions", region, gu] as const,
    trades: (region: string, gu?: string, dong?: string, page?: number, sortBy?: string) =>
      ["mb", "trades", region, gu, dong, page, ...(sortBy ? [sortBy] : [])] as const,
    presale: (presaleType: string, region?: string, gu?: string, page?: number, sortBy?: string, keyword?: string) =>
      ["mb", "presale", presaleType, region, gu, page, ...(sortBy ? [sortBy] : []), ...(keyword ? [keyword] : [])] as const,
    presaleDetail: (id: string) => ["mb", "presaleDetail", id] as const,
    competition: (region?: string, gu?: string, page?: number, sortBy?: string, keyword?: string) =>
      ["mb", "competition", region, gu, page, ...(sortBy ? [sortBy] : []), ...(keyword ? [keyword] : [])] as const,
    officetelRental: (region?: string, page?: number) =>
      ["mb", "officetelRental", region, page] as const,
  },
} as const;
