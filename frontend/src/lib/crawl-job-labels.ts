/**
 * 크롤 작업 유형(job_type) 한글 라벨 + 한 줄 설명.
 * BE crawler/* 에서 사용하는 job_type 을 화면에서 사람말로 보여주기 위한 매핑.
 *
 * ⚠ label 은 BE `backend/crawler/plain_words.py` 의 `JOB_WORDS` 값과 **글자까지 같아야** 한다
 *   (사장님 결정: 관리자 화면·텔레그램 알림·달력이 같은 작업을 한 이름으로 부른다).
 *   정본은 BE 쪽이다 — 이름을 바꾸려면 JOB_WORDS 를 먼저 고치고 여기를 따라 고친다.
 *   `src/lib/__tests__/crawl-job-labels-sync.test.ts` 가 두 사전을 키별로 대조해 어긋나면 실패시킨다.
 *   키 누락(BE 가 새 job_type 을 만들었는데 여기 없음)은 scripts/check-job-labels.mjs 가 CI 에서 잡는다.
 */

export const CRAWL_JOB_LABELS: Record<string, { label: string; desc: string }> = {
  complex_articles: {
    label: "단지 매물 가져오기",
    desc: "특정 아파트 단지의 현재 매물(매매·전세·월세) 목록을 네이버에서 가져옴",
  },
  complex_list: {
    label: "새 단지 찾기",
    desc: "키워드 검색으로 새 아파트 단지를 찾아 우리 목록에 추가",
  },
  popular_crawl: {
    label: "자주 보는 단지 미리 갱신",
    desc: "최근 자주 조회된 단지 매물을 미리 갱신해두는 정기 작업",
  },
  article_detail: {
    label: "매물 상세 내용 채우기",
    desc: "이미 가져온 매물에 사진·설명·중개사 정보 등 상세 항목을 채우는 작업",
  },
  // 스케줄러에는 backfill_detail_dawn(00:20) · backfill_detail_noon(12:20) 두 잡으로
  // 등록돼 있으나 DB 에 남는 job_type 은 둘 다 article_detail_backfill 하나다.
  // 화면은 job_type 을 보므로 여기도 한 항목만 둔다 (infra.md §잡 이름 ≠ job_type).
  article_detail_backfill: {
    label: "빠진 정보 뒤늦게 채우기",
    desc: "네이버가 항목 이름을 바꿔 비어버린 정보(난방 방식·건물 층수 등)를 나중에 다시 채우는 작업 (매일 0시 20분·낮 12시 20분)",
  },
  field_drift_monitor: {
    label: "정보 안 채워지면 알림",
    desc: "매물 정보가 갑자기 안 채워지기 시작하면 바로 알려주는 감시 작업 (매일 새벽 4시 40분)",
  },
  price_history: {
    label: "단지 시세 기록 모으기",
    desc: "단지별 매매·전세 시세의 월별 변동 이력 수집",
  },
  public_trade_data: {
    label: "정부 실거래가 받기",
    desc: "국토교통부 공공데이터로 실제 거래된 가격 가져옴",
  },
  bulk_recrawl: {
    label: "여러 단지 한꺼번에 다시 받기",
    desc: "관리자가 직접 눌러 여러 단지를 한 번에 다시 수집",
  },
  air_quality: {
    label: "동네 공기질 받기",
    desc: "에어코리아에서 측정소별 미세먼지·오존 데이터 수집 (매일 새벽 2시)",
  },
  emergency: {
    label: "응급실 위치 받기",
    desc: "전국 응급의료기관 위치·운영시간 갱신 (매월 첫째 월요일)",
  },
  childcare: {
    label: "어린이집 정보 받기",
    desc: "전국 어린이집 정원·교사·시설 정보 수집 (매월 첫째 목요일)",
  },
  crime_stats: {
    label: "동네 범죄 통계 받기",
    desc: "경찰청 공공데이터에서 시군구별 범죄 통계 수집 (분기별)",
  },

  // ── 세션 399 추가 15종 ──────────────────────────────────────────────
  // 관리자 화면에 영문 코드가 그대로 노출되던 것들. 누락 재발은
  // scripts/check-job-labels.mjs 가 CI 에서 차단.
  price_backfill: {
    label: "옛 시세 채워 넣기",
    desc: "시세 이력이 부족한 단지를 국토교통부 실거래가로 과거분까지 채움 (매일 03:30)",
  },
  complex_metric: {
    label: "단지 가치 점수 계산",
    desc: "시세 이력을 집계해 단지별 가치 지표를 계산·저장 (매일 04:30)",
  },
  officetel_presale: {
    label: "오피스텔 청약 공고 받기",
    desc: "청약홈에서 오피스텔·도시형 생활주택 청약 공고와 평형별 공급 정보 수집 (매주 월요일)",
  },
  rental_presale: {
    label: "민간임대 청약 공고 받기",
    desc: "청약홈에서 공공지원 민간임대 청약 공고와 평형별 공급 정보 수집 (매주 월요일)",
  },
  official_price: {
    label: "정부 공시가격 받기",
    desc: "V-WORLD에서 법정동별 공동주택 공시가격을 받아 단지·평형별로 저장 (매월 15일, 3~7시간 소요)",
  },
  billing_charge: {
    label: "구독료 자동 결제",
    desc: "구독 갱신일이 된 이용자의 등록된 카드로 자동 결제 실행 (매일 04:50)",
  },
  vacuum_maintenance: {
    label: "자료 보관함 정리",
    desc: "매물·거래 자료 정리로 조회 속도 유지 + 만료된 사용량 기록 청소 (매일 03:50)",
  },
  kapt_match: {
    label: "관리비 단지 연결하기",
    desc: "국토부 K-apt 전국 단지 목록과 우리 단지를 대조해 연결 (매월 21일, 최대 8시간)",
  },
  kapt_costs: {
    label: "단지 관리비 받기",
    desc: "연결된 단지의 월별 관리비 22개 항목을 받아 세대당 금액 계산 (매일 06:20·12:40·21:00)",
  },
  api_version_probe: {
    label: "정부 자료 창구 살아있나 확인",
    desc: "우리가 쓰는 공공데이터 창구 13종이 닫히지 않았는지 확인 (매주 일요일 06:40)",
  },
  complex_detail_APT: {
    label: "아파트 단지 정보 채우기",
    desc: "상세 정보가 비어 있는 아파트 단지를 골라 보강 (4시간마다)",
  },
  complex_detail_OPST: {
    label: "오피스텔 단지 정보 채우기",
    desc: "상세 정보가 비어 있는 오피스텔 단지를 골라 보강 (4시간마다)",
  },
  complex_detail_JGC: {
    label: "재건축 단지 정보 채우기",
    desc: "상세 정보가 비어 있는 재건축 단지를 골라 보강 (매주 화요일 07:00)",
  },
  complex_detail_ABYG: {
    label: "아파트 분양권 단지 정보 채우기",
    desc: "상세 정보가 비어 있는 아파트 분양권 단지를 골라 보강 (매주 수요일 07:00)",
  },
  complex_detail_OBYG: {
    label: "오피스텔 분양권 단지 정보 채우기",
    desc: "상세 정보가 비어 있는 오피스텔 분양권 단지를 골라 보강 (매주 목요일 07:00)",
  },
};

/** job_type 코드를 한글 라벨로. 미등록 코드는 코드명 그대로 반환 */
export function jobTypeLabel(code: string): string {
  return CRAWL_JOB_LABELS[code]?.label ?? code;
}

/** job_type 코드의 한 줄 설명. 미등록 코드는 빈 문자열 */
export function jobTypeDesc(code: string): string {
  return CRAWL_JOB_LABELS[code]?.desc ?? "";
}
