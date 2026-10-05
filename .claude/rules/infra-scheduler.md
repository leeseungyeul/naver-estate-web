---
paths:
  - "backend/crawler/**"
  - "backend/scripts/**"
  - "backend/routers/admin/**"
  - "backend/services/**"
  - "backend/main.py"
  - "backend/tests/**"
  - "backend/.claude/details.md"
  - ".github/workflows/healthcheck.yml"
  - "frontend/src/lib/crawl-job-labels.ts"
---

# 인프라 상세 — 스케줄러 표·알림 창구 현황·관찰성·data.go.kr 호출 표 (infra.md 에서 이동, 세션 430)

> `.claude/rules/infra.md` 에 있던 절을 **글자 그대로** 옮겼다(매 세션 통째로 읽히던 약 40KB 를 필요할 때만 읽게 — 2026-10-05 토큰 다이어트).
> 위 `paths` 파일을 열면 자동으로 읽힌다. 파일을 안 열고도 지켜야 하는 규칙(잡 id ≠ job_type·재시작 묶기·IP 차단·공용 테이블·텔레그램 금지어)은 infra.md 에 남아 있다.
> 링크의 상대경로(`../../backend/.claude/details.md`)는 같은 폴더라 그대로 맞다.

### 적용 현황 — **모듈 9개 / 호출부 12곳 전부 완료** (세션 409 8모듈·11곳 + 세션 421 `service_public` 남은 횟수 부족 알림 1곳)

