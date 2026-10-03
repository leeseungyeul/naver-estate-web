/** DB 통계 */
export interface DbStats {
  complex_count: number;
  article_count: number;
}

/** 지역 구조: {시도: {시군구: [동, ...]}} */
export type Regions = Record<string, Record<string, string[]>>;

/** 면적별 가격 통계 — 거래유형별 평균가 */
export interface AreaPriceStat {
  label: string;
  maemae?: number;
  jeonse?: number;
  wolse?: number;
  maemae_count?: number;
  jeonse_count?: number;
  wolse_count?: number;
}

/** 층수별 가격 통계 — 거래유형별 min/avg/max */
export interface FloorPriceStat {
  label: string;
  maemae_avg?: number; maemae_min?: number; maemae_max?: number; maemae_count?: number;
  jeonse_avg?: number; jeonse_min?: number; jeonse_max?: number; jeonse_count?: number;
  wolse_avg?: number;  wolse_min?: number;  wolse_max?: number;  wolse_count?: number;
}

export interface PriceStats {
  complex_no: string;
  total_articles: number;
  by_area: AreaPriceStat[];
  by_floor: FloorPriceStat[];
}

/** 단지 가격 추이 항목 */
export interface PriceHistoryItem {
  trade_type: string;
  trade_type_label: string;
  price_upper: number | null;
  price_lower: number | null;
  price_avg: number | null;
  base_month: string;
}

/** 단지 가격 추이 응답 */
export interface PriceHistoryResponse {
  complex_no: string;
  items: PriceHistoryItem[];
}

/** 단지 개별 실거래 점 (거래 1건 = 점 1건) */
export interface TradePoint {
  year_month: string;
  deal_day: string | null;
  price: number;
  area2_m2: number | null;
  floor_number: number | null;
}

/** 단지 개별 실거래 점 응답 */
export interface TradePointsResponse {
  complex_no: string;
  points: TradePoint[];
}

/** 단지 공동주택 공시가격 평형별 항목 */
export interface OfficialPriceItem {
  prvuse_ar: number;
  price_median: number;
  ho_count: number;
}

/** 단지 공동주택 공시가격 응답 (무료 공개, 게이트 없음) */
export interface OfficialPriceResponse {
  complex_no: string;
  year: string | null;
  items: OfficialPriceItem[];
}

/**
 * 단지 인근 지하철역 1건.
 * lines = 환승역의 전 노선 (BE 가 역명으로 그룹핑해 배열로 내려줌).
 */
export interface SubwayStationNear {
  station_name: string;
  lines: string[];
  distance_m: number;
}

/** 단지 인근 지하철역 응답 — 거리 오름차순 최대 3개, 3km 이내. 없으면 stations: [] */
export interface SubwayNearResponse {
  stations: SubwayStationNear[];
}

/**
 * 단지 공동주택 관리비 (K-apt, GET /api/complexes/{no}/kapt).
 *
 * 전국 6.4만 단지 중 K-apt 의무관리단지(~1.5만)만 데이터가 존재한다 — 매칭·관리비가
 * 없으면 BE 가 404 로 응답하므로 **404 는 다수의 정상 케이스**이고, FE 래퍼는 이를
 * null 로 변환한다 (getComplexKapt 주석 참조).
 *
 * 금액 단위는 **원**(won) — 화면 표시 시 만원 환산이 필요하다.
 */
export interface KaptInfo {
  kapt_code: string;
  kapt_name: string;
  /** 복도유형 (계단식·복도식·혼합식 등). 미상이면 null */
  corridor_type: string | null;
  /** 관리비 기준월 YYYYMM */
  cost_month: string;
  /** 공용관리비 총액 (원) */
  common_cost: number | null;
  /** 개별사용료 총액 (원) */
  individual_cost: number | null;
  /** 관리비 총액 (원) */
  total_cost: number | null;
  /** 세대당 관리비 (원) */
  cost_per_household: number | null;
  household_count: number | null;
}
