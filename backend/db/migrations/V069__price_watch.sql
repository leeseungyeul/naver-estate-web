-- V069: 관심 단지 호가 추적 (매매호가 변동률 모니터링)
--
-- 배경: articles 는 "지금 가격" 1개(+직전가 1개)만 들고, 네이버에서 사라진 매물은
-- 물리 삭제된다(services/upsert.py delete_missing_articles). article_price_history 도
-- article_no 만 있어 매물이 지워지면 어느 단지·동·층이었는지 잃는다. 그래서 과거 호가
-- 추이를 되살릴 수 없다 — 날짜별 기록(스냅샷)을 따로 남겨야 한다.
--
-- price_watch_targets   = 사용자가 등록한 관심 대상(단지 + 전용면적, 면적 NULL = 전체 평형)
-- price_watch_snapshots = 관심 단지의 활성 매매 매물을 날짜(KST)별로 1행씩 기록
--                         (같은 날 여러 번 수집되면 마지막 값으로 덮어씀)
--
-- 기록 시점 = 그 단지 매물 수집이 끝까지 성공했을 때(crawler/service_discover.py ·
-- routers/live/_crawl_bg.py), 그리고 대상 등록 직후 1회(현재 DB 상태).
-- 관심 단지는 "자주 보는 단지 미리 갱신"(10:45/14:45/19:15) 선정에서 먼저 뽑혀
-- 하루 1회 이상 갱신된다 — 선정 몫(배치) 안에서 순서만 바뀌어 네이버 호출 총량 불변.
--
-- 추가만 하는 마이그레이션(기존 표 변경 0). infra.md §권한·정책: 새 public 표는
-- Supabase 기본 권한으로 anon/authenticated 에 열리므로 RLS 를 켜고 클라이언트 권한을
-- 회수한다 — 접근은 backend 경유만.
--
-- 배포 순서: 이 SQL 을 먼저 적용한 뒤 backend 재시작. 코드가 먼저 떠도 수집은 멈추지 않지만
-- (기록·관심 단지 우선 선정이 best-effort) 호가 추적 API 는 표가 생길 때까지 500 이다.
-- 적용 후 mibunyang 기준선 재승인 요청(infra.md §권한·정책): 표 2개 신설·RLS 켬·anon/authenticated 표·시퀀스 권한 회수.

CREATE TABLE IF NOT EXISTS price_watch_targets (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    complex_no VARCHAR(20) NOT NULL,
    area_m2 DOUBLE PRECISION,
    label VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- NULLS NOT DISTINCT (PG15+, 운영 17.6): area_m2 NULL(전체 평형)끼리도 중복으로 본다.
    -- 기본 UNIQUE 는 NULL 을 서로 다르게 봐서 같은 단지 "전체 평형"이 두 번 들어갈 수 있다.
    CONSTRAINT uq_price_watch_target UNIQUE NULLS NOT DISTINCT (user_id, complex_no, area_m2)
);
CREATE INDEX IF NOT EXISTS idx_price_watch_targets_complex ON price_watch_targets (complex_no);

CREATE TABLE IF NOT EXISTS price_watch_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    complex_no VARCHAR(20) NOT NULL,
    article_no VARCHAR(20) NOT NULL,
    building_name VARCHAR(50),
    floor_info VARCHAR(20),
    area1_m2 DOUBLE PRECISION,
    area2_m2 DOUBLE PRECISION,
    price INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_price_watch_snapshot UNIQUE (snapshot_date, article_no)
);
CREATE INDEX IF NOT EXISTS idx_price_watch_snapshots_complex_date
    ON price_watch_snapshots (complex_no, snapshot_date);

ALTER TABLE price_watch_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_watch_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON price_watch_targets FROM anon, authenticated;
REVOKE ALL ON price_watch_snapshots FROM anon, authenticated;
REVOKE ALL ON SEQUENCE price_watch_targets_id_seq FROM anon, authenticated;
REVOKE ALL ON SEQUENCE price_watch_snapshots_id_seq FROM anon, authenticated;

-- 역방향 (롤백):
-- DROP TABLE IF EXISTS price_watch_snapshots;
-- DROP TABLE IF EXISTS price_watch_targets;
