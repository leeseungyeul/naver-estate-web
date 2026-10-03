-- V068: 단지 실거래 개별 원본 (개별 점 차트용)
-- 기존 complex_price_history 는 월별 min/max/avg 집계 행이라 원본 가격을 잃는다.
-- complex_trade_raw 는 거래 1건 = 행 1건으로 원본을 보존한다 (거래 1건 = 점 1건 차트).
-- complex_no FK 없음 — 단지 매칭 실패 원본도 NULL 로 보존 (complex_official_prices 답습).

CREATE TABLE IF NOT EXISTS complex_trade_raw (
    id BIGSERIAL PRIMARY KEY,
    complex_no VARCHAR(20),
    trade_type VARCHAR(10) NOT NULL,
    deal_year_month VARCHAR(6) NOT NULL,
    deal_day VARCHAR(2),
    price INTEGER NOT NULL,
    area2_m2 DOUBLE PRECISION,
    floor_number INTEGER,
    apt_dong VARCHAR(50),
    source VARCHAR(20) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ctr_complex_ym ON complex_trade_raw (complex_no, deal_year_month);
