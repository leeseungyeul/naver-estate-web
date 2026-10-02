/** 단지 정보 */
export interface Complex {
  complex_no: string;
  complex_name: string;
  cortar_no?: string;
  real_estate_type_code?: string;
  real_estate_type_name?: string;
  latitude?: number;
  longitude?: number;
  total_household_count?: number;
  high_floor?: number;
  low_floor?: number;
  use_approve_ymd?: string;
  total_dong_count?: number;
  min_supply_area_m2?: number;
  max_supply_area_m2?: number;
  cortar_address?: string;
  sido?: string;
  sigungu?: string;
  dong?: string;
  heat_method_type?: string;
  total_parking_count?: number;
  construction_company?: string;
  floor_area_ratio?: string;
  building_coverage_ratio?: string;
  address?: string;
  road_address?: string;
  heat_fuel_type?: string;
  parking_count_by_household?: number;
  management_office_tel?: string;
  last_crawled_at?: string;
  detail_crawled_at?: string;
  article_count?: number;
  /** 거래유형별 활성 매물 수 (매매/전세/월세/단기임대) */
  trade_type_counts?: { 매매: number; 전세: number; 월세: number; 단기임대: number };
  nearby_median_price?: number;
  jeonse_rate?: number;
  recent_trades_6m?: number;
  filter_options?: FilterOptions;
  has_pool?: boolean;
}

/** 매물 정보 */
export interface Article {
  article_no: string;
  complex_no: string;
  trade_type_name?: string;
  building_name?: string;
  floor_info?: string;
  deal_or_warrant_prc?: string;
  rent_prc?: string;
  area1_m2?: number;
  area2_m2?: number;
  area2_pyeong?: number;
  direction?: string;
  article_feature_desc?: string;
  tags?: string[];
  realtor_name?: string;
  article_confirm_ymd?: string;
  complex_name?: string;
  numeric_price?: number;
  numeric_rent_price?: number;
  price_per_pyeong?: number;
  room_count?: number;
  bathroom_count?: number;
  move_in_date?: string;
  maintenance_cost?: string;
  numeric_maintenance_cost?: number;
  heating_type?: string;
  total_floor_count?: number;
  jibun_address?: string;
  detail_description?: string;
  photo_urls?: string[];
  representative_img_url?: string;
  realtor_phone_display?: string;
  realtor_address?: string;
  parking_count?: string;
  acquisition_tax?: string;
  broker_fee?: string;
  latitude?: number;
  longitude?: number;
  is_verified?: boolean;
  is_presale?: boolean;
  detail_crawled?: boolean;
  use_approve_ymd?: string;
  article_name?: string;
  first_seen_at?: string;
  last_seen_at?: string;
  previous_price?: number;
  price_changed_at?: string;
  total_household_count?: number;
  complex_address?: string;
  article_real_estate_type_name?: string;
  realtor_id?: string;
  realtor_phone?: string;
  monthly_rent_yield?: number;      // 월세 수익률 (%)
  article_jeonse_ratio?: number;    // 개별 전세가율 (%)
  // #9 매물 가치 필드 (네이버 리스트 API 응답)
  price_change_state?: string;      // 가격변동 (SAME/INCREASE/DECREASE)
  article_status?: string;          // 거래상태 코드
  same_addr_cnt?: number;           // 동일주소 매물 묶음 수
  group_count?: number;             // 조회 전용: 보수적 추정 묶음의 원본 행 수
  group_members?: Article[];        // 조회 전용: 펼치기용 원본 매물
  same_addr_min_prc?: string;       // 동일주소 최저가
  same_addr_max_prc?: string;       // 동일주소 최고가
  verification_type_code?: string;  // 검증유형 코드
  is_direct_trade?: boolean;        // 직거래 여부
  cp_name?: string;                 // 제공 플랫폼명
  site_image_count?: number;        // 사진 수
  same_addr_premium_min?: string;   // 분양권 프리미엄 최저
  same_addr_premium_max?: string;   // 분양권 프리미엄 최고
  premium_prc?: string;             // 분양권 개별 매물 프리미엄
  // #10 매물 상세 4필드 (네이버 상세 API articleDetail 응답)
  walking_time_to_subway?: number;  // 지하철역 도보시간 (분)
  isale_right_type_name?: string;   // 분양권 유형명 (분양권 매물만)
  detail_status_code?: string;      // 상세 API 매물 상태코드 (cf. article_status = 리스트 API)
  trade_complete?: boolean;         // 거래완료 여부
}

/** 매물 가격 변동 이력 항목 */
export interface ArticlePriceHistoryItem {
  price: number | null;
  rent_price: number | null;
  recorded_at: string | null;
}

/** 면적별 상세 */
export interface PyeongDetail {
  pyeong_no: number;
  pyeong_name?: string;
  supply_area?: string;
  supply_area_double?: number;
  exclusive_area?: string;
  exclusive_rate?: string;
  household_count_by_pyeong?: string;
  entrance_type?: string;
  room_count?: number;
  bathroom_count?: number;
  avg_maintenance_cost?: number;
  summer_maintenance_cost?: number;
  winter_maintenance_cost?: number;
  floor_plan_url?: string;
  supply_pyeong?: string;
  exclusive_pyeong?: string;
  latest_maintenance_cost?: number;
  maintenance_cost_basis?: string;
}

/** 정렬 옵션 (백엔드 Literal과 동기화) */
export type SortBy = "rank" | "price_asc" | "price_desc" | "area_asc" | "area_desc" | "ppyeong_asc" | "ppyeong_desc" | "maintenance_asc" | "maintenance_desc" | "confirm_asc" | "confirm_desc" | "building_asc";

/** 필터 옵션 */
export interface ArticleFilters {
  trade_types?: string;
  min_price?: number;
  max_price?: number;
  min_rent?: number;
  max_rent?: number;
  min_area_m2?: number;
  max_area_m2?: number;
  min_rooms?: number;
  min_baths?: number;
  direction?: string;
  min_ppyeong?: number;
  max_ppyeong?: number;
  min_maintenance?: number;
  max_maintenance?: number;
  building_name?: string;
  verified_only?: boolean;
  max_building_age?: number;
  move_in_type?: string;
  estate_type?: string;
  min_floor?: number;
  max_floor?: number;
  tags?: string;
  min_yield?: number;
  max_yield?: number;
  selected_articles?: string;
  sort_by?: SortBy;
  page?: number;
  page_size?: number;
}

/** 필터 옵션 (단지별 동적 값) */
export interface FilterOptions {
  building_names: string[];
  tags: string[];
  directions: string[];
}

export interface ArticlesResponse {
  articles: Article[];
  total: number;
  raw_total?: number;
  page: number;
  page_size: number;
}