⚠ **"창구 수"를 셀 때 모듈 수와 호출부 수를 구분하라.** `send_telegram` 을 부르는
**모듈은 9개**지만, 한 모듈이 여러 곳에서 알림을 쏜다(`service_official_price` 는 3곳).
세션 409 가 모듈만 세고 "8창구 전부"라 보고했다가, `service_official_price:451`
표준코드 이관 알림 **한 곳이 안 고쳐진 채** 남아 적대검증에 적발됐다.
→ 판정은 `scripts/verify_alert_wording.py` 로. ⚠ 그 스크립트는 **창구를 손으로 등록**한다(⑧ 만 호출부를 소스에서
   추출해 3곳으로 나뉘어 출력) — 새 창구를 만들면 ⑫처럼 직접 등록해야 렌더 검사가 된다(세션 421 적대검증 정정 — 옛 "소스에서
   추출해 전수 검사" 문장은 과장). 모듈 단위 자동 추출은 `test_plain_words.py` 쪽이다.

`monitor`(#524) · `field_drift_monitor`·`job_error_listener`·`healthcheck.yml`·
`service_official_price`(#526) · `api_version_monitor`·`scheduler_lock`·
`billing_charge`·`routers/payment`(세션 409) · `service_public`(세션 421 — 정부 실거래가 창구 남은 횟수 부족).

잡 라벨(`_JOB_LABEL_FALLBACK`) 9개에 남아 있던 영문(`단지 상세 backfill APT`,
`정기 VACUUM 유지보수`, `K-apt 관리비 수집`, `data.go.kr API 버전 감시` 등)도 함께
우리말로 바꿨다 — 라벨은 알림 본문에 그대로 찍히므로 사전만 고쳐선 부족했다.

**재유입 차단**: `test_plain_words.py` 가 `send_telegram` 호출 모듈을 **소스에서 추출**해
전수 검사한다(`test_no_developer_jargon_in_any_alert_module`·접두어 가드 2종 + 워크플로
YAML). 새 창구가 생겨도 자동으로 검사 대상이 된다 — 손 목록이 아니다.
⚠ 이 가드는 **알림 문구만** 본다. `logger.*`(여러 줄 호출의 이어지는 줄 포함)·환경변수·
API 응답·데이터 사전은 제외한다 — 거짓 경보를 내는 가드는 결국 꺼지기 때문이다.
단 `_JOB_LABEL_FALLBACK` 은 사전이어도 **값이 알림 본문에 찍히므로** 검사 대상이다.

**라이브 확인 (재시작 후 한 줄)**:
```bash
cd backend && PYTHONPATH=. PYTHONUTF8=1 python scripts/verify_alert_wording.py
# 종료 0 = 전부 우리말 / 1 = 어려운 말이 남은 창구를 지목해 출력
# 세션 410 확장: ⓪ 못 알아본 에러 렌더(새 알림 + 해소 알림 — 내부 마침표 검사) ·
#   ⑨ 자동결제 중단 사유 6종(_mark_retry 실호출) · ⑩ 부분환불(이메일 마스킹 검사) · ⑪ 관리자 화면 `explain_stored_error`
#   (스윕 마커·psycopg2·붙는 형태 3입력, 세션 411 후속) · ⑫ 정부 실거래가 창구 남은 횟수 부족(세션 421 — 숫자 셋 검사)
#   포함 = "12창구 + 미지 에러 렌더".
#   텔레그램·이메일·log_action 은 전부 patch — 실발송 0. 워크트리(.env 없음)에선 DATABASE_URL="sqlite:///:memory:" 를 앞에 붙인다
```

⚠ **잡 이름은 두 곳에 있고 라이브는 스케줄러 쪽을 쓴다** (세션 409 HIGH-1):
`job_error_listener._job_label()` 은 `scheduler.get_job(id).name` 을 **우선**하고
`_JOB_LABEL_FALLBACK` 은 그게 실패할 때만 본다. 라이브는 scheduler 가 주입되므로
**폴백 표만 고치면 알림에 안 반영된다** — `crawler/scheduler.py` 의 `add_job(name=...)`
을 함께 고쳐야 한다. 두 곳의 값은 `plain_words.JOB_WORDS` 와 같은 표현으로 맞춘다.

## 잡 이름 대조표 (옛 → 새, 세션 419 #585)

관리자 화면·텔레그램 알림·달력의 잡 이름을 한 벌로 맞추면서 옛 표시 이름(관리자 스케줄러 표)이 바뀌었다.
**정본 = `backend/crawler/scheduler.py` 의 `add_job(name=…)`** 이고, 그 이름은 `crawler/plain_words.py JOB_WORDS[job_type]` 로 시작한다
(crawl_jobs 를 안 남기는 `crawler_monitor` 만 예외 — 가드 = `tests/test_plain_words.py test_every_registered_job_name_starts_with_job_words`). 옛 이름으로 문서를 찾다 여기 왔다면 오른쪽이 지금 화면에 보이는 이름이다.
아래 표·다른 문서에서는 옛 이름을 "옛 이름(새 이름)" 으로 함께 적어 두었다.

| 잡 id | 옛 이름 | 새 이름 |
|---|---|---|
| `discover_regions` | 전국 단지 발견 | 새 단지 찾기 |
| `crawl_articles` | 매물 수집 배치 | 단지 매물 가져오기 |
| `crawl_details` | 매물 상세 보강 | 매물 상세 내용 채우기 |
| `backfill_detail_dawn` | 상세 백필 00:20(키 드리프트 대응) | 빠진 정보 뒤늦게 채우기 00:20 |
| `backfill_detail_noon` | 상세 백필 12:20(키 드리프트 대응) | 빠진 정보 뒤늦게 채우기 12:20 |
| `collect_prices` | 시세 이력 수집 | 단지 시세 기록 모으기 |
| `popular_1030` | 인기 단지 크롤링 10:45 | 자주 보는 단지 미리 갱신 10:45 |
| `popular_1430` | 인기 단지 크롤링 14:45 | 자주 보는 단지 미리 갱신 14:45 |
| `popular_1900` | 인기 단지 크롤링 19:15 | 자주 보는 단지 미리 갱신 19:15 |
| `collect_public_trades` | 공공데이터 실거래가 | 정부 실거래가 받기 |
| `collect_officetel_presale` | 청약홈 오피스텔 수집 | 오피스텔 청약 공고 받기 |
| `collect_rental_presale` | 청약홈 민간임대 수집 | 민간임대 청약 공고 받기 |
| `official_price` | 공동주택 공시가격 수집 | 정부 공시가격 받기 |
| `backfill_price` | 시세 이력 소급 수집 | 옛 시세 채워 넣기 |
| `collect_air_quality` | 에어코리아 대기질 | 동네 공기질 받기 |
| `collect_emergency` | 응급의료기관 | 응급실 위치 받기 |
| `collect_childcare` | 어린이집 | 어린이집 정보 받기 |
| `collect_crime_stats` | 범죄통계 | 동네 범죄 통계 받기 |
| `complex_detail_APT` | 단지 상세 backfill APT | 아파트 단지 정보 채우기 |
| `complex_detail_OPST` | 단지 상세 backfill OPST | 오피스텔 단지 정보 채우기 |
| `complex_detail_JGC` | 단지 상세 backfill JGC | 재건축 단지 정보 채우기 |
| `complex_detail_ABYG` | 단지 상세 backfill ABYG | 아파트 분양권 단지 정보 채우기 |
| `complex_detail_OBYG` | 단지 상세 backfill OBYG | 오피스텔 분양권 단지 정보 채우기 |
| `collect_metrics` | 단지 가치지표 수집 | 단지 가치 점수 계산 |
| `billing_charge` | 빌링키 자동결제 | 구독료 자동 결제 |
| `crawler_monitor` | 크롤링 모니터 | 서버 일감 점검 |
| `field_drift_monitor` | 상세 필드 채움률 드리프트 감시 | 정보 안 채워지면 알림 |
| `vacuum_maintenance` | 정기 VACUUM 유지보수 | 자료 보관함 정리 |
| `api_version_probe` | data.go.kr API 버전 감시 | 정부 자료 창구 살아있나 확인 |
| `kapt_match` | K-apt 단지 매칭 | 관리비 단지 연결하기 |
| `kapt_costs` | K-apt 관리비 수집 | 단지 관리비 받기 06:20 (세션 422 에 시각 붙임 — 낮 회차와 구분) |
| `kapt_costs_noon` | — (세션 422 신설) | 단지 관리비 받기 12:40 |
| `kapt_costs_evening` | — (세션 426 신설) | 단지 관리비 받기 21:00 |

## 스케줄러 (APScheduler)

> **재시작 판정용 전수 시각표는 `release.md` §3-0 의 생성 표**다(`backend/scripts/gen_restart_schedule_table.py` 가 코드에서 생성 — 등록 잡 32행·⏰ 장시간 잡).
> 아래 표는 **설명 + 라이브 실값** 기준이라 interval 이 그 표와 다를 수 있다(크롤링 모니터(서버 일감 점검) = 라이브 `.env` 10분, 코드 기본값·생성 표 30분).
> 잡을 추가·삭제하거나 시각을 바꾸면 이 표의 행을 고치고 `--write` 로 생성 표도 갱신한다(가드 = `tests/test_restart_schedule_table.py`).

| 작업 | 주기 | 설명 |
|------|------|------|
| 새 단지 찾기 (전국 단지 발견) | 일요일 3시 | 네이버 키워드 검색으로 신규 단지 수집 |
| 단지 매물 가져오기 (매물 수집 배치) | **매일 01:00 / 13:00** cron (±45분 jitter) | 활성 lane + 발굴 lane 두 몫으로 단지 선정해 매물 목록 크롤링 (배치 기본 **150**, 세션 402 PR #506). ⚠ 옛 "12시간 interval" 은 APScheduler `IntervalTrigger` 가 `start_date = now + interval` 이라 **재시작마다 다음 실행이 12h 밀렸다** — 최근 14일 중 9일이 하루 1회만 돌았다(crawl_jobs 실측). cron 은 벽시계 기준이라 재시작 무관. **선정 키**(`db/complex_queries.py get_complexes_for_article_crawl`, 세션 402 PR #507): 활성 lane 80% = 활성 매물 보유 단지를 `complexes.articles_crawled_at` 오래된 순(NULL 우선), 발굴 lane 20% = 활성 0 + `articles_crawled_at IS NULL` 단지. 한쪽이 모자라면 남는 몫을 다른 lane 이 흡수. 옛 1순위 `has_article.asc()`(매물 0건 우선)는 2026-04-13 엔 정당했으나 그 풀이 53,581 로 불어나 활성 10,567 단지의 76%가 30일+ 미방문이 됐다. **호출 총량 불변은 단지 수 기준**이지 콜 수 기준이 아니다(매물 보유 단지는 페이지네이션) — `record_call("crawl_articles_batch")` 로 1주 관찰. ⚠ 라이브 `.env` 에 `CRAWL_BATCH_SIZE` 가 있으면 코드 기본값 150 을 덮는다 |
| 매물 상세 내용 채우기 (매물 상세 보강) | 30분 interval (±15분 jitter) | 매물 상세 크롤링(배치 500). 매물오류 상한·부분 인덱스·순회마다 commit (상세: [§잡 상세 — 매물 상세 보강](../../backend/.claude/details.md#잡-상세--매물-상세-보강)) |
| 빠진 정보 뒤늦게 채우기 00:20·12:20 (상세 백필 새벽·낮) | 매일 00:20 / 12:20 | 스케줄러 id `backfill_detail_dawn`(배치 1500·약 38분)·`backfill_detail_noon`(배치 4000·실측 113~134분), job_type 은 둘 다 `article_detail_backfill`. 네이버가 상세 응답 키를 바꿔 빈 채 굴러간 필드(난방·사용승인일·지번주소·총층수)를 상세 API 로 사후 보강한다. 소요 = 배치 × 1.5초(throttle)라 다음 네이버 잡(01:00 매물 수집·14:45 인기 단지)과 안 겹치게 회차별 배치를 달리했다 — **낮 회차가 145분을 넘기면 14:45 와 겹친다**(2026-09-18 실측 133.9분 — 원인은 네이버 차단이 아니라 30분 주기 상세 보강과의 겹침, 세션 414). 스윕 임계 4h(⏰ 재시작 금지 구간). 토글 `BACKFILL_DETAIL_ENABLED`(코드 기본 false — 2026-09-14 라이브 `.env` 에서 ON), 배치 `BACKFILL_DETAIL_BATCH_SIZE`(덮으면 두 회차 모두 그 값) |
| 단지 시세 기록 모으기 (시세 이력 수집) | 수요일 4시 | 단지별 시세(매매/전세) 주간 수집 |
| 옛 시세 채워 넣기 (시세 이력 소급 수집) | 매일 03:30 | complex_price_history 6행 미만 단지 세대수 상위순 국토교통부 backfill (PUBLIC_DATA_ENABLED 토글, 네이버 0 — 세션 288 표 누락 정정) |
| 단지 가치 점수 계산 (단지 가치지표 수집) | 매일 04:30 | complex_price_history 집계 → complexes 가치 3필드. **매일 전 단지 다시 계산**(최근 6개월 매매 평균가가 있는 모든 단지 — 옛 코드는 빈 단지만 한 번 채우고 끝이라 값이 낡았다) · **최근 6개월 매매가 없는 단지는 마지막 값 유지**(10-03 사장님 결정 — 3월 일괄 수집분만 있는 단지 약 8천 곳이 비지 않게) · 값이 바뀐 단지만 UPDATE(updated_at 도 그때만 — 쓰기량을 줄이려고, complexes 는 미분양도 읽는 공용 표) · 잡 기록 처리 수 = 확인한 단지 수(값이 그대로인 날도 헛바퀴 경보 없음). 최근 6개월 A1·B1 줄을 한 번에 읽어 계산(10-03 실측 운영 약 20만 줄·0.5초). 안전장치: 최근 6개월 매매 평균가를 하나도 못 읽으면 아무것도 안 쓰고 failed. `COMPLEX_METRIC_RECOMPUTE_LIMIT` **0 = 전량**(코드 기본, 기동 로그 "(전량)" — 세션 428 새 이름. 운영 .env 에 남은 옛 `COMPLEX_METRIC_BATCH_SIZE` 줄은 안 읽어 전량이 덮이지 않는다, 남아 있으면 기동 로그에 안내 한 줄), 양수면 **매일 같은 세대수 상위 N곳만** 계산(순환 없음 — 나머지는 옛 값 유지, 회차 시작 때 경고 로그). 네이버 API 0 (세션 428) |
| 정보 안 채워지면 알림 (상세 필드 채움률 감시) | 매일 04:40 | 스케줄러 id `field_drift_monitor`(잡 이름 "정보 안 채워지면 알림"). 최근 48시간에 상세를 받은 활성 매물의 **필드별 채움률**을 DB 집계만으로 점검(네이버 0)해 임계 미달이면 텔레그램. 2026-09-13 실사고(네이버가 상세 응답 키를 바꿔 `heating_type` 등 4필드가 6개월 넘게 0% — HTTP 200 이라 에러·경보 0)의 조기 경보. 04:30 가치지표·04:50 자동결제 사이 빈 슬롯. 토글 `FIELD_DRIFT_MONITOR_ENABLED`(코드 기본 false — 라이브 ON). 집계 조건을 V061 인덱스 술어와 모양 맞춤(`IS true`→`= true`, 주원인) + 이 잡의 집계 트랜잭션은 문장마다 30초(안전망 — 집계 뒤 알림 조회·잡 완료 기록 포함, 다른 연결·다른 잡은 8초. 세션 424 — 48h 창 5.5배 성장도 겹침) |
| 구독료 자동 결제 (빌링키 자동결제) | 매일 04:50 | billing_keys 의 next_charge_at 도래분(status='active' AND is_default) PortOne 빌링키 결제 → paid_until 연장 + next_charge_at 갱신. 3일 연속 실패 시 status='failed' 중단+알림. PortOne 결제라 네이버 0, 토글 BILLING_AUTO_CHARGE_ENABLED (정기결제 PR3, 세션 330). ⚠ **`PAYMENT_ENABLED`(코드 기본값 false, 세션 400 무료 전환) 가 꺼짐이면 이 잡이 아예 등록되지 않는다** — 관리자 스케줄러 화면에는 **행이 남고 "비활성"으로 표시**된다(그 화면은 등록된 잡이 아니라 `SCHEDULER_JOB_META` 사전을 순회하므로 행 자체는 안 사라진다 — 활성 판정은 META 의 `env_extra` 로 두 토글의 AND 를 본다. 이 장치가 없던 초안은 꺼진 기간에도 "활성 · 매일 04:50"으로 거짓 표시했다 — 세션 400 적대검증 HIGH). 같은 토글로 결제 API 7종(`/api/payment/*`·`/api/payment/billing/*`)도 403 이 된다. 즉 `BILLING_AUTO_CHARGE_ENABLED=true` 만 보고 "자동결제가 돈다"고 판정하면 오판 — 두 토글의 **AND** 다(`crawler/scheduler.py` 등록 조건). 켜려면 `.env` 에 `PAYMENT_ENABLED=true` 추가 + 재시작. 게이트 = `config/payment_flags.py` |
| 자료 보관함 정리 (정기 VACUUM 유지보수) | 매일 03:50 | articles/trades VACUUM (ANALYZE) — visibility map 재악화 차단. Supabase autovacuum 미동작 대비 안전망. **+ rate_limit_counters 만료 행 정리**(`quota_db.purge_expired_counters`, `expires_at < now()` 만 삭제·NULL 미대상. 날짜별 키가 쌓이는데 청소 주체가 없어 2026-04-15 이후 만료분 ~135행 잔존하던 것 — best-effort 라 실패해도 VACUUM 결과·잡 상태 영향 0, dialect 무관이라 VACUUM 의 PostgreSQL early-return **앞**에서 실행). **+ 상세 상한(detail_fail_count≥6) 매물 카운터를 5 로 되돌려 하루 1회 재시도 자격 부여** — 영구 방치 사각 차단, 세션 395(상한 매물이 네이버 쪽 오류가 풀려도 자동 복귀할 경로가 없어 수동 SQL 이 유일 탈출구이던 것. 되돌린 매물은 다음 배치에서 딱 1회 재시도되고 또 매물오류면 즉시 재제외 = 매물당 하루 1콜 유계. 쿼터 정리와 동일한 best-effort·early-return 앞). DB 전용(네이버 0), 토글 VACUUM_MAINTENANCE_ENABLED (세션 260) |
| 자주 보는 단지 미리 갱신 (인기 단지 크롤링) | 매일 10:45/14:45/19:15 | 자주 조회되는 단지 선제적 크롤링, 개별 try/except (기본 배치 50) **부모 잡이 자식 실패를 집계**(세션 396 PR #487) — `crawl_complex_articles` 가 성공/실패 bool 을 돌려주고 부모가 "N/50개 단지 실패" 를 error_message 에 남긴다(옛 코드는 자식이 예외를 흡수해 항상 50/50 completed 로 보였다). **선정 키 = `complexes.last_viewed_at` 최근 7일**(사용자가 `start-crawl` 을 호출한 시각, V058·세션 402 PR #507), 부족분은 활성 lane(`articles_crawled_at` 오래된 순)으로 채운다. 옛 키 `last_crawled_at DESC` 는 배치·자매 일괄 스탬프에 오염돼 7일 1,050회 중 **846회(81%)** 가 직전 24h 내 배치가 이미 긁은 단지 재방문이었다. 세대수 상위 폴백은 제거(빈 DB 외 도달 불가). |
| 정부 실거래가 받기 (공공데이터 수집) | 토요일 5시 | 국토교통부 실거래가 |
| 오피스텔 청약 공고 받기 (청약홈 오피스텔 수집) | 월요일 05:00 | 오피스텔/도시형 청약 공고+평형(getUrbtyOfctlLttotPblancDetail/Mdl), 독립 테이블 officetel_presale_schedule·officetel_unit_supply 저장 (V045 재설계 — apartments 무관, 옛 "로스터 매칭분만 upsert" 방식 폐기. 네이버 0, PUBLIC_DATA_ENABLED 공유 — 이슈 #323) |
| 민간임대 청약 공고 받기 (청약홈 민간임대 수집) | 월요일 05:30 | 공공지원 민간임대 공고+평형(getPblPvtRentLttotPblancDetail/Mdl), 신규 독립 테이블 (네이버 0, PUBLIC_DATA_ENABLED 공유 — 이슈 #323) |
| 정부 공시가격 받기 (공동주택 공시가격 수집) | 매월 15일 06:30 | V-WORLD 공시가격 → 단지 매칭(세대수 게이트). 3~7시간 소요, 네이버 0 (상세: [§잡 상세 — 공동주택 공시가격 수집](../../backend/.claude/details.md#잡-상세--공동주택-공시가격-수집)) |
| 동네 공기질 받기 (대기질 수집) | 매일 2시 | 에어코리아 API. **배치 100 은 `infra.air_attempted_at` 오래된 순(NULL 최우선) 순환**(V055·PR #459, 세션 394 — 옛 ORDER BY 부재로 매일 같은 앞쪽 100개만 재갱신되던 결함 수정. prod 실측 2026-09-05: 2,938단지 중 913개가 한 번도 수집된 적 없고 최근 30일 갱신은 977개뿐 — 매일 100×30일=3,000슬롯을 쓰고도). **전 단지 한 바퀴 ≈ 30일**(2,938 ÷ 100). ⚠ **배치 유지·전량 전환 금지** — 단지마다 `get_nearby_station` 1콜이 나가 전량이면 매일 ~3,000콜로 data.go.kr 공유 쿼터(일 10,000, mibunyang 과 공유)를 압박한다(응급의료 V054 는 전국 목록 1회 + 로컬 계산뿐이라 전량이 공짜였던 것과 다름). ⚠ **순환 키가 `air_updated_at` 이 아니라 신설 `air_attempted_at`("시도" 시각)인 이유**: `air_updated_at` 은 측정값(pm10/pm25/o3)이 하나라도 있을 때만 찍힌다(세션 280 — 전부 None 인데 찍으면 신선도 green 인데 화면은 빈값). 그 의미론은 보존해야 하는데, 그걸 순환 키로 쓰면 측정값이 안 나오는 단지가 영원히 NULL 로 남아 NULLS FIRST 앞자리를 매일 독점 → 순환이 그 자리에서 멈춘다. 그래서 측정소 미발견·측정값 전무여도 찍는 시도 마커를 분리 신설(`complexes.public_data_attempted_at`(V046) 선례와 같은 결). 매월 10일 토요일 건너뛰기 삭제(세션 422) — 그날도 평소처럼 최대 약 200콜(에어코리아 창구 2개: 단지마다 측정소 조회 1콜 + 측정소마다 실시간 측정 1콜, `env_air.py` 런 안 캐시) |
| 응급실 위치 받기 (응급의료 수집) | 매월 첫째 월 3시 | NEMC 응급의료기관 → infra.emergency_*. 전량 갱신(회차당 목록 6콜 + 병상 1콜 = 7콜). **병상 = 실시간 op `hvs01`(응급실 일반병상), 등급 = 목록 `dutyEmclsName`, 모르면 None** — 세션 417 전까지는 목록 op 에 없는 필드를 읽어 병상 0·등급 빈값만 저장됐다 (상세: [§잡 상세 — 응급의료 수집](../../backend/.claude/details.md#잡-상세--응급의료-수집)) |
| 어린이집 정보 받기 (어린이집 수집) | 매월 첫째 목 1시 | CPMS cpmsapi030 API (01:00 고정 — 아래 §CPMS 키 공유 참조, 04:30 이후 금지). **배치 = 전량**(`CHILDCARE_BATCH_SIZE=0`, 사장님 결정 2026-09-05 / 세션 393): 위경도 보유 2,938단지를 매월 전부 갱신한다. 전량이 가능한 근거 = 이 수집기는 **시군구당 1콜 + 런 내 캐시 재사용**이라 호출 상한 = 단지가 걸친 (region,gu) 조합 수 = **248콜**(2026-09-05 prod 실측)로, CPMS 일 1,000콜 공유 쿼터 안에서 여유. 옛 배치 100 은 한 바퀴 ≈ 30개월이라 실익이 없었다. `infra.childcare_updated_at` 오래된 순(NULL 최우선) 순환 키(V053·PR #451, 세션 392)는 **안전망으로 유지** — 부분 배치로 되돌릴 때의 폴백 + 전량 실행이 도중에 끊겨도 다음 회차가 미수집분부터 이어받게 한다(500단지마다 중간 저장). 첫 실전 = 2026-10-01 목, 이때 NULL 방치 901단지가 일괄 해소될 전망 |
| 동네 범죄 통계 받기 (범죄통계 수집) | 분기별 첫째 일 4시 | 경찰청 odcloud API (CSV 폴백) |
| 유형별 단지 정보 채우기 (단지 상세 backfill) | APT/OPST 4시간 interval 매일 / JGC·ABYG·OBYG 주1회 7시 | 매물유형별 독립 job, detail_crawled_at NULL 단지 보강 (APT/OPST 배치 1000 가속 — PR #19 답습, 소수 유형 배치 1000 cron 유지. 2026-05-27 PR 6a 답습 6h→4h 33% 가속) |
| 관리비 단지 연결하기 (K-apt 단지 매칭) | 매월 21일 14:50 (세션 426 — 옛 06:10. 1.5초 간격이면 약 6.1시간이라 그날 관리비 두 회차가 끝난 뒤 혼자 돈다) | 국토부 K-apt 전국 목록 ↔ 우리 단지 4중 게이트 매칭. **단지 기본정보 받기가 실패한 단지는 기존 연결·관리비를 그대로 둔다**(덮어쓰기·회차 끝 정리 모두 제외 — 세션 426). 실패가 연결보다 많으면 그 회차는 failed·정리 건너뜀. 네이버 0 (상세: [§잡 상세 — K-apt 단지 매칭](../../backend/.claude/details.md#잡-상세--k-apt-단지-매칭)) |
| 단지 관리비 받기 (K-apt 관리비 수집) | 매일 06:20 · 12:40 · 21:00(12:40 = 세션 422 — 아침 포털 04 장애 때 같은 날 받아주기 · 21:00 = 세션 426 — 1.5초 간격에서 한 달 수요 맞추기, 셋 다 되는 날 K-apt 약 14,400콜) | **세 회차**: 스케줄러 id `kapt_costs`(06:20)·`kapt_costs_noon`(12:40)·`kapt_costs_evening`(21:00), 같은 함수·같은 배치, job_type 은 모두 `kapt_costs`(스윕 임계 3h 공유). 2026-09-25 부터 K-apt 창구가 분 단위 간헐 오류(코드 04)를 내 06:20 회차가 사흘 연속 실패해 낮 회차를 더했다. 아침 06시대가 가장 심하고 오후(09-25 14:47~17:21·09-26 14:28)에도 실패한 날이 있다 — 낮 회차는 두 번째 기회일 뿐 완치가 아니다. 이미 running 인 회차가 있으면 새 회차는 잡 행 없이 건너뛴다(`already_running`). 신선도 카드 "단지 관리비 받기"·monitor 의 "자료 오래됨" 경보는 세 id 를 함께 센다(`routers/admin/freshness.py _CARD_SCHEDULER_IDS`). **매월 최신 공개월로 갱신**(2026-09-19 사장님 결정 — 옛 "단지별 약 3개월에 1회"). 대상 = kapt_complex_map 중 **보유한 가장 최신 달보다 새 달이 남은 단지**(보유월 이하는 절대 재조회 안 함 → 옛 무한 재조회 가드를 더 강한 형태로 유지), 순서는 **관리비 행이 아예 없는 단지 먼저 → matched_at 오래된 순**. **미공개 단지는 슬롯을 소모하지 않고**(3콜뿐) 수집·실패만 batch_size(500)를 채우며, 미공개 **스캔 상한 2,000** 에서 루프 중단. 훑은 단지가 전량 미공개면 저장행 표본 3건에 첫 op 1콜씩 찔러 **카나리**로 API 생사를 확인한다(살아있으면 정상 완료 — 월 전환일 거짓 경보 차단, 표본 0건·전부 빔이면 failed). 달마다 행이 쌓이고 조회 API 는 최신월 1건. 500개 × 22항목(공용 V3 17 + 개별 V3 5, 관리비 두 서비스도 **운영계정(10만/일) 전환 완료** → `KAPT_COST_BATCH_SIZE` 기본 500 으로 운영 중(2026-08-31 첫 정기 실행 실측: 하루 kapt 32,035콜, 실패 0·쿼터 에러 0). 개발계정 시절엔 한도가 서비스당 5,000/일 오퍼레이션 합산이라(공개 페이지 실측 2026-08-29 — 옛 "op당 1,000" 추정은 틀림) 배치 500 이면 공용만 8,500콜로 초과해 250 으로 낮춰 돌렸었고, 그 .env 오버라이드는 제거됨) 합산 → kapt_management_costs 월별 upsert(**항목별 금액 = 세부 칸 합** — 세션 417 정정, 옛 파서는 첫 칸만 저장해 인건비·제세공과금 등 다칸 op 5종이 과소. 22항목 표: [§잡 상세 — K-apt 관리비 수집](../../backend/.claude/details.md#잡-상세--k-apt-관리비-수집-항목별-금액--세부-칸-합-세션-417))(공개 지연 3개월 실측. 폴백월 무한 재조회 차단은 옛 "후보월 중 아무 달이나 보유 시 제외" 에서 **보유월 이하 재조회 금지**로 승계 — 더 강한 형태). 실측 87~107분(2026-09, 조기 탈출 전 — 미공개 단지가 66콜씩 먹던 시기. 조기 탈출 후 기대 33~40분). **매월 갱신 전환 후 평시 기대 ≈63분**(500×22 + 상시 미공개 ~516×3 ≈ 12,500콜), **최악 ≈90분**(500×24 + 2,000×3 = 18,000콜 × 0.303초 실측 throttle — 스캔 상한이 이 최악을 묶는다)이라 1h 경계를 넘는다 → _STALE_HOURS_BY_TYPE 3h. 단지 상세 GET /api/complexes/{no}/kapt(12h 캐시)·기본정보 "월 관리비(세대당)·복도유형" 표시 원천. 배치 500 기준 회차당 11,000콜(세션 422 부터 두 회차 모두 되는 날엔 하루 ≈25,000 — ⚠ 둘 다 0.3초 간격 시절 값. 1.5초 간격인 지금은 시간 예산 120분에 회차당 약 4,800콜, 세 회차 다 되는 날 약 14,400콜 — 10-01 12:40 회차 실측 4,818) — 전역 쿼터가 아닌 kapt 버킷(6만 상한) 소모. **호출 실패 단지는 저장 안 하고(반쪽 총액 방지) 다음 회차 재시도, 한도 초과(22)는 배치 조기 중단 + 잡 failed.** **미공개 단지는 첫 op 에서 끊어 66콜→3콜**(근거 = 저장 7,757행 전수 실측, 세션 414). ⚠ **이 조기 탈출은 세션 417 전까지 실전에서 한 번도 서지 않았다** — K-apt 의 실제 미공개 응답은 빈 body 가 아니라 **키는 다 있고 값이 전부 null 인 item** 이라(2026-09-24 원문 실측) 옛 판정 `if not item` 을 통과해, 미공개 단지가 공용 17콜 × 3개월 = **51콜**씩 태웠다(09-24 회차 실측 26,351콜·약 132분 = 수집 500×22 + 미공개 299×51). 세션 417 에 `kapt_api._is_blank_item` 으로 정정 → 기대 **수집 500·미공개 ≈300 이면 ≈11,900콜·55~65분**(위 "33~40분"은 이 결함 때문에 한 번도 실현되지 않은 옛 예측). 판정은 회차 로그 한 줄 `[kapt_costs] 호출 집계: 미공개 N단지가 M콜 사용(단지당 평균 X콜), 이번 회차 관리비 호출 총 T콜` — 평균이 3 이하면 정상, 17 근처면 조기 탈출이 또 안 선 것. 네이버 0, 토글 KAPT_ENABLED 공유. 제공기관 오류 봉투(코드 04 등)는 사유째 기록(일시성 01·02·04·05·99 는 3/10/30초 재시도 뒤에만 실패), 연속 실패는 카나리·대기(30/60/120초) 뒤에만 중단 — 세션 417 후속, 09-25 실사고. **수집 0 인 채로 "카나리 살아있음 — 계속" 은 2회까지**(`_ALIVE_CONTINUE_CAP_WHILE_EMPTY`), 3번째면 `partial_outage` 로 마감 — 09-25 14:47~17:21 수동 회차가 이 상한 없이 수집 0·실패 75·미공개 162·1,276콜(재시도 585 포함)로 예산을 다 태웠다. 수집 ≥1 이어도 실패 > 수집이면 failed(`mostly_failed` — 한 단지 성공으로 monitor 가 "복구" 를 알리지 않게), 이미 running 인 회차가 있으면 새 잡 없이 반환. 회차 시간 예산 120분(단지 사이에서만 검사 — 최악 120 + 마지막 단지 17.6분 + 카나리 15분 ≈ 152분 < 3h, 옛 150분은 09-25 실측 154.6분). 카나리 표본 4건은 논리 호출이고 재시도 포함 최대 16콜·표본당 43초. 재시도·실패 로그와 잡 기록에 `kaptCode=… searchDate=…` 가 붙는다. `kapt_match` 의 **기본정보는 재시도하지 않는다**(실패 1건 = 1콜 — 장애일에 14,747건 × 4콜·대기 176시간이 되는 것을 막음). 목록(약 22페이지)은 재시도 유지 — 한 페이지가 끊기면 일부 목록으로 매칭돼 멀쩡한 매핑·관리비 행이 지워질 수 있다 (상세: [§잡 상세 — K-apt 관리비 수집](../../backend/.claude/details.md#잡-상세--k-apt-관리비-수집-항목별-금액--세부-칸-합-세션-417)). ⚠ 세션 425(2026-10-01): K-apt 창구에 속도 제한이 있다 — 0.3초 간격이면 33번째 콜부터 약 10분간 K-apt 전체가 코드 04(09-25~10-01 15회 연속 실패의 원인, 서버 밖 재현). 그래서 K-apt 호출만 1.5초 간격(`kapt_api._KAPT_MIN_INTERVAL_SEC`). 회차 시간 예산 120분이면 약 4,800콜 ≈ 200단지 안팎 — 위의 '500단지·63분' 류 수치는 0.3초 시절 값이다. K-apt 를 부르는 스크립트(`recollect_kapt_5ops.py` 등)를 정기 회차와 **동시에** 돌리면 합쳐서 한계를 넘는다 — 겹치지 않게. `kapt_match`(매월 21일)의 기본정보 약 1.47만 건(09-21 실측 14,747)도 1.5초 간격이라 혼자 돌아도 약 6.1시간이다 — 06:10 에 돌면 같은 날 06:20·12:40 관리비 회차와 간격을 나눠 써 약 7.8시간(스윕 임계 8h 근처)이 되므로 **14:50 으로 옮겼다**(세션 426, 사장님 결정 2026-10-01 — 12:40 회차가 늦게 끝나는 날은 매칭이 그 회차를 최대 45분 기다렸다 시작한다(세션 427) — 15:12 종료면 +0.37h, 최대 +0.75h 라 약 6.85시간·8h 안). 같은 PR 에서 기본정보 실패를 예외로 받게 바꿔, 실패한 단지의 매칭·관리비 행을 덮어쓰거나 지우던 길도 막았다. 지속 한계는 1초에 1콜에 못 미친다(두 측정으로 추정 약 0.9콜/초 + 여유 약 20콜 — 1.0초도 오래 부르면 막힌다. 1.5초는 10분·400콜 통과). 미분양 레포의 K-apt 수집(6일·10/11일·15~19일 05:30, 0.2~0.4초 간격)이 창구를 막아 놓으면 그날 06:20 회차는 벌칙 중에 시작한다(12:40 회차가 받친다 — 미분양 세션에 인계, 2026-10-01). **세 번째 회차 21:00**(스케줄러 id `kapt_costs_evening`, 세션 426 — 사장님 결정 2026-10-01): 1.5초 간격이면 두 회차로는 한 달 수요의 97~107% 라 매월 최신 달을 못 따라가 같은 함수·같은 배치로 한 번 더 돈다(밤에도 같은 속도 제한 — 10-01 23:30 실측, 길면 약 23:30 끝나 01:30~ 밤 배치 창과 안 겹침. 기존 행 재수집 스크립트는 20:30 이후 시작 거부·20:45 에 멈춰 이 회차와 창구를 나눠 쓰지 않는다). 세 회차가 다 되는 날 K-apt 약 14,400콜. **관리비 단지 연결(`kapt_match`)이 running 이면 모든 관리비 회차가 잡 행 없이 건너뛰고(`match_running`), 관리자 "단지 관리비 받기" 버튼은 409 로 알린다** — 같은 간격을 나눠 쓰고 매칭이 관리비 행을 정리하므로. 21일 저녁 회차는 대개 건너뛴다(매칭 약 6.1시간 + 꼬리, 21:00 전에 끝난 날만 평소대로). **실패 알림은 연속 두 회차 실패일 때만** — 한 번 실패는 다음 회차가 받아 주므로, 세션 427 사장님 결정(`crawler/monitor.py _MIN_CONSECUTIVE_FAILED_BY_TYPE` — 끝난 회차(완료·실패)만 최신순으로 세고 도는 중·취소된 회차는 건너뛴다. 묶음 실패·마비·자료 오래됨 알림은 그대로). |
| 정부 자료 창구 살아있나 확인 (data.go.kr API 버전 감시) | 일요일 06:40 | 코드가 쓰는 엔드포인트 13종 생사 확인 → dead 시 텔레그램 (상세: [§잡 상세 — data.go.kr API 버전 감시](../../backend/.claude/details.md#잡-상세--datagokr-api-버전-감시)) |
| 서버 일감 점검 (크롤링 모니터) | 10분 interval(라이브 `.env` `MONITOR_INTERVAL_MIN` — 코드 기본·release.md 생성 표는 30분) | crawl_jobs 정합성 점검 → 텔레그램. **알림은 전부 쉬운 우리말**(§텔레그램 알림 문구). **stale running 잡을 `_STALE_HOURS_BY_TYPE` 임계로 자동 cancelled(`swept by monitor`)** — 부팅 스윕(5분)이 못 잡은 "재시작 직전 시작 잡"도 1h 뒤 여기서 정리된다(세션 410 정정, release.md §3-0) (상세: [§잡 상세 — 크롤링 모니터](../../backend/.claude/details.md#잡-상세--크롤링-모니터)) |


### 잡 상세 (표에서 덜어낸 원문)

> 여섯 잡(매물 상세 보강(매물 상세 내용 채우기)·공동주택 공시가격·응급의료·K-apt 단지 매칭(관리비 단지 연결하기)·data.go.kr API 버전 감시(정부 자료 창구 살아있나 확인)·크롤링 모니터(서버 일감 점검))의
> 원문은 **`backend/.claude/details.md` §스케줄러 잡 상세** 에 있다(세션 411 이동 — 이 규칙 파일은 세션·서브에이전트마다
> 통째로 읽히므로, 파고들 때만 필요한 원문은 명시 참조 파일로 뺐다. 내용 무손실). 위 표의 `§잡 상세 — …` 링크가
> 그쪽을 가리킨다. **잡의 동작을 바꾸면 표와 그 절을 함께 갱신**한다.

## 관찰성 인프라 (세션 340 — 운영 중 문제를 볼 수 있게)

- **외부 uptime 감시** = `.github/workflows/healthcheck.yml` (매일 05:30 KST cron 1회 + workflow_dispatch. 2026-08-02 10분→일1회 격하, 사장님 결정. 05:30 = 새벽 재부팅 직후).
  ⚠ **격하 사유였던 "Actions 무료한도 소진"은 거짓 전제였다 — 세션 398(2026-09-11) 적대검증 실측으로 확정.**
  이 레포는 **public**(`gh api repos/developer-duno/naver-estate-web --jq .visibility` → `public`, 2026-03-12 생성 이래)이고,
  **public 레포의 GitHub-hosted runner 사용은 무료·무제한**이라 2,000분 쿼터 자체가 적용되지 않는다
  ([공식 문서](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions):
  "GitHub Actions usage is free ... for public repositories"). 실측으로도 최근 run 의 `/timing` `billable.UBUNTU.total_ms` 가 **전부 0**.
  또 "7/13 소진 → CI 월말까지 마비"도 사실이 아니다 — 7/13~7/20 창의 run 을 `gh api` 로 나열하면 CI·dependabot 이 정상 실행됐고,
  같은 창 Health Check 는 **306회 failure + 5회 success** 로 **실행 자체는 계속됐다**(= 쿼터 차단이 아니라 대상(터널)이 실제로 죽어 있었던 것).
  즉 그 시기 감시는 정상 작동해 터널 사망을 **정확히 포착하고 있었다**.
  → **비용 제약이 없으므로 일 1회 유지의 근거가 사라졌다.** 현재 최대 24시간 통지 지연은 근거 없는 손실이다.
  다만 UptimeRobot 5분 감시(`backend/.claude/details.md` §Supabase DB 전면 다운 런북과 재발 이력 의 처방)가 그 공백을 이미 메우고 있는지 먼저 확인해 **중복 여부를 판단한 뒤**
  주기 상향을 사장님께 재문의할 것(세션 398 백로그 §12). GitHub Actions(집서버 무관)가 `curl https://api.2u.pe.kr/health/db` → 실패 시 텔레그램(secrets `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, 미설정 시 안전 스킵). **집서버가 통째로 죽으면 내부 watchdog 도 함께 죽어 무통지**이던 사각지대를 외부에서 메움. ⚠ GitHub Actions `if:` 에 `secrets` context 사용 불가(공식) → secrets 는 `env:` 로 주입해 shell 판정(PR #276 hotfix). CI 문법은 `gh workflow run` 라이브 실행만 ground truth. ⚠ **Cloudflare Bot Fight 모드를 켜면 이 외부감시가 오탐으로 전멸** — GH runner(미국 데이터센터 IP + curl)가 "관리 챌린지"를 못 풀어 403 을 받고, origin 로그엔 요청 자체가 안 남는다(2026-08-09 실사고: 8/8~8/9 이틀 연속 오탐, 서버는 정상. 공인 감시봇은 면제라 통과). 무료 플랜 BFM 은 경로 예외를 못 걸어 `/health/db` 만 빼는 것도 불가 → **켜기 전 healthcheck 영향 검토 의무**. 403 을 받으면 집서버가 아니라 CF 보안설정부터 의심 (워크플로가 HTTP 코드를 캡처해 403 을 별도 문구로 구분 알림).
- **심층 헬스체크** = `backend/routers/health.py` `/health/db` (DB `SELECT 1`, 성공 200 / DB장애 503 클린 JSON, **GET/HEAD 허용** — 외부 감시 HEAD 프로브 405 방지, 세션 353). 외부 모니터 전용. ⚠ 기존 `/health`(정적 200, main.py:208)는 **일부러 얕게 유지** — watchdog 이 폴링하는데 DB 장애 시 503 주면 "backend 죽음" 오판 → 무한 재시작 루프(재시작으로 DB 안 살아남). watchdog=프로세스 생존만, /health/db=DB 포함.
- **backend.log 회전 보존** = `scripts/log_rotation.py` `rotate_backend_log()`. `start_backend()` 가 매 재시작 backend.log 를 `"w"` 로 truncate 해 어제 크래시 로그 소실되던 것 → 재시작 직전 `backend_<mtime>.log` 로 회전 보존 + 7일 초과분 정리. 안정 경로 backend.log 유지(release.md §2 `head -1 scripts/backend.log` 불변). ⚠ orchestrator 상주 프로세스라 **재부팅(또는 release.md §3 `Restart-Service naver-orchestrator`)이 있어야 회전 코드 적용**(startup_orchestrator.py 수정 = orchestrator zombie 대상). 프로세스명은 현행(nssm 서비스, 세션 363+) 항상 pythonw — 옛 "경로 따라 python/pythonw 갈림"(세션 353)은 레거시 수동 기동 시에만.
- **결제·크롤 알림 삼킴 로그화** = billing_charge.py·payment.py·service_discover.py 의 `except: pass`(알림 발송 실패) → `logger.warning`(best-effort 유지). 결제 로직은 안 깨지되 알림 실패가 관찰 가능.

> 상세 = 글로벌 메모리 `[[session340-summary]]`·`[[project-observability-backlog-s340]]`. 백로그 2건(connect_timeout 공용엔진·open(w) 파일락)은 PR #278(09b61e4, 2026-07-04)에서 완료 — `db/database.py` connect_args connect_timeout=5, `startup_orchestrator.py` open() try/except 가드로 코드 직독 재확인 완료(세션 352).

### data.go.kr 호출 일정 표 (infra.md §data.go.kr API 쿼터 에서 이동)

| 일자 | 프로젝트 | 워크플로우 | 창구(카운터) | 추정 호출수 |
|------|----------|-----------|------|------------|
| 매월 1일 | mibunyang | collect-unsold-kosis | (옛 표 그대로 — 창구 미확인) | ~1(원문 — 옛 표) |
| 매월 5일 | mibunyang | collect-population, market-stats | (옛 표 그대로 — 창구 미확인) | ~100(원문 — 옛 표) |
| 매월 6일 | mibunyang | collect-trades + molit-units | 실거래가(RTMS) 추정 | ~1,500~3,800(원문 — 옛 표) |
| 매월 10일 | mibunyang | **collect-building-info** | **K-apt 창구 — 실거래가와 별도 카운터**(메모리 `project_data_source_map` 정정, 세션 421 검사관 C) | **~8,500**(원문 — 옛 표) |
| 토요일 05:00 | naver-estate-web | collect_public_trades(주간) | 실거래가(RTMS) | **~6,100**(추정 — 코드 253 시군구 × 24개월 = 6,072, 1,000건 넘는 달은 여러 쪽이라 더 많음. 09-26 실측 190/253 시군구에 ≈4,900. 옛 표 "~3,600" 은 낡은 값) |
| 매일 03:30 | naver-estate-web | backfill_price(소급) | 실거래가(RTMS) | 상한 30단지 × 24개월 = 720, 캐시 적중으로 실제 ≈150~330(추정 — 09-26 회차 153초 실측에서 역산, 세션 421 검사관) |
| 평일·토 08:00 | KOSPI | daily.yml 실거래가 250지역 | 실거래가(RTMS) 매매 ≈756 + 전월세 ≈756 | ~1,500(원문 — KOSPI `.github/workflows/daily.yml` 55행 주석, 두 서비스 합) |
| PR·수동마다 | KOSPI | **rehearsal.yml("Closing Rehearsal")** — 진짜 열쇠로 실거래가 수집 | 실거래가(RTMS) 매매 ≈756 + 전월세 ≈756 | 회당 1,512(원문 — 실행 로그 "[수집]아파트 호출 1501~1506/1512건"). **2026-09-29 부터 기본 0**(KOSPI 결정 0030 — 리허설은 실거래가 수집을 건너뛰고 필요할 때만 켬, 세션 421 조율) |
| 사장님 지정일(주로 자정 직후) | KOSPI | 실거래가 소급(backfill-real-estate.yml 수동 발사 또는 로컬 예약 작업) | 실거래가(RTMS) | 회차당 최대 3,000~6,000(원문 — `--max-cells` 값, 09-27 01:09 회차 2,720칸·분당 20~45콜 실측) |

### 실거래가 캐시·광주·전남 (같은 절에서 이동)

- 실거래가 캐시는 한 회차 안에서만(세션 422) — 주간 수집·소급 배치가 시작·끝에 `PublicDataAPI.clear_trade_cache()` 로 비운다(옛 코드는 재시작 전까지 지난 회차의 달을 재사용해 새 거래를 못 받았다). 비울 때 로그 한 줄 `[정부 실거래가] 실거래가 캐시 비움: 달 N개·거래 M건`(비어 있어도 0·0 — 재시작 뒤 첫 03:30 소급에 이 줄이 보이면 새 코드). 소급 호출 규모 = 기본 30단지 × 24 = 약 720(1,000건 넘는 달은 여러 쪽이라 더 — 상한 아님). 늘어나는 양: 평일 0~약 300콜(재시작이 잦아 원래도 캐시가 비어 있던 날이 많았다) · **토요일 +약 300**(05:00 주간이 03:30 소급이 받아 둔 달을 다시 받는다). 관리자 단건 소급(`/backfill-price/{no}`)은 캐시를 비우지 않지만 다음 주간·소급 회차 시작에서 비워진다. 배치를 반복 호출하는 일회성 스크립트(`scripts/backfill_apartment_public_data.py`)는 `clear_cache=False` 로 배치 사이 캐시를 나눠 쓰고 끝에서 한 번 비운다.
- 광주·전남 12체계는 실거래가 창구가 직접 받는다(세션 424 — 번역 제거. 8/10(PR #341) 번역 도입 뒤 12체계 27 시군구(단지 2,838곳 중 정부 줄이 있던 약 1,000곳)가 7주 동안 0건이었다 — 창구가 바뀐 것이 아니라 번역이 멀쩡하던 수집을 끊은 것. 회복 예정 = 반영 뒤 첫 토요일 주간이 24달을 다시 받는다 — 그 회차가 429 로 끊기지 않았는지와 12체계 단지에 8~9월 정부 줄이 생겼는지 확인). 2026-10-01 27 시군구 전수 실측: 새 코드 25/27 건수 있음 · 옛 29/46 코드 0/27. 공시가격(V-WORLD)은 여전히 옛 코드라 `to_vworld_cortar` 로 번역한다 — 두 창구가 다르다.
