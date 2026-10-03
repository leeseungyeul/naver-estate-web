# Backend — FastAPI + SQLAlchemy

## 디렉토리 구조

| 경로 | 역할 |
| --- | --- |
| `main.py` | FastAPI 앱 진입점, 라우터 등록, CORS |
| `deps.py` | 인증 의존성 (get_current_user, get_approved_user, get_admin_user). 관리자 판정 = `is_admin_user()` = `role == "admin"` 또는 `user_id ∈ ADMIN_USER_IDS` — **이메일 판정 금지**(세션 417) |
| `routers/live/` | 실시간 크롤링 + 실거래가 on-demand 수집 API (search 등 분할) |
| `routers/complexes.py` | 단지 조회/필터/시세/가격추이 |
| `routers/articles.py` | 매물 조회/엑셀 내보내기 (xlsxwriter 엔진) |
| `routers/admin/` | 관리자 API 분할 10 파일 (`collect`/`data`/`freshness`/`freshness_meta`/`jobs`/`naver_calls`/`recrawl`/`scheduler`/`users` + `_shared` 공통 의존성) |
| `routers/stats.py` | 통계 API |
| `routers/regions.py` | 지역 데이터 API |
| `routers/users.py` | 사용자 로그인 기록 |
| `routers/verify.py` | 공인중개사 검증 (odcloud API) |
| `routers/payment.py` | 유료 구독 결제 (PortOne V2 — prepare/complete/webhook, 멱등·환불·위변조 방어) |
| `routers/billing.py` | 빌링키 자동결제 (정기결제 — 발급 prepare/카드 등록+첫결제, 카드 여러 장 보관 + 기본 1장) |
| `routers/serializers.py` | ORM → dict 변환 barrel re-export (3모듈) |
| `routers/estate_serializers.py` | Complex/Article ORM → dict |
| `routers/filter_builder.py` | 필터 파라미터 → dict 변환 |
| `routers/mb_serializers.py` | mibunyang ORM → dict (10개 모델) |
| `routers/mb.py` | mibunyang 데이터 API (미분양/실거래/지역통계) |
| `db/models.py` | SQLAlchemy ORM 모델 (estate) |
| `db/mb_models.py` | mibunyang 테이블 ORM 모델 (같은 Base 상속) |
| `db/queries.py` | DB 쿼리 barrel re-export (5모듈) |
| `db/query_helpers.py` | 필터 조건 빌더 + 정렬 빌더 |
| `db/complex_queries.py` | 단지 조회 쿼리 |
| `db/article_queries.py` | 매물 조회 쿼리 (필터+정렬+페이지네이션) |
| `db/price_queries.py` | 가격 이력/통계/추이 쿼리 |
| `db/stats_queries.py` | DB 통계 + 필터 옵션 쿼리 |
| `db/mb_queries.py` | mibunyang 쿼리 barrel re-export (3모듈) |
| `db/mb_query_helpers.py` | mibunyang 중복 제거 + 정렬 + 필터 헬퍼 |
| `db/mb_apartment_queries.py` | mibunyang 아파트 단지 + 미분양 조회 쿼리 |
| `db/mb_misc_queries.py` | mibunyang 지역 통계 + 실거래 + 단지 부속 쿼리 |
| `db/migrations/` | Flyway 스타일 SQL 마이그레이션 (V000~V068, 69 버전 — 최신은 하단 §DB 마이그레이션 표가 진실) |
| `shared/naver_api.py` | NaverEstateAPI (수정 금지) |
| `shared/constants.py` | 상수 (수정 금지) |
| `auth/permissions.py` | 역할 체크 (require_role) + 일일 쿼터 (check_quota) |
| `auth/rate_limiter.py` | IP 기반 요청 제한 |
| `auth/audit.py` | 감사 로그 |
| `crawler/service.py` | 크롤링 서비스 barrel re-export (기존 import 호환) |
| `crawler/service_common.py` | 공통 헬퍼 (시세 upsert, 체크포인트) |
| `crawler/service_discover.py` | 단지 발견 + 매물 수집 + 상세 보강 |
| `crawler/service_price.py` | 시세 수집 (배치 + on-demand) |
| `crawler/service_public.py` | 공공데이터 실거래가 수집 |
| `crawler/service_official_price.py` | 공동주택 공시가격 수집 (법정동 루프 + 단지 매칭 + 평형별 중위가 + 읍/면 리 확장 패스 + 이름 2차 매칭 패스) |
| `crawler/service_kapt.py` | K-apt 관리비 수집(단지 관리비 받기·관리비 단지 연결하기) (단지 매칭 3중 게이트 월1회 + 월별 관리비 공용17/개별5 합산 매일) |
| `crawler/kapt_api.py` | K-apt 단지·관리비 API 클라이언트 (AptListService4·AptBasisInfoServiceV5·관리비 V3 — 공용 17·개별 5 전부 V3, 개별은 PR #435 로 V2→V3 전환 완료. BasePublicDataAPI 상속) |
| `crawler/cortar_ri_map.py` | 읍/면→리 코드 정적 dict + expand_to_ri_codes (공시가격 리 단위 확장 전용, PR-E2 세션 373) |
| `crawler/scheduler.py` | APScheduler 스케줄 (매물/시세/공공데이터/인기단지) |
| `crawler/public_data_api.py` | 국토교통부 공공데이터 API |
| `crawler/vworld_price_api.py` | V-WORLD 공동주택 공시가격 API (getApartHousingPriceAttr, 전 페이지 수집) |
| `crawler/utils.py` | AdaptiveThrottle, CheckpointManager |
| `services/cache.py` | TTLCache (동적/고정 TTL, delete_by_prefix) |
| `services/upsert.py` | DB upsert 헬퍼 (_do_upsert: pg_insert/sqlite_insert 자동 분기) |
| `services/enricher.py` | 단지 상세 정보 보강 |
| `formatters/price_core.py` | 가격 포맷 코어 (format_price_value, format_price_data) |
| `formatters/complex_area.py` | 단지/면적 HTML 포맷 |
| `formatters/analysis.py` | 전세가율/대출분석 HTML 포맷 |
| `formatters/school.py` | 학군 HTML 포맷 |
| `formatters/area_price_detail.py` | 면적별 시세 상세 HTML 포맷 |
| `price_school_formatter.py` | HTML 포맷 barrel re-export (5모듈) |

## 토픽 인덱스 (BE 깊이 자료, 명시 참조 — 자동 로드 안 됨)

| 토픽 파일 | 내용 |
| --- | --- |
| `backend/.claude/details.md` | 실거래가 on-demand + mibunyang 통합 + 공인중개사 검증 워크플로 + 미분양 중복 제거 + **스케줄러 잡 상세 6절**(매물 상세 보강(매물 상세 내용 채우기)·공시가격·응급의료·K-apt 매칭·API 버전 감시·크롤링 모니터(서버 일감 점검) — infra.md 표에서 이동, 세션 411) + **Supabase 다운 런북·재발**(infra.md, 세션 412) + **스케줄러 운영 배경 3절**(재시작 겹침·잡 에러 리스너·monitor freshness — infra.md, 세션 412) + **release 레거시 재기동 절차·사건 박제 표**(release.md, 세션 412) |

## 새 스케줄러 잡 추가 체크리스트 (흩어져 있던 안내를 한곳에 — 세션 412)

| # | 어디에 | 무엇을 | 빠뜨리면 |
| --- | --- | --- | --- |
| 1 | `crawler/scheduler.py` `add_job(id="…", name="…")` | id 는 **문자열 리터럴**, `name` 은 알림 본문에 그대로 찍히므로 쉬운 우리말(라이브는 폴백표보다 이 name 을 우선한다) | 루프로 만든 동적 id 는 정적 가드가 못 본다 / 영문 name 은 텔레그램에 그대로 나간다 |
| 2 | `crawler/job_error_listener.py` `_JOB_LABEL_FALLBACK` | 1번과 같은 우리말 라벨(**스케줄러 id** 키) | `tests/test_scheduler_monitoring_coverage.py` 실패 |
| 3 | `routers/admin/freshness_meta.py` `FRESHNESS_ITEMS` 또는 `MONITORING_EXEMPT`(정당한 사유와 함께) | 신선도 감시 등록 또는 예외 | 같은 테스트 실패 — 잡 이름을 메시지가 알려준다 |
| 4 | `routers/admin/scheduler.py` `SCHEDULER_JOB_META` | 관리자 스케줄러 화면의 행(등록 토글이 둘이면 `env_extra`) | 화면에 행이 없거나 "활성" 표시가 거짓이 된다 |
| 5 | `crawler/plain_words.py` `JOB_WORDS` + FE `frontend/src/lib/crawl-job-labels.ts` | **job_type** 키(스케줄러 id 와 다른 이름 체계) 양쪽 등록 | `tests/test_plain_words.py`·`npm run check:job-labels` 실패 |
| 6 | `crawler/monitor.py` `_STALE_HOURS_BY_TYPE` | 1시간 넘게 도는 잡이면 **실측** 최대 소요의 약 2배(job_type 키) | 모니터가 정상 실행 중인 잡을 cancelled 처리(90일 15건 오탐 전례) |
| 7 | `scripts/gen_restart_schedule_table.py` `_ID_TO_JOB_TYPE`(id ≠ job_type 일 때) → `python scripts/gen_restart_schedule_table.py --write ../.claude/rules/release.md` | 재시작 금지 시각표 재생성 후 함께 커밋 | `tests/test_restart_schedule_table.py` 실패 |
| 8 | `.claude/rules/infra.md` §스케줄러 표 (+ 네이버를 호출하면 §네이버 크롤링 시간 분리) | 설명 행 추가 | ⚠ **가드 없음** — 세션 403 에 만든 3잡(상세 백필 2·채움률 감시)이 세션 412 까지 이 표에서 빠져 있었다 |

## 운영 스크립트 (라이브 판정·문서 생성 — `backend/scripts/`)

| 스크립트 | 용도 |
| --- | --- |
| `scripts/verify_alert_wording.py` | 알림 12창구 + 미지 에러 렌더가 쉬운 우리말인지 **실발송 없이** 검사(exit 0/1). 워크트리에선 `DATABASE_URL="sqlite:///:memory:"` 를 앞에 붙인다 — `.claude/rules/infra.md` §텔레그램 알림 문구 |
| `scripts/gen_restart_schedule_table.py` | `.claude/rules/release.md` §3-0 재시작 금지 시각표를 `scheduler.py`·`monitor.py` 에서 **생성** / `--check`(다르면 diff + exit 1) / `--write`. **잡을 추가·삭제하거나 시각·임계를 바꾸면 `--write ../.claude/rules/release.md` 후 함께 커밋** — `tests/test_restart_schedule_table.py` 가 드리프트를 막는다. 간격 상수는 소스 기본값으로 되돌려 만들므로 `.env` 유무와 무관하게 같은 결과(세션 412 #540) |
| `scripts/run_official_price_now.py` | 공동주택 공시가격 수동 재수집 — 3~7시간이라 세션 독립 실행 필수(`backend/.claude/details.md` §release 레거시 재기동 절차의 schtasks 방식) |

## CI 테스트 인프라

- **엔진**: file-based SQLite + NullPool + WAL + busy_timeout 5초
- **dialect 분기**: `_search_all_types()`는 SQLite에서 ThreadPoolExecutor 대신 순차 실행
  - `_do_upsert()`도 dialect-aware (pg_insert/sqlite_insert 자동 분기)
- **테스트**: 루트 `CLAUDE.md` §테스트 현황 참조 (`python -m pytest --tb=short -q`)
- **conftest.py**: `sys.modules["db.database"]` 교체로 테스트 엔진 주입

## CORS 미들웨어 순서 (중요)

- `RateLimitMiddleware` → `CORSMiddleware` 순서로 등록 (CORS가 마지막 = 가장 먼저 실행)
- 반대로 하면 OPTIONS preflight가 429 반환

## DB 마이그레이션 (실행 완료)

| 버전 | 내용 | 실행일 |
| --- | --- | --- |
| V014 | crawl_jobs.scheduler_job_id | 2026-04-03 |
| V015/V016 | apartments/trades 인덱스 7개 + trigram | 2026-04-07 |
| V017 | agent_verifications 테이블 | — |
| V018 | agent_verifications.license_doc_path | — |
| V019 | infra.childcare_nearest_type/teachers | — |
| V020 | naver_call_counter Supabase 영속화 | 2026-04-22 (세션 54) |
| V021~V023 | 단지/매물 유형명 backfill + 유형별 인덱스 | 2026-05-17 (세션 195) |
| V024 | articles 매물 가치 필드 12개 (에픽 D #9) | 2026-05-17 (세션 195) |
| V025 | articles 매물 상세 4필드 (에픽 D #10) | 2026-05-18 (세션 196) |
| V026 | monitor_alerts 테이블 (크롤링 모니터(서버 일감 점검)) | 2026-05-18 (세션 196) |
| V027 | crawl_jobs scheduler_started 인덱스 (PR #21) | 2026-05-21 (세션 207) |
| V028 | user_profiles.agree_marketing (회원가입 마케팅 동의) | 2026-05-31 (세션 252) |
| V029 | RLS 11 테이블 활성화 (anon 노출 차단) | 2026-05-31 (세션 254) |
| V030 | trades 중복 인덱스 3개 제거 (~57MB, prod 적용완료 세션 270 라이브검증) | 2026-06-02 (세션 260) |
| V031 | 공유 4테이블 anon/authenticated REST 노출 차단 (prod 적용완료, 세션 261 라이브검증) | 2026-06-02 (세션 261) |
| V032 | complex_price_history 제약명 정합 (V001 uq_cph_composite → 코드·prod의 complex_price_history_upsert_key, 멱등 no-op on prod) | 2026-06-07 (세션 280) |
| V033 | agent_verifications.phone 컬럼 추가 (공인중개사 검증 연락처 수집, PR #171) | 2026-06-15 (prod 적용완료, 세션 307 라이브검증: phone 저장 확인) |
| V034 | agent_verifications broker_verified/broker_jurirno/broker_status 3컬럼 (V-WORLD 중개사 대조 결과, 세션 308 PR B) | 2026-06-15 (prod 적용완료, 세션 308 직접 실측: 3컬럼 확인) |
| V035 | user_profiles.paid_until + payments 테이블 (결제 시스템 PR1 — 유료 구독 이용권) | 2026-06-24 (prod 적용완료, 세션 322: 사장님 SQL Editor 실행 → Claude 재검증 paid_until·payments·인덱스 EXISTS) |
| V036 | billing_keys 테이블 (빌링키 자동결제(구독료 자동 결제) — 정기결제 PR1, 방식 B 우리 cron, 세션 327) | 2026-06-27 (prod 적용완료, 세션 329: 사장님 SQL Editor 실행 → information_schema 13컬럼·타입 일치 확인. PR2+ 결제 엔드포인트 INSERT/SELECT 준비됨) |
| V037 | billing_keys.is_default 컬럼 + 부분 유니크 인덱스 (카드 여러 장 보관, 자동결제는 기본 1장 — 정기결제 PR2, 세션 329) | 2026-06-27 (prod 적용완료, 세션 329: 사장님 SQL Editor 실행 → Claude prod 직접 실측 is_default(boolean·default true)·uq_billing_keys_default 인덱스 EXISTS 확인) |
| V038 | articles.updated_at 인덱스 (ix_articles_updated_at DESC — 신선도 monitor timeout 방지, 세션 342) | 2026-07-04 (prod 적용완료, 세션 342: Claude 가 CREATE INDEX CONCURRENTLY autocommit 엔진 실행 5.7초·락0. 라이브 검증 = max(updated_at) 2.7초 Seq Scan → 0.071초 Index Only Scan(38배), EXPLAIN `ix_articles_updated_at` 확인) |
| V039 | articles.created_at 인덱스 (ix_articles_created_at — 신선도 new_rows 헛바퀴감지 timeout 방지, 세션 342) | 2026-07-04 (prod 적용완료, 세션 342: CREATE INDEX CONCURRENTLY 5.9초·락0. 라이브 검증 = new_rows(created_at≥job_start count) 3.8초 Seq Scan → 0.021초 Index Scan(180배), compute_freshness 전체 9.2초 → 0.6초) |
| V040 | presale_schedule_official·applyhome_unit_supply 에 house_type 컬럼 추가 (오피스텔·도시형·생활숙박을 기존 아파트 청약 테이블에 흡수, 이슈 #323) | 2026-08-08 (prod 적용완료, 세션 352: 사장님 SQL Editor 실행 → Claude 재검증 house_type 컬럼 EXISTS) |
| V041 | rental_schedule_official 신규 테이블 (공공지원 민간임대 공고 일정, apartments 로스터와 독립, 이슈 #323) | 2026-08-08 (prod 적용완료, 세션 352: 사장님 SQL Editor 실행 → Claude 재검증 테이블 EXISTS) |
| V042 | rental_unit_supply 신규 테이블 (공공지원 민간임대 평형별 공급정보, rental_schedule_official FK, 이슈 #323) | 2026-08-08 (prod 적용완료, 세션 352: 사장님 SQL Editor 실행 → Claude 재검증 테이블 EXISTS) |
| V043 | presale_schedule_official.house_nm 컬럼 추가 (오피스텔 실제 단지명 저장 — apartments JOIN 제거로 화면에 apartment_id placeholder 만 노출되던 문제 해결, 이슈 #323) | 2026-08-08 (prod 적용완료, 세션 352: 사장님 SQL Editor 실행 → Claude 재검증 house_nm 컬럼 EXISTS) |
| V044 | complex_official_prices 신규 테이블 (공동주택 공시가격 — V-WORLD getApartHousingPriceAttr, 단지×연도×전용면적 중위값. RLS+GRANT REVOKE 이중 빗장, 세션 354) | 2026-08-09 (prod 적용완료, 세션 355: 사장님 SQL Editor 실행 → Claude information_schema 4요소 재검증(컬럼·RLS·정책·anon/authenticated GRANT 0건) 통과) |
| V045 | officetel_presale_schedule·officetel_unit_supply 신규 테이블 (오피스텔·도시형 청약 완전 분리 — presale_schedule_official/applyhome_unit_supply/apartments 에 apartment_id placeholder 로 끼워 넣던 방식 폐기, mibunyang 무결성 전제 보존. rental V041/V042 선례 답습). 2026-08-10 재설계: officetel_unit_supply 는 아파트 청약 틀(general_supply/special_supply/special_by_type, 오피스텔 API가 안 주는 죽은 컬럼) 대신 실제 응답 필드(supply_hshldco/supply_amount/subscrpt_reqst_amount)로 재구성, top_amount 는 시리얼라이저·FE 공유 키라 컬럼만 유지(항상 NULL). officetel_presale_schedule 에 region_name(SUBSCRPT_AREA_CODE_NM) 컬럼 신설 — V045 시점(당시)엔 지역 필터 로직 미구현이었으나 세션382~384(V049)에서 구현 완료(get_officetel_schedules() 참조) | 2026-08-10 (prod 적용완료, 세션 358: 사장님 SQL Editor 실행 → Claude information_schema 4요소 재검증(officetel_presale_schedule·officetel_unit_supply 두 테이블 존재·FK는 officetel_unit_supply→officetel_presale_schedule만이고 apartments 없음·컬럼 전부·RLS 활성화) 통과, PR #352 커밋 9429522 머지완료) |
| V046 | complexes.public_data_attempted_at 컬럼 (국토부 백필 무한재시도 방지 시도 마커 + 90일 쿨다운 — 세션 360 근본수정, 커밋 fd7219f) | prod 적용완료 (적용일은 표 누락으로 미기록 — 세션 367 소급 보강·재검증: 컬럼 timestamptz EXISTS + 31,979개 단지에 시도시각 기록 중 = 라이브 작동 실측) |
| V047 | subway_stations 신규 테이블 (전국 도시철도 역사 1,099행 — 국가철도공단 레일포털 표준데이터, 단지 상세 "가까운 지하철" 표시용. RLS+GRANT REVOKE 이중 빗장 V044 답습, 세션 367) | 2026-08-14 (prod 적용완료, 세션 367: 사장님 SQL Editor 실행 → Claude information_schema 재검증(9컬럼·RLS·정책 Service write·anon/authenticated GRANT 0건) → `python -m scripts.import_subway_stations` 1,099행 적재 → 라이브 GET /subway 3개 단지 실측(강남·동탄·대전 — PR #375 그룹핑 정규화 포함)) |
| V048 | trades·complex_price_history·complexes 3개 테이블에 인덱스 3개 추가 (신선도 monitor 10분 주기 풀스캔 제거 — DB 크래시 2회 원인 가설의 보조 요인, 세션 381) | 2026-08-24 (prod 적용완료·**첫 Claude 직접 적용 사례**(예외적으로 SQL Editor 아님) — `CREATE INDEX CONCURRENTLY` + `SET statement_timeout='10min'`(엔진 기본 8초 우회) 로 1개씩 생성, 매번 `pg_index.indisvalid` 재조회로 확인. 3개 모두 valid, 소요 2.4/2.6/1.7초. `EXPLAIN (ANALYZE, BUFFERS)` 이 Index Only Scan 0.05~0.06ms 로 전환, monitor 주기 slow query 소멸 실측. ⚠ 신규 테스트는 SQLite 환경이라 인덱스 사용 경로 자체는 검증 못함(리팩터링 안전성만 검증), 효과는 위 prod EXPLAIN 으로만 확인됨) |
| V049 | rental_schedule_official.region_name 컬럼 추가 (민간임대 청약 지역 필터 결함 근본수정 — 세션383이 발견한 region_code 숫자코드 vs 한글 시도명 불일치를, 오피스텔 짝꿍 패턴(V045 region_name)과 동일하게 SUBSCRPT_AREA_CODE_NM 을 저장하는 방식으로 해소, 세션 384) | 2026-08-25 (prod 적용완료, 세션 384: 사장님 SQL Editor 실행 → Claude 가 `information_schema.columns` + `pg_indexes` 직접 조회로 region_name(text·nullable) 컬럼과 `idx_rental_schedule_region_name` 인덱스 EXISTS 재검증 → PR #422 머지·backend 재시작(release.md §2 cross-check 4중 통과)·라이브 GET `/api/mb/presale/officetel-rental?region=서울` 로 오피스텔 200건 전량 지역명 일치 실측 확인. 기존 rental 저장분은 region_name NULL 이라 다음 정기 수집(월요일)까지 rental 필터에서만 제외 — 오피스텔은 즉시 정상 동작) |
| V050 | complex_official_prices.collected_at 인덱스 추가 (신선도 monitor 10분 주기 풀스캔 제거 — V048(세션381)이 trades/complex_price_history/complexes 3테이블만 고치고 이 5번째 테이블을 놓쳤던 것을 세션385 개선 스캔이 재발견, 동일 패턴 답습) | 2026-08-25 (prod 적용완료, 세션 385: Claude 가 V048 선례대로 `CREATE INDEX CONCURRENTLY` + `SET statement_timeout='10min'` 직접 실행, `pg_index.indisvalid=True` 확인. `EXPLAIN (ANALYZE, BUFFERS)` 33.5ms Seq Scan → 0.106ms Index Only Scan(약 316배) 실측. freshness.py 의 official_price 축을 max(인덱스 스캔)+count(`_approx_count` 근사) 물리 분리, 신규 characterization test 1건(최댓값 선택 로직까지 검증, 뮤테이션 검증 통과) — PR 진행 예정) |
| V051 | kapt_complex_map·kapt_management_costs 신규 테이블 2개 (K-apt 관리비 연동 — 단지 매칭 결과 + 월별 관리비 공용17/개별5 합산. RLS+GRANT REVOKE 이중 빗장 V044/V047 답습) | 2026-08-27 (prod 적용완료, 세션 388: Claude 가 V048 선례대로 SQLAlchemy raw_connection 으로 직접 실행 — ⚠ 첫 시도는 프록시 객체의 `autocommit` 속성이 드라이버에 안 닿아 통째 롤백(테이블 0개 실측), 명시적 `commit()` 재실행으로 반영. information_schema 4요소 재검증 통과: 테이블 2·RLS 양쪽 True·"Service write" 정책 2·anon/authenticated GRANT 0건·인덱스 5(pkey 2+유니크 1+ix 2)·컬럼 7+10. 신규 테이블 2개라 공유 DB(mibunyang) 영향 0) |
| V052 | kapt_management_costs 테이블 COMMENT 정정 (코멘트 잔존 문구 "개별 V2 5항목" → 개별 V3 — PR #435 의 개별사용료 V2→V3 선제전환을 메타데이터에 반영. pg_description 만 변경, 데이터·스키마·코드 영향 0) | 2026-08-31 (prod 적용완료, 세션 390: Claude 직접 실행 23:33 → obj_description 재조회로 신문구 확인. migration-safety-reviewer 4항목 PASS — mibunyang 참조 0건(collect-maintenance.mjs 는 K-apt API 만 사용). 순수 .sql 문서 + 수동 적용이라 backend 재시작 불요. PR #439, 4ff9533) |

| V053 | infra.childcare_updated_at 컬럼 추가 (어린이집 배치 순환 결함 근본수정 — 선정 쿼리가 ORDER BY 없이 limit(100) 만 걸어 매월 같은 앞쪽 단지만 재갱신, prod 실측 2,938개 중 901개(30.7%)가 5개월간 childcare_count NULL 방치. "오래된 것 우선" 순환 키로 사용. ⚠ 공용 infra.updated_at 은 mibunyang collect-childcare.mjs 가 자기 수집마다 갱신해 순환 키로 쓸 수 없어 전용 컬럼 신설 — air_updated_at·crime_updated_at 선례 답습) | 2026-09-05 (prod 적용완료, 세션 392 직접 실행 — 세션 394 가 `information_schema` 로 컬럼 존재 재확인. ⚠ **적용을 마치고도 이 표를 안 고쳐 오랫동안 "적용 대기"로 방치**됐던 것을 세션 394 가 소급 정정 — V046 "적용일 미기록" 선례의 재발이다. 적용 직후 표 갱신을 같은 PR 에 반드시 동반할 것). nullable 컬럼 추가라 기존 데이터 영향 0, mibunyang 은 이 컬럼을 읽지도 쓰지도 않아 공유 DB 영향 0 |

| V054 | infra.emergency_updated_at 컬럼 추가 (응급의료 배치 순환 결함 근본수정 — 선정 쿼리가 ORDER BY 없이 limit(100) 만 걸어 매월 같은 앞쪽 단지만 재갱신, prod 실측 2,938개 중 496개(16.9%)만 emergency_hospital 채워지고 2,442개(83.1%) 영구 방치. "오래된 것 우선" 순환 키로 사용 + 배치 전량 전환. V053(childcare)과 완전히 동일 계열 결함 — 공용 infra.updated_at 은 mibunyang 이 갱신해 순환 키로 못 써 전용 컬럼 신설, air/crime/childcare 선례 답습) | 2026-09-05 (prod 적용완료, 세션 394: Claude 가 `raw_connection` + **명시 `commit()`** 으로 직접 실행 — V051 의 "프록시 `autocommit` 이 드라이버에 안 닿아 통째 롤백" 함정 답습. `information_schema` 재검증 통과 = `('emergency_updated_at','timestamp without time zone','YES')` + COMMENT 존재 True. 사전 스키마 백업 = `D:/db-backups/naver-estate/schema_20260905_235622.sql` (149KB)). nullable 컬럼 추가라 기존 데이터 영향 0, mibunyang 은 이 컬럼을 읽지도 쓰지도 않아 공유 DB 영향 0 |
| V055 | infra.air_attempted_at 컬럼 추가 (대기질 배치 순환 결함 근본수정 — 선정 쿼리가 ORDER BY 없이 limit(100) 만 걸어 **매일** 같은 앞쪽 단지만 재갱신, prod 실측 2026-09-05: 위경도 보유 2,938단지 중 913개가 한 번도 수집된 적 없고 최근 30일 내 갱신은 977개뿐 — 매일 100개 × 30일 = 3,000슬롯을 쓰고도. V053(childcare)·V054(emergency)와 동일 계열. "오래된 것 우선" 순환 키로 사용, **배치 100 유지**(단지당 API 1콜이라 전량이면 매일 ~3,000콜로 data.go.kr 공유 쿼터 압박 — 응급의료 V054 의 전량 전환과 다른 결정. 한 바퀴 ≈ 30일). ⚠ **기존 air_updated_at 을 순환 키로 못 쓰는 이유** = 그건 측정값이 하나라도 있을 때만 찍히므로(세션 280 — 전부 None 인데 찍으면 신선도 green 인데 화면 빈값) 측정값 없는 단지가 영구 NULL 로 남아 NULLS FIRST 앞자리를 매일 독점 → 순환이 거기서 멈춘다. 그래서 성공/실패 무관하게 찍는 "시도" 마커를 분리 신설(complexes.public_data_attempted_at (V046) 선례와 같은 결). 공용 infra.updated_at 도 mibunyang 이 갱신해 순환 키 부적격) | 2026-09-06 (prod 적용완료, 세션 394: Claude 가 `raw_connection` + **명시 `commit()`** 으로 직접 실행 — V051 의 "프록시 `autocommit` 이 드라이버에 안 닿아 통째 롤백" 함정 답습. `information_schema` 재검증 통과 = `('air_attempted_at','timestamp without time zone','YES')` + COMMENT 존재 True. 사전 스키마 백업 = `D:/db-backups/naver-estate/schema_20260906_003550.sql` (149.8KB). migration-safety-reviewer 4항목 전부 PASS — mibunyang 참조 0건 + 명시 payload upsert 라 NULL 밀림 위험 0 실측 포함). ⚠ 코드보다 **prod 선행 실행 필수**였던 이유 — ORM 매핑 컬럼이라 prod 에 없으면 Infra SELECT 경로 전부 UndefinedColumn 500(환경 수집기 4종 + mb_misc_queries.get_infra). nullable 컬럼 추가라 기존 데이터 영향 0, mibunyang 은 이 컬럼을 읽지도 쓰지도 않아 공유 DB 영향 0 |
| V056 | articles.detail_fail_count 컬럼 추가 (매물 상세 보강(매물 상세 내용 채우기) 무한 재시도 상한, 세션 395 — crawl_article_details 가 상세 API 응답을 정상/dead(NotExistInformation)/transient 3갈래로만 나눠, 네이버가 **매물 단위로** 답하는 dict 오류(code 가 dead 집합 밖)를 transient 로 분류해 30분마다 영원히 재시도했다. 라이브 실측 2026-09-08: 매물 2643869752·2643862927 이 HTTP 200 + `{"error":{"code":"ERROR","message":"알수없는 오류(시스템 오류)"}}` 를 이틀째 일관 반환 → 24시간 로그에 "0/2건 (dead 0건, transient 2건 재시도 대기)" 32회. 처방 = 매물 단위 dict 오류만 카운트해 상한 `_DETAIL_FAIL_CAP`(6 ≈ 30분×6=3시간) 도달 시 선정 쿼리에서 제외. ⚠ **문자열 오류(시스템성 transient: 401/403/429/5xx/네트워크)는 세지 않는다** — 세면 네이버 전체 장애 몇 시간에 살아있는 매물 수백 개가 한꺼번에 상한에 걸려 상세 보강에서 통째로 빠진다. ⚠ is_active 는 불변 = "시도 중단"이지 "매물 비활성화"가 아니다. 수동 복구 = `UPDATE articles SET detail_fail_count=0 WHERE article_no=...`) | **prod 적용완료 2026-09-09 00:20 KST** (세션 395 — 스키마 덤프 후 `lock_timeout 5s` 로 ALTER+COMMENT+NOTIFY 1트랜잭션 0.05초·재시도 0, information_schema 검증 smallint/NOT NULL/default 0/comment 有, 비0 행 0. 머지 **전** 적용해 선행 게이트 준수. ⚠ 게이트 원문: 코드보다 **선행 실행 필수** — ORM(db.models.Article) 매핑 컬럼이라 prod 에 없으면 Article SELECT 경로 전부 UndefinedColumn 500: 매물 조회 API 전체(/api/complexes/{no}/articles·/api/live/*·매물 상세·엑셀 export) + 크롤러 upsert. 배포 순서 = ① 본 파일 prod 실행 → ② 코드 머지·재시작). `NOT NULL DEFAULT 0` 이라 기존 행은 전부 0 = 현행과 동일 동작, PG11+ 상수 DEFAULT 라 대형 테이블 articles 재작성 0. articles 는 mibunyang 과 공용이나 **컬럼 추가만**이고 mibunyang 은 이 컬럼을 읽지도 쓰지도 않아 영향 0 |
| V057 | articles 매물 상세 후보 SELECT 부분 인덱스 `ix_articles_detail_pending` 추가 (30분 배치의 636MB 전량 스캔 제거 — 세션 400) | prod 적용완료 (2026-09-24 세션 417 information_schema/pg_indexes/role_table_grants 실측: 인덱스 `ix_articles_detail_pending` 운영 존재 ✓) |
| V058 | complexes 도장 컬럼 2개 `articles_crawled_at`·`last_viewed_at` 추가 (크롤 선정 키 오염 근본수정 — 세션 402) | prod 적용완료 (2026-09-24 세션 417 information_schema/pg_indexes/role_table_grants 실측: `complexes.articles_crawled_at`·`last_viewed_at` 존재 ✓) |
| V059 | 중복 인덱스 `ix_articles_complex_no` 제거 (24MB 회수 — 세션 406) | prod 적용완료 (2026-09-24 세션 417 information_schema/pg_indexes/role_table_grants 실측: `ix_articles_complex_no` 운영에 없음 = 삭제 적용 ✓) |
| V060 | rental_unit_supply 에 `supply_amount`·`subscrpt_reqst_amount` 추가 (전수 0% 빈 칸 근본수정 — 세션 557) | prod 적용완료 (사장님 SQL Editor 실행, 09-22~24 · 2026-09-24 세션 417 information_schema/pg_indexes/role_table_grants 실측: 두 컬럼 존재 ✓) |
| V061 | field_drift_monitor 쿼리 부분 인덱스 `ix_articles_field_drift_window` 추가 (새벽 statement timeout 반복 — 세션 561) | prod 적용완료 (2026-09-24 세션 417 information_schema/pg_indexes/role_table_grants 실측: 인덱스 `ix_articles_field_drift_window` 존재 ✓). ⚠ 마이그 파일 주석의 "코드 변경 불필요"는 틀렸다 — 코드 조건이 `.is_(True)`(SQL `IS true`)라 인덱스 조건(`= true`)과 모양이 달라 세션 424 까지 **한 번도 안 쓰였다**. 코드 쪽을 `== True` 로 맞춘 뒤에야 탄다(운영 EXPLAIN 비용 75,633 → 9,019, 2026-10-01). 적용 끝난 마이그 파일은 고치지 않는다 |
| V062 | user_profiles — anon·authenticated 의 쓰기 권한(INSERT/UPDATE/DELETE/TRUNCATE) 회수 (자기 등급 올리기 구멍 봉합 — mibunyang 세션566) | prod 적용완료 (mibunyang 세션 09-23 적용 · 2026-09-24 세션 417 information_schema/pg_indexes/role_table_grants 실측: user_profiles 에 anon/authenticated INSERT/UPDATE/DELETE/TRUNCATE 없음 ✓) |
| V063 | storage.objects 정책 "Admins can view license docs" 삭제 (이름과 달리 로그인 사용자 전체에 license-docs 버킷 읽기를 허용 → 클라이언트 읽기 0, backend 서명 URL 만 — 세션 417) | **prod 적용완료 2026-09-24 18:06:03 KST**(세션 417 — raw_connection + 시험 모드 ROLLBACK 1회 통과 뒤 COMMIT, pg_policies 2→1·RLS 켜짐 유지·INSERT 정책 잔존 사후 확인, 사전 스키마 백업 `D:/db-backups/naver-estate/schema_20260924_174934.sql`. mibunyang 기준선 재승인 요청 18:07 발송) |
| V064 | articles 가격변동 조회 부분 인덱스 `ix_articles_price_changed_active` 추가 (`/api/articles/price-changes` 4.2~5.5초 Parallel Seq Scan 149만 행 풀스캔 제거 — 조사반 C 실측, 세션 417) | **prod 적용완료 2026-09-24 19:21 KST**(세션 417 — AUTOCOMMIT 연결로 `CREATE INDEX CONCURRENTLY` 8.5초, 88KB, `indisvalid` True, EXPLAIN ANALYZE = Index Scan 3.6ms, 라이브 `/api/articles/price-changes` 5.8초 → 0.6초 실측. ⚠ 풀 프록시 `raw_connection().autocommit` 은 드라이버에 안 닿아 `ActiveSqlTransaction` — `engine.connect().execution_options(isolation_level='AUTOCOMMIT')` 로 실행) |
| V065 | payments·billing_keys — anon·authenticated 전 권한(SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER) 회수 (RLS 켜짐·정책 0·클라이언트 미사용인데 7권한 보유 = 정책 하나 추가되면 열리는 구조 차단 — 세션 417, mibunyang 인계 09-24) | **prod 적용완료 2026-09-24 19:31:41 KST**(세션 417 — raw_connection + 시험 모드 ROLLBACK 1회 통과 뒤 COMMIT, `role_table_grants` 대조: anon/authenticated 권한 0·service_role/postgres 불변·RLS 켜짐 유지. mibunyang 기준선 재승인 요청 발송) |
| V066 | officetel_presale_schedule 에 `address`(공급위치, 청약홈 HSSPLY_ADRES) 추가 — 분양 탭 오피스텔·민간임대 표 "주소" 열이 오피스텔 620건 전부 "-" 이던 것 해소 (세션 417) | ****prod 적용완료 2026-09-24 20:39:25 KST**(세션 417 — 시험 모드 ROLLBACK 통과 뒤 ADD COLUMN IF NOT EXISTS + COMMENT + NOTIFY pgrst, 620행 무영향, information_schema 로 text/nullable 확인)** — 코드보다 prod 선행 실행 필수(ORM 매핑 컬럼). 메인이 운영 적용 뒤 시각 기입 |
| V067 | 관리자 통계 부분 인덱스 2개 — 상세 채움 count 9.9초 · running 폴링 (커밋 ae1bbcee, #602) | prod 적용 여부는 커밋 ae1bbcee 메시지·세션 기록 참조 (본 세션 밖 — 미확인 시 V067 파일 주석 참조) |
| V068 | `complex_trade_raw` 신규 테이블 — 단지 실거래 **개별 원본**(거래 1건 = 행 1건). 기존 complex_price_history 는 월별 min/max/avg 집계라 원본 가격이 버려져 개별 점 차트를 못 그렸다. complex_no FK 없음 = 매칭 실패 원본도 NULL 보존(공시가격 선례 답습). API `GET /api/complexes/{no}/trade-points`(B2 게이트) + FE PriceHistoryChart Scatter 오버레이. 저장은 `save_trade_raw_rows()` — aptDong 혼합 타입(정수·문자 섞임)은 str 정규화 필수(미정규화 시 insertmanyvalues 첫행 타입 추론으로 DataError, 커밋 b6601c9b) | **prod 적용완료 2026-10-03 09:25 KST**(헤르메스 세션 — 시험 모드 ROLLBACK 통과 뒤 COMMIT, information_schema 로 컬럼 10개·인덱스 `idx_ctr_complex_ym` 확인, RLS·클라이언트 권한 관례가 complex_official_prices·kapt_management_costs 와 동일 실측). 파크리오 소급 실측: 24개월, 개별 점 493건 시드. 적용 스크립트 `/home/ict/work/apply_v068.py` |

- `db/migrations/` 폴더에 `V000__` ~ `V068__` SQL 파일 = 69 버전
- Supabase 에 SQLAlchemy 엔진으로 실행 (V023 = 973,837행 backfill)
- 롤백: 각 마이그레이션 파일의 역방향 SQL 실행
- 최신 = V068 (complex_trade_raw 신규 테이블 — **prod 적용완료 2026-10-03 09:25**, 헤르메스 세션. 시험 ROLLBACK 후 COMMIT, 사후 information_schema 실측. 파크리오 소급 24개월·개별 점 493건 시드). 직전 V067 (관리자 통계 부분 인덱스 2개 — 커밋 ae1bbcee, prod 적용 여부는 해당 세션 기록 참조). 그 직전 V066 (officetel_presale_schedule.address 추가 — **prod 적용완료 2026-09-24 20:39**, 코드보다 prod 선행 실행 필수, 세션 417). 직전 V065 (payments·billing_keys 클라이언트 권한 회수 — **prod 적용완료 2026-09-24 19:31**, 세션 417). 그 직전 V064 (articles 가격변동 부분 인덱스 — **prod 적용완료 2026-09-24 19:21**, 세션 417). 그 직전 V063 (storage 정책 삭제 — **prod 적용완료 2026-09-24**, 세션 417). V057~V062 는 위 표 참조(전부 prod 적용완료). 그 이전 최신 V056 (articles.detail_fail_count — **prod 적용완료 2026-09-09**, 세션 395: 코드보다 선행 실행 필수 게이트를 머지 전 적용으로 준수). 직전 V055 (infra.air_attempted_at — **prod 적용완료 2026-09-06**, 세션 394). 직전 V054(infra.emergency_updated_at)·V053(infra.childcare_updated_at)도 **prod 적용완료**(둘 다 2026-09-05, 세션 394·392) — 다만 V053 표기가 오래 "적용 대기"로 방치돼 있어 세션 394 가 소급 정정했다. V053~V055 는 childcare·emergency·air 세 수집기의 **동일 계열 순환 결함**(ORDER BY 부재)을 차례로 메운 3부작이다. 새 마이그레이션 시 본 표 1행 추가 의무 (`.claude/rules/release.md` 답습 — backend zombie 회피. ⚠ V052 가 이 의무를 놓쳐 세션 392 P2-6 drift 점검에서 소급 보강된 선례 — 마이그레이션 PR 에 본 표 갱신을 반드시 동반할 것)
  - V043 = prod 적용완료·backend 재시작(zombie 해소) 완료 — 세션 352 라이브 검증: `/presale/officetel-rental` 200 정상 응답 확인.
  - V043 = house_nm TEXT nullable 컬럼 추가 — 기존 아파트 청약 행은 NULL 로 두면 되므로 기존 데이터 영향 0. `ADD COLUMN IF NOT EXISTS` 라 멱등·안전. 코드(`db/mb_models.py`)가 이미 이 컬럼에 매핑돼 SELECT 목록에 포함되므로 **prod 선행 적용 필수** — 세션 352 에 적용·재검증 완료.
  - V040~V042 = 이슈 #323(청약홈 오피스텔·도시형·민간임대 편입) 3종 세트 — `CREATE TABLE/ADD COLUMN IF NOT EXISTS` 라 멱등·안전. V040 은 기존 컬럼에 `NOT NULL DEFAULT 'apt'`로 추가해 기존 아파트 데이터에 영향 0. V041/V042 는 신규 독립 테이블이라 공유 DB(mibunyang) 영향 0. 코드(`db/mb_models.py`)는 이미 이 컬럼/테이블에 매핑돼 있으므로 **prod 선행 적용 필수** — 세션 352 에 적용·재검증 완료.
  - V038 = `ix_articles_updated_at` 신규 인덱스 — 코드(freshness.py max/count 분리)는 인덱스 없어도 동작(Seq Scan 느릴 뿐)이라 즉시 500 위험 0. prod 는 CONCURRENTLY 로 락 없이 적용(5.7초). 공유 DB(mibunyang)도 articles upsert 하나 인덱스 유지 오버헤드 미미. `CREATE INDEX IF NOT EXISTS` 라 멱등·안전(마이그 파일은 비-CONCURRENTLY 지만 이미 존재해 no-op).
  - V036 = billing_keys 신규 테이블 — `BillingKey` 가 ORM 매핑되나 PR1 시점엔 INSERT/SELECT 하는 코드가 없어 즉시 500 위험 0. 빌링키 발급/결제 엔드포인트(PR2+) 머지 전 prod 적용 필수. `CREATE TABLE/INDEX IF NOT EXISTS` 라 멱등·안전. 공유 DB(mibunyang) 영향 = 신규 테이블이라 0.
  - V035 = 코드보다 prod 선행 실행 완료 — `paid_until`(user_profiles)·`Payment` 가 ORM 매핑돼 INSERT/SELECT 목록 포함 → 컬럼/테이블 부재 시 get_current_user·결제 엔드포인트 500 이었으나, 세션 322 에 적용·재검증 완료. `ADD COLUMN/CREATE TABLE IF NOT EXISTS` 라 멱등·안전.
  - V034 = 코드보다 prod 선행 실행 완료 — broker_verified 등 3컬럼이 ORM 에 매핑돼 INSERT/SELECT 목록 포함 → 컬럼 부재 시 submit/status/admin 전부 500. `ADD COLUMN IF NOT EXISTS` 라 멱등·안전.
  - ⚠ V033 = 코드보다 **prod 선행 실행 필수** — ORM 에 phone 매핑돼 INSERT/SELECT 컬럼 목록에 포함되므로, 컬럼 부재 시 submit/status/admin 전부 500. `ADD COLUMN IF NOT EXISTS` 라 멱등·안전.
- ⚠️ **마이그레이션 자동 러너 없음** — V030/V031 + `db/maintenance/*.sql` 은 Supabase SQL Editor **수동 실행** 필수 (파일만 있으면 효과 0). 정기 VACUUM 은 `vacuum_maintenance` 스케줄러 잡(매일 03:50)이 자동 처리.
  - V031 = anon/authenticated 의 articles/complexes/trades/complex_price_history SELECT·쓰기 GRANT REVOKE + permissive 정책 DROP. 외부가 anon key 로 매물 전량 긁어 micro RAM 압박(세션 261 실증, PostgREST 부하 1위)한 것 차단 + B2B 모델 유출 봉합. 적용 후 `db/maintenance/verify_anon_shared_locked.sql` 로 라이브 검증. 회귀 가드 = `tests/test_migration_v031_anon_lock.py` (SQLite 라 텍스트 자산 검사).

## 코드 구조 (분리 완료)

- BE service.py → **5 파일** (`service.py` barrel + `service_common`/`service_discover`/`service_price`/`service_public` 4 분할)
- BE formatters/ → **5 파일** (`analysis`/`area_price_detail`/`complex_area`/`price_core`/`school`)
- BE db/ → **14 파일** (`__init__`/`article_queries`/`complex_queries`/`database`/`mb_apartment_queries`/`mb_misc_queries`/`mb_models`/`mb_queries` barrel/`mb_query_helpers`/`models`/`price_queries`/`queries` barrel/`query_helpers`/`stats_queries`)
- BE serializers → **3 파일** (`routers/serializers.py` barrel + `routers/estate_serializers.py` + `routers/mb_serializers.py`)

> **공인중개사 검증 + 미분양 중복 제거**: `backend/.claude/details.md` 참조
