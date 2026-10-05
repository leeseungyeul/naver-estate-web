# 인프라·운영 규칙

## 집 서버 재시작 후 복구 절차

### 자동 시작 (정상 경로 — 세션 363부터 nssm 서비스)

**nssm 서비스 `naver-orchestrator`**(부팅 시 지연 자동 시작, **로그인 불필요**, 실행 계정
`.\user`)가 `scripts/startup_orchestrator.py`를 실행:
1. 기존 프로세스 정리 (port 8002)
2. 백엔드 서버 시작 → health check 대기 (터널은 별도 nssm 서비스 `cloudflared-naver` 전담)
3. Watchdog (30초 간격 생존 감시, backend 죽으면 재시작)
4. orchestrator 프로세스 자체가 죽으면 **nssm 이 60초 후 자동 재기동** (AppRestartDelay=60000)

- ⚠ **재부팅 직후 콜드 부팅은 43초까지 걸린다**(2026-09-27 01:02 실측 — 이 PC 는 nssm 서비스 9개가 동시에 뜬다). 오케스트레이터는 30초 뒤에도 백엔드 프로세스가 살아 있으면 **겹쳐 띄우지 않고 60초 더 기다리고**(`BACKEND_HEALTH_GRACE`), 다시 띄울 땐 **자기 프로세스부터 끝낸다**(`_terminate_proc`, watchdog 도 같음 — PR #605). 옛 코드는 포트를 아직 못 잡은 첫 프로세스를 `_kill_port` 가 못 죽여 둘을 겹쳐 띄우고, 둘째가 포트 충돌(종료코드 3)로 죽자 워치독이 멀쩡한 첫째를 죽였다(01:04 "백엔드 다운→복구" 헛경보 1건, 피해 0). 따뜻한 재시작에선 이 분기가 안 타므로 새 코드 적재 판정 = 오케스트레이터 프로세스 시작 시각 > 파일 수정 시각(세션 421).
- 설치/재설치 = `scripts/install_orchestrator_service.ps1` (관리자 PowerShell 1회). 옛 로그인
  Startup BAT 는 `startup-server.bat.disabled` 로 보존 (서비스 제거 시 원복 폴백).
- 서비스 DACL 에 사용자 계정의 시작/중지 권한 등록됨 → **비관리자 세션도
  `Restart-Service naver-orchestrator` 로 재시작 가능** (재시작 절차 = release.md §3).
- ⚠ 서비스 프로세스는 session 0 + UAC 필터링 없는 전체 토큰: 비관리자 조회에서
  CommandLine=NULL(프로세스 grep 무동작), 비관리자 `Stop-Process` 는 액세스 거부(세션 363
  훈련 실측). 프로세스 탐색은 `scripts/orchestrator.pid`, 재시작은 Restart-Service 로.

(상세: .claude/rules-detail/infra.md §nssm 전환 사건·재발 검증)

### 수동 복구 (자동 시작 실패 시)

```bash
# 1. 백엔드 서버 실행 (집 서버 cmd)
D:
cd naver-estate-web\backend
python -m uvicorn main:app --host 0.0.0.0 --port 8002

# 2. Named Tunnel 실행 (cmd 하나 더)
cloudflared tunnel run naver-estate-backend
```

URL이 고정(api.2u.pe.kr)이므로 Vercel 재배포 불필요.

### Named Tunnel 초기 셋업 절차 (1회성 — 완료·운영 중, 재설치 시 참고)

(상세: .claude/rules-detail/infra.md §Named Tunnel 셋업 명령)

### Vercel 프로젝트 정보

(상세: .claude/rules-detail/infra.md §Vercel 프로젝트 정보)
- ⚠ Hobby 무료는 약관상 비상업적 한정 — 유료 결제 서비스라 매출 시작 시 Pro 전환 (사장님 결정). 상세 = 글로벌 메모리 `[[project-vercel-github-freetier-infra]]`.

## DB 커넥션 풀

- **NullPool** 사용 (요청마다 연결/해제) — Supabase Session Mode 동시 연결 한도 방지
- `db/database.py`에서 설정

### statement_timeout 적용 방식 (세션 255 실측 — 함정 주의)

- **폭주 쿼리 안전망 = `connect` 이벤트의 `SET statement_timeout`** (env `STATEMENT_TIMEOUT_MS`, 기본 8000ms). NullPool 이라 매 요청 새 연결 → connect 이벤트가 매번 발동 → 모든 세션 보장.
- ⚠ **`connect_args={"options": "-c statement_timeout=..."}` 는 작동 안 한다.** Supabase Supavisor 풀러가 startup `options` 파라미터를 무시함 (`SHOW statement_timeout` 이 기본 2min 그대로). [Supabase Timeouts 공식문서](https://supabase.com/docs/guides/database/postgres/timeouts): transaction mode 에선 role-level `ALTER ROLE` 도 무효, 연결 직후 명시 `SET` 만 세션에 적용.
- 검증법 = prod 연결로 `SHOW statement_timeout` (8s 기대) + `SELECT pg_sleep(9)` (8.0초에 QueryCanceled 기대). 실제 앱·배치 쿼리는 0.03~0.05초라 false positive 없음 (인덱스 없는 풀스캔 GROUP BY 만 8초 초과 → 죽음).
- **예외는 세는 명령으로 확인**(숫자를 문서에 고정하면 새 예외가 생겨도 안 갱신되니 — 세션 424 보완): `grep -rn 'text(f\?"SET \(LOCAL \)\?statement_timeout' backend --include=*.py | grep -v "/tests/"`(2026-10-01 현재 5곳: 관리자 상세 통계·정보 안 채워지면 알림(둘 다 `SET LOCAL`, 트랜잭션 단위) + service_discover 2곳·vacuum_maintenance 1곳(연결 단위 `SET`, 세션 단위)). 둘 다 PostgreSQL 일 때만 걸고 다른 연결·다른 잡은 8초 그대로다:
(상세: .claude/rules-detail/infra.md §statement_timeout 예외 두 곳의 경위)

### 슬로우 쿼리 로깅 (세션 255)

- `services/slow_query_log.py` — `before/after_cursor_execute` 이벤트로 `SLOW_QUERY_MS`(기본 1000) 초과 SQL 을 `logger.warning` (best-effort). prod `engine` 에만 attach, 테스트는 conftest SQLite 격리로 영향 0.

### Supabase DB 전면 다운 — 런북·재발 이력은 `backend/.claude/details.md` (세션 412 이동)

`/health/db` 가 `degraded` 이거나 statement timeout 이 연쇄로 터지면 **[details.md §Supabase DB 전면 다운 런북과 재발 이력](../../backend/.claude/details.md#supabase-db-전면-다운-런북과-재발-이력)** 의
8단계(층위 순서로 국소화 → Postgres Logs 원문 확인)를 따른다. 여기 남기는 결론 두 줄:

- **처방 = 자가회복 대기 우선**(실사고 2건 29분·34분 자가회복). ⛔ 성급한 backend 재시작 금지 — 재시작은 DB 를 못 살리고, 부팅 스윕(시작 5분 경과 running 잡)이 외부 프로세스의 잡까지 cancelled 로 오염시킨다.
- 컴퓨트 Micro→Small·V048 freshness 인덱스·UptimeRobot 5분 감시는 세션 381 에 적용 완료. "OOM 크래시"는 확정이 아니라 **가설** — 재발 시 대시보드 → Observability → Logs → Postgres Logs 에서 `out of memory`/`PANIC`/`FATAL` 원문부터 확인해 승격한다.

## 텔레그램 알림 문구 — 전부 쉬운 우리말 (전 창구 공통, 예외 0)

> 사장님 지시(2026-09-15): *"텔레그램 알림은 일반인이 봐도 무엇이 어떻게 잘못되었는지
> 손쉽게 알 수 있어야 해. 그 부분을 절대로 간과하면 안 돼. 어려운 말은 금지야."*

⚠ **이 규칙은 특정 잡이 아니라 텔레그램을 쓰는 모든 코드에 적용된다.** 세션 408 까지는
`크롤링 모니터`(서버 일감 점검) 표 행 안에만 적혀 있어서, 새 알림을 만드는 사람이 못 보고 지나쳤다
(그 결과 8개 창구 중 4곳이 영문·개발자 용어인 채로 남았다) — 그래서 독립 절로 올린다.

### 금지 (알림 본문에 다시 넣지 말 것)

영문 job_type·DB 컬럼명(`total_floor_count`)·개발자 에러 원문(`psycopg2…`)·파일:줄
위치·`batch`/`running`/`red`·`엔드포인트`·`웹훅`·`락`·`임계`·env 변수명·`[BILLING]`·
`[PAYMENT]` 같은 영문 접두어. **접두어는 3채널 공통 `[서버 알림]`** 하나뿐이다.

### 사전 (한 곳에서 관리)

(상세: .claude/rules-detail/infra.md §텔레그램 알림 사전 위치 표)

⚠ **잡 이름 체계가 둘이고 서로 다르다**(`crawl_details`(id) vs `article_detail`(job_type)).
한쪽 사전만 채우면 "고쳤는데 실제로는 그대로 나가는" 상태가 된다 — 세션 408 에 실제로
리스너 경로만 고치고 **주 발화 경로(monitor → `alert_format`)를 놓쳤다**.

### 의무

- 새 `job_type` → `JOB_WORDS` + FE `crawl-job-labels.ts` 양쪽 등록(`test_plain_words.py` 가 대조).
- 결제·정산 잡은 **"돈이 안 걷힌다"** 안내로 갈린다(`action_words_for_job*`) — 수집용
  "새 자료만 안 들어와요" 를 쓰면 심각도를 정반대로 알린다.
- `crawl_jobs.error_message` 도 관리자 화면에 보이므로 같은 기준을 적용한다. **단 알림과 화면은 함수가 다르다**(세션 411 PR #534):
  알림 = `explain_error`(아는 에러면 번역, 못 알아보면 고정 문장 + INFO 수집 로그) / 화면 = `explain_stored_error`
  (⓪붙은 스윕 마커 분리 → ②번역 → ③**이미 우리말이면 원문 유지** → ④고정 문장, **로그 없음** — 화면 폴링 60초·3~15초가
  P1-2 수집 로그를 오염시키므로). 그래서 `세션388 수동 중단 — kaptCode …` 같은 사람이 쓴 문장은 알림에선 "처음 보는 문제",
  화면에선 원문 그대로 보인다 — **화면이 더 자세한 것은 의도**(검사관 C A-2). 라우터는 `error_plain` 을 raw 옆에 실어 주고
  FE 는 `error_plain || error_message` + `title=raw`. 관리자 카드의 **버튼 조작 오류**(`detail`)도 창구다 —
  `routers/admin/collect.py` 의 수집 버튼(`POST /collect/{name}`)은 세션 420 부터 수집기를 백그라운드로 돌려 `started`/409(우리말 고정 문구)로 답하고, 예외 원문은 로그에만 남는다(사유는 그 잡의 crawl_jobs 행 → 화면). 스레드 시작 실패는 500, 단건 소급(`POST /backfill-price/{no}`)은 여전히 동기라 실패 시 500 + `explain_error` 우리말 사유.
- 접두어 회귀는 `test_plain_words.py` 가 **`.py` 9모듈(세션 421 부터) + 워크플로 YAML** 을 전수 추출해 막는다.

### 적용 현황·라이브 확인 — `infra-scheduler.md` 로 이동 (세션 430)

창구 목록(모듈 9개·호출부 12곳)·재유입 가드·`scripts/verify_alert_wording.py` 라이브 확인 명령·"잡 이름은 두 곳(`add_job(name=…)`·`_JOB_LABEL_FALLBACK`)을 함께 고친다" 주의는
`.claude/rules/infra-scheduler.md` 에 원문 그대로 있다(`backend/crawler/**` 등을 열면 자동으로 읽힘). **새 알림 창구를 만들거나 알림 문구를 고치기 전에 그 절을 연다.**

## 스케줄러 (APScheduler)

> 잡별 주기·배치·토글·설명 표, 잡 이름 대조표(옛 → 새), 잡 상세 링크는 **`.claude/rules/infra-scheduler.md`** 로 옮겼다(세션 430 —
> `backend/crawler/**`·`backend/scripts/**`·`backend/routers/admin/**` 등을 열면 자동으로 읽힘). **DB 만 조회하거나 수동 실행을 정할 때도**
> 잡 주기·배치·토글이 궁금하면 그 파일을 직접 연다. 재시작 판정용 전수 시각표는 `release.md` §3-0(생성 표).

⚠ **위 표의 "잡 이름"은 스케줄러 등록 id(`scheduler.py`의 `id="..."`)이고, DB
`crawl_jobs.job_type` 컬럼에 실제로 저장되는 값은 이와 다를 수 있다** — 이 프로젝트
전반의 기존 관례이지 버그가 아니다. 예: 스케줄러 id `collect_officetel_presale` →
job_type `officetel_presale`(접두어 없음), id `collect_rental_presale` → job_type
`rental_presale`, id `crawl_details` → job_type `article_detail`(이름 자체가 다름).
**DB로 "이 잡이 실행됐나" 조회할 때는 반드시 각 서비스 모듈(`crawler/service_*.py`)의
`CrawlJob(job_type="...")` 호출부를 먼저 grep 해 정확한 job_type 문자열을 확인**한다 —
스케줄러 id를 그대로 조회하면 0건이 나와 "실행 안 됐다"고 오판하기 쉽다(세션 372
실사고: 이 함정에 두 번 걸림). 컬럼명도 `finished_at`이 아니라 `completed_at`이니
`db/models.py`의 `CrawlJob` 정의를 함께 확인할 것.

### 재시작 겹침·잡 에러 리스너·monitor freshness — 원문은 `backend/.claude/details.md` (세션 412 이동)

세 절(짧은 주기 크론과 재시작 겹침 · 스케줄러 잡 에러 최후 안전망 · monitor freshness 풀스캔 timeout 방지 — 세션 340~372)의
원문은 **[details.md §스케줄러 운영 배경 3절](../../backend/.claude/details.md#스케줄러-운영-배경-3절)** 에 있다. 여기 남기는 규칙 세 줄:

- 여러 PR 을 연속 배포할 때 **매 PR 마다 재시작하지 말고 묶어서 한 번**. 텔레그램 "마비→복구" 알림이 몰리면 진짜 장애인지 재시작 부작용인지 **재시작 시각과 먼저 대조**한다(세션 372: 하루 8회 재시작이 만든 오탐 4건).
- CrawlJob 기록 **전에** 예외로 죽거나 misfire 로 스킵된 잡은 `crawler/job_error_listener.py`(EVENT_JOB_ERROR|MISSED, `(kind, job_id)` 별 600초 쿨다운, best-effort)가 잡는다 — monitor 의 사각을 메우는 최후 안전망(세션 340, PR #273).
- monitor 의 `compute_freshness` 는 별도 세션 격리 + max/count 분리 + reltuples 근사(V038·V039)로 **상시 1초 미만**을 유지한다(9.2초→0.6초). 신선도·집계 쿼리에 새 대형 테이블을 붙이면 인덱스 또는 근사가 의무 — 8초 statement_timeout 이 monitor 자신을 죽인다(세션 342).


## 관찰성 인프라 — 상세는 `infra-scheduler.md` (세션 430 이동)

외부 감시(healthcheck.yml)·`/health/db`·backend.log 회전·알림 삼킴 로그화의 원문은 `infra-scheduler.md`. 파일을 안 열고도 어길 수 있는 두 줄만 여기 남긴다:
- `/health`(정적 200)는 **일부러 얕게** 둔다 — watchdog 이 폴링하므로 DB 장애에 503 을 주면 무한 재시작 루프가 된다. DB 를 포함한 검사는 `/health/db`(외부 감시 전용).
- **Cloudflare Bot Fight 모드를 켜기 전 healthcheck 영향 검토 의무** — GitHub Actions 외부 감시가 403 으로 전멸한다(2026-08-09). 403 이면 집서버가 아니라 CF 보안설정부터 의심.

## 공유 인프라 규칙 (mibunyang 프로젝트와 공유)

### data.go.kr API 쿼터 (동일 키를 **세 프로젝트**가 공유 — 한도는 **서비스별** 일일 10,000회)

같은 키(`PUBLIC_DATA_API_KEY`)를 **naver-estate-web·mibunyang·KOSPI daily_report** 세 프로젝트가 같이 쓴다
(KOSPI `config.py` 의 `DATA_GO_KR_KEY` 값 동일 — 세션 421 실측). 한도는 키 전체가 아니라 **서비스별** 10,000/일이다 —
실거래가(RTMS)와 K-apt 는 **별도 카운터**(세션 420 실측). 리셋은 한국 자정(세션 420 판정, 09-27 01:06 남은 9,794 로 부합).
창구가 응답 헤더 `x-ratelimit-remaining`·`x-ratelimit-limit` 로 남은 횟수를 알려주며 200·429 모두에 온다(세션 420·421 실측),
연속 3콜 차이 1·1 = 포털 집계는 1배(세션 421 실측).

> 프로젝트별 호출 일정 표(미분양·KOSPI·우리 잡 9행)는 `infra-scheduler.md` §data.go.kr 호출 일정 표로 옮겼다(세션 430). 수동 실행으로 그날 한도를 쓸 일이 있으면 그 표부터 본다.

- "매월 10일 토요일 건너뛰기"는 전부 삭제됐다 — 실거래가 주간 수집(세션 421)·공기질·어린이집(세션 422, 2026-09-27). 미분양 사이트 building-info 는 K-apt 창구(별도 카운터)라 합산 전제가 성립하지 않는다.
- **위험일(진짜)**: **KOSPI 가 토요일 새벽(00:00~06:00)에 실거래가를 많이 쓰면 05:00 주간 수집과 같은 예산을 먹어 429 로 끝난다** — 2026-09-26 사고 = 우리 ≈4,900(자체 카운터 6,245 − 429 벽 뒤 ≈1,356) + **KOSPI rehearsal.yml 7회 ≈5,300**(01:57~04:17 KST, 세션 421 검사관 C `gh run list` 실측). 소급뿐 아니라 **리허설(PR 마다 진짜 열쇠)** 도 같은 예산. 조율 창구 = KOSPI 메모리 인계 메모 `handoff_from_2u_2026-09-27_shared_data_go_kr_key.md`.
(상세: .claude/rules-detail/infra.md §data.go.kr 남은 횟수 알림 문턱)
- 실거래가 캐시를 회차마다 비우는 것(세션 422)·광주·전남 12체계를 창구가 직접 받는 것(세션 424)의 상세 = `infra-scheduler.md` 같은 절.

- **K-apt 개별관리비 창구도 미분양이 같이 쓴다**(세션 422 검사관 C-615 확인): 미분양 `scripts/collectors/collect-maintenance.mjs` 가 **AptIndvdlzManageCostServiceV3**(우리 `kapt_costs` 의 개별관리비 5 op 와 같은 창구, 5·46행)를 매월 **15~19일 05:30** 회당 ≈3,600콜(`--limit=600` × 단지당 ~6콜) 쓴다 — 실행 = 미분양 `scripts/kosis-local-runner.mjs:215-225`(Windows 작업 MibunyangKosisLocal, 매일 05:30). 그 닷새는 06:20 관리비 회차 직전에 같은 창구 몫이 먼저 쓰인다.

### CPMS cpmsapi030 키 공유 (어린이집 API — 일일 1,000건, 동일 키 공유, 세션 366)

naver 의 `CHILDCARE_DETAIL_API_KEY` == mibunyang 의 `CHILDCARE_BASIC_API_KEY` (같은 키).
**mibunyang childcare-detail 이 매일 04:30 에 쿼터 1,000건을 설계상 전량 소진**한다
(전국 시설 23,122곳 70필드 순환 갱신, ~23일 주기 — 의도된 설계, 멈추면 손해).

- naver `collect_childcare` 는 **첫째 목 01:00 고정** (자정 리셋 직후 ~250콜 선사용 — 세션 393
  전량 전환 후 값. 전량이어도 시군구당 1콜 캐시 구조라 상한 248콜, 2026-09-05 실측). 06:00
  시절 2026-07·08 두 달 연속 INFO-300 즉사가 신설 계기. **04:30 이후로 이동 금지.**
(상세: .claude/rules-detail/infra.md §CPMS 별도 키 발급 불가 실측)
- 이 키의 운영계정 만료 = **2027-04-07** (만료 30일 전부터 포털에서 기간연장 신청 — 놓치면
  naver·mibunyang 어린이집 수집 동시 정지).

### 네이버 크롤링 시간 분리 (같은 집 서버 IP)

(상세: .claude/rules-detail/infra.md §네이버 크롤링 시간 분리 표)

### IP 차단 방지 (절대 규칙)

같은 집 서버 IP 로 네이버를 크롤링하므로, 짧은 시간에 대량 요청하면 IP 가 차단된다.

1. **모든 네이버 수집 코드는 `AdaptiveThrottle` 경유 필수.** `crawler/utils.py` 의 `get_shared_throttle(name, ...)` 로 인스턴스를 받아 단지·페이지 루프마다 `.wait()` 호출. 429 응답 시 자동 감속(`on_rate_limit`). throttle 우회한 직접 반복 호출 금지.
2. **크롤 지표 컬럼을 SQL 직접 일괄 UPDATE 로 찍지 말 것.** `complexes.last_crawled_at`·`complexes.detail_crawled_at`·`articles.detail_crawled` 는 실제 크롤 코드(`CrawlJob` 생성 경유)만 갱신한다. SQL 로 일괄 UPDATE 하면 "크롤된 것처럼" 보이지만 실제 데이터는 없어 진단을 망친다.
3. **`articles.detail_fail_count` 일괄 리셋은 정비 잡 전용, 수동은 단건만.** 상한 매물 되살리기는 일일 정비 잡(정기 VACUUM 유지보수(자료 보관함 정리), 매일 03:50)이 CAP-1 부여로 이미 한다(매물당 하루 1콜 유계). 손으로 `WHERE detail_fail_count > 0` 같은 일괄 0 리셋을 박으면 그 매물들이 상한까지 N매물×6콜을 다시 태우며 한꺼번에 재유입돼 네이버 부하가 튄다. 수동 개입은 특정 매물 1건(`WHERE article_no = '...'`)만.

(상세: .claude/rules-detail/infra.md §IP 차단 사건 (2026-04-13))

### 공용 테이블 규칙 (같은 Supabase DB)

- 공용 (양쪽 upsert): `complexes`, `articles`, `complex_price_history`
- `trades`: **mibunyang write 전용** (매월 6일 collect-trades), **naver-estate 는 read-only**. naver-estate 는 이 테이블에 절대 안 쓴다(신선도 카드가 읽기만 함 — 세션 343 실측 확정). 옛 "양쪽 upsert" 표기는 부정확.
- `infra` · `air_quality_stations`: **naver-estate 도 write** (환경 수집 스케줄러). 옛 "mibunyang 전용" 표기는 부정확 (세션 343 정밀분석 실측 확정). 컬럼 분담 =
(상세: .claude/rules-detail/infra.md §infra·air_quality_stations 컬럼 분담)
  - ⚠ ALTER/DROP 시 **양쪽 영향 검토 필수** ("mibunyang 전용" 오판 금지).
- mibunyang 전용: `apartments`, `unsold_history`, `regions`, `prices`, `trade_stats`, `builders`, `schools`, `transport`
- **기존 컬럼 타입 변경/삭제 금지** — 컬럼 추가만 허용
- ALTER/DROP 전 상대 프로젝트의 SELECT 쿼리/ORM 모델 검색 필수
- 컬럼명 불일치 주의: naver-estate-web은 `latitude`/`longitude`, mibunyang은 `lat`/`lng` (mb_models.py alias)

### 권한·정책·뷰·함수를 바꾸는 마이그 = mibunyang 기준선 재승인 요청 (세션 417 신설, 2026-09-24)

공유 DB(`rwdtljipvmqpazrimyns`)의 public·storage **표/뷰/정책/GRANT/함수 SECURITY 속성/기본 권한/확장/역할/버킷**(146항목)은
mibunyang 쪽 감시가 **매주 월요일 09:00 KST** 에 사장님 승인 기준선(#1, 2026-09-24)과 대조해 하나라도 다르면 텔레그램 경보를 낸다.
열 추가·데이터 변경·인덱스는 지문에 안 들어간다(경보 없음). 따라서 그런 것을 바꾸는 마이그(V0xx)를 운영에 적용한 뒤에는
**반드시 mibunyang 세션에 재승인 요청을 남긴다** — 바뀐 물건 이름·명령·역할·조건을 한 줄씩
(`~/.claude/projects/f--mibunyang/memory/handoff_from_2u_<날짜>_<주제>.md` + 그 폴더 `MEMORY.md` 맨 위 한 줄, 또는 그 세션에 SendMessage).
mibunyang 이 미리보기로 "달라진 것이 그것뿐"인지 대조해 accept 한다(다른 변경이 섞이면 멈추고 사장님께). 첫 사례 = V063(세션 417).

- 새 public 표는 Supabase 기본 권한으로 anon/authenticated 에 전권한이 자동 부여된다 → **RLS 를 켜지 않은 새 표는 즉시 공개.**
  새 표·정책은 **클라이언트 쓰기 정책 없이 backend 경유**가 원칙(`user_profiles` 는 V062 로 클라이언트 쓰기 회수, `login/page.tsx` 보조 upsert 는 정리 대상).
- `payments`·`billing_keys` 는 V065 로 anon/authenticated 전 권한을 회수했다(2026-09-24, 세션 417) — RLS 켜짐·정책 0·클라이언트 권한 0. 새 정책을 붙일 땐 service_role 전용으로.
- 관리자 판정은 **user_id 기반**이 원칙(이메일 판정 금지 — 세션 417 에 `backend/deps.py` 를 `role == "admin"` 또는 `ADMIN_USER_IDS` 로 교체).

## DB 백업·DR — 마이그레이션 전 수동 스냅샷 (세션 367 신설)

(상세: .claude/rules-detail/infra.md §DB 백업 실태·도구 (2026-08-14 실측))

**절차 (마이그레이션 SQL Editor 실행 전 의무)**:

- 컬럼/테이블 **추가만**(CREATE·ADD COLUMN): 스키마 덤프 1회.
- **DROP·ALTER·대량 UPDATE 동반**: 스키마 + 데이터 덤프까지.
- 공유 DB 주의: mibunyang 테이블도 같은 DB 라 덤프에 함께 담기는 게 정상(복구 시 양쪽 영향 검토 — 위 §공용 테이블 규칙).

(상세: .claude/rules-detail/infra.md §DB 백업 덤프 명령)

- **표준 도구 = 로컬 `pg_dump`** (18.4, scoop — 서버 PG 17.6 하위호환 확인). ⚠ `supabase db dump` 는
  pg_dump 를 **Docker 컨테이너로** 돌려서 Docker Desktop 미실행 시 실패한다 (2026-08-14 V047 사전덤프 실측
  — "failed to inspect docker image"). 이 PC 평상시엔 Docker 꺼져 있으므로 pg_dump 직행이 표준.
- 덤프 저장 = 레포 밖 `D:\db-backups\naver-estate\` (git 추적 위험 원천 차단, D=내장 NVMe).
(상세: .claude/rules-detail/infra.md §DB 백업 덤프 범위·첫 실전)
- **Pro 확정(현행) 운용**: 일일 자동 백업이 1차 안전망 — 단 백업 시점 이후 그날 유입분은 미보호이므로, **DROP·ALTER·대량 UPDATE 동반 마이그레이션은 실행 직전 수동 덤프 필수** 유지(컬럼 추가만인 건은 권장). 복구가 필요하면 대시보드 Database > Backups 에서 복원 시점 선택 — 복원은 프로젝트 전체 롤백이라 mibunyang 데이터도 함께 되돌아감(양쪽 세션 합의 후 실행).
