/**
 * 관심 단지 매매호가 추적 타입 — BE routers/price_watch.py · services/price_watch.py 짝꿍 (V069)
 */

export interface PriceWatchTarget {
  id: number;
  complex_no: string;
  complex_name: string | null;
  area_m2: number | null;
  pyeong: number | null;
  label: string | null;
  created_at: string | null;
  first_snapshot: string | null;
  last_snapshot: string | null;
  snapshot_days: number;
}

export interface PriceWatchTargetsResponse {
  targets: PriceWatchTarget[];
  max_targets: number;
}

export interface PriceWatchArea {
  area_m2: number;
  pyeong: number | null;
  supply_area_m2: number | null;
  supply_pyeong: number | null;
  count: number;
  min_price: number | null;
  max_price: number | null;
}

export interface PriceWatchAreasResponse {
  complex_no: string;
  complex_name: string | null;
  articles_crawled_at: string | null;
  areas: PriceWatchArea[];
}

export interface PriceWatchPeriod {
  start: string;
  end: string;
  days: number;
}

export interface UnitSeriesPoint {
  date: string;
  price: number;
  min: number;
  max: number;
  listings: number;
}

export type UnitConfidence = "높음" | "보통" | "낮음";

export interface PriceWatchUnit {
  unit_key: string;
  complex_no: string;
  complex_name: string | null;
  building: string | null;
  floor: string | null;
  floor_info: string | null;
  area_m2: number | null;
  pyeong: number | null;
  confidence: UnitConfidence;
  first_date: string;
  first_price: number;
  last_date: string;
  last_price: number;
  change_amount: number;
  change_pct: number | null;
  min_price: number;
  max_price: number;
  observations: number;
  price_moves: number;
  listings_now: number;
  status: "active" | "gone";
  series: UnitSeriesPoint[];
}

export interface PriceWatchUnitsResponse {
  period: PriceWatchPeriod;
  summary: {
    unit_count: number;
    tracked_count: number;
    up_count: number;
    down_count: number;
    flat_count: number;
    median_change_pct: number | null;
    avg_change_pct: number | null;
    gone_count: number;
  };
  units: PriceWatchUnit[];
}

export interface BasketPoint {
  date: string;
  avg_price: number;
  avg_ppy: number | null;
  unit_count: number;
  index: number;
  complex_coverage: number;
  complex_count: number;
}

export interface BasketTargetPoint {
  date: string;
  avg_price: number;
  avg_ppy: number | null;
  unit_count: number;
}

export interface BasketTarget {
  target_id: number;
  complex_no: string;
  complex_name: string | null;
  area_m2: number | null;
  pyeong: number | null;
  label: string | null;
  first_avg_price: number | null;
  last_avg_price: number | null;
  change_pct: number | null;
  ppy_change_pct: number | null;
  series: BasketTargetPoint[];
}

export interface PriceWatchBasketResponse {
  period: PriceWatchPeriod;
  summary: {
    first_date: string | null;
    last_date: string | null;
    first_avg_price: number | null;
    last_avg_price: number | null;
    avg_price_change_pct: number | null;
    avg_ppy_change_pct: number | null;
    same_unit_index_change_pct: number | null;
    observation_days: number;
  };
  series: BasketPoint[];
  targets: BasketTarget[];
}
