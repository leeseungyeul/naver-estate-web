# PR 머지 후 backend 가동 검증 룰

(상세: .claude/rules-detail/release.md §룰 신설 배경)

## 룰 본문

### 1. 트리거 (의무 적용)

다음 PR 머지 시 본 룰 발동:

- backend 스케줄러 설정 변경 (`crawler/scheduler.py`, `crawler/monitor.py`, `crawler/service_metrics.py`)
- 환경변수 추가/변경 (`backend/.env.example`, 새 `os.getenv` 호출)
- backend 의존성 변경 (`backend/requirements.txt`) — ⚠ **머지만으로는 부품이 안 바뀐다.** `requirements.txt` 는
  *주문서*이고 실제 설치본은 그대로다(세션 404 실측: 머지 후에도 psycopg2 2.9.12·filelock 3.32.5 상주).
  **머지 → `pip install` → 재시작 3단계**를 다 해야 반영이다. 2단계를 건너뛰고 재시작만 하면 4중 지표가
  전부 초록인데 **옛 부품이 도는** zombie 와 같은 상태가 되고, "반영 완료"는 거짓 보고가 된다.
  검증은 라이브가 쓰는 파이썬으로 `python -c "import psycopg2; print(psycopg2.__version__)"` —
  `pip` 의 `Successfully installed` 출력은 그 자체로 증거가 아니다(설치 대상 인터프리터가 다를 수 있다).
  ⚠ 이 PC 파이썬은 **전역 공유**(`Python312`, 집서버 4프로젝트 동거)라 교체는 다른 프로젝트에도 적용된다 —
  사장님 승인 후 진행하고, 되돌리기는 `pip install "<패키지>==<옛버전>"`.
- DB 마이그레이션 (`backend/db/migrations/V*.sql`)
- backend 모듈 import 흐름 변경 (`main.py`, `routers/*`, `crawler/*`)

FE 만 변경된 PR (frontend/*) 은 본 룰 면제.

⚠ **여러 PR을 짧은 간격으로 연속 머지할 때는 매번 재시작하지 말고 묶어서 한 번에
재시작해도 된다**(`backend/.claude/details.md` §스케줄러 운영 배경 3절 「짧은 주기 크론과 재시작 겹침」 답습 — 반복 재시작이 크론
실행 시각과 겹쳐 일시적 오탐을 낼 수 있다, 세션 372 실사고). 단 묶어서 재시작하면
**그 안의 어느 PR이 zombie였는지 개별 구분이 안 되는 대가**가 있다 — 재시작 후 4중
지표가 옛값이면, 묶음 안의 PR을 머지 순서 역순으로 하나씩 되짚어(이분 탐색 재시작)
원인 PR을 격리한다. 확실하게 개별 검증하고 싶으면 원칙(PR마다 재시작)을 유지해도 된다 —
묶음 재시작은 선택지이지 의무 완화가 아니다.

### 2. 머지 직후 4중 cross-check 의무

머지 직후 다음 4 지표를 동시 확인. 하나라도 옛 시각/옛값이면 zombie 의심. (4번째 = 표시값 PR 한정 필수, 세션 257 신설)

⚠ **반영 확인에는 재시작 직후 옛 코드와 새 코드가 다른 값을 내는 지표만 쓴다**(세션 419 검사관 C). "2시간 넘게 도는 잡이 목록에 보이면
새 코드" 처럼 조건이 붙는 지표는 재시작 게이트(running 0)와 동시에 성립할 수 없어 그 자리에서 판정이 안 된다 — 그런 지표는 **확인
가능한 시각**을 함께 적어 두고 그때 본다.

| 지표 | 확인 명령 | 기대 |
|---|---|---|
| **orchestrator.pid mtime** | `ls -la scripts/orchestrator.pid` 또는 `stat -c '%y' scripts/orchestrator.pid` | 머지 시각 이후 |
| **backend.log 첫 줄 시각** | `head -1 scripts/backend.log` (uvicorn 부팅 시각) | 머지 시각 이후 |
| **crawl_jobs 최신 row** | 해당 PR 변경한 잡의 최신 row 가 새 코드 기대 동작 일치 (예: PR #61 = `complex_metric` total=1000) | 새 코드 동작 |
| **관리자 화면 표시값(라이브 GET)** | `.env` SUPABASE_JWT_SECRET 로 admin 토큰 발급 후 `GET /api/admin/scheduler-status` → `jobs[].schedule` | 새 코드 표시값 (정적 분석·pytest 로 대체 불가 — 라이브만 ground truth, §5-1 답습) |

위 지표가 머지 시각 이후로 모두 갱신되어야 새 코드 반영 확정. ⚠ 표시값 변경 PR (예: SSOT 자동생성) 은 trigger 동작이 새값이어도 **화면 표시는 표시 모듈 본문이 옛 코드라 옛값 잔존** 가능 — 4번째 지표(라이브 GET) 필수 (세션 257 사고).

⚠ **"4중" 은 PR 성격에 따라 줄어든다** (세션 301 정정). 3번째(crawl_jobs)는 *스케줄러 잡 변경* PR 전용, 4번째(관리자 표시값)는 *표시값 변경* PR 전용. **정렬·쿼리 로직만 바꾼 PR (예: PR #167 mb 정렬)** 은 스케줄러 잡도 표시값도 아니라 3·4번째 부적용 → 적용 지표 = ①orchestrator.pid/PID ②backend.log 부팅시각 ③**해당 PR 이 바꾼 API 의 라이브 GET 동작** = 3중. crawl_jobs 새 row 가 안 생기는 게 정상이지 zombie 아님.

(상세: .claude/rules-detail/release.md §거짓양성 차단 — prod DB 직접 실측 (세션 301))

### 3. zombie 발견 시 처리 절차

4 지표 중 하나라도 옛 시각/옛값이면:

**현행 (세션 363+ — nssm 서비스 `naver-orchestrator`, 2026-08-14 00:19 라이브 훈련 검증):**

**3-0. 재시작 직전 확인 (예외 0 — 세션 397 절차 누락)**

재시작은 **돌고 있는 잡을 끊는다**(부팅 스윕이 running 잡을 cancelled 처리). 명령을 치기 전에
① 지금 running 인 잡이 있는지 ② 앞으로 5분 안에 도래할 크론이 있는지 둘 다 본다.

⛔ **판정 명령에 파이프를 붙이지 말 것**(세션 411 실사고, details.md §release 사건 박제 표 411 행): `python check.py | grep -v "slow query" && Restart-Service …`
는 파이프 종료코드가 **grep 의 0** 이라 스크립트가 WAIT(exit 1)를 내도 `&&` 가 통과한다. 잡음 제거는 스크립트 안에서 하거나
`out=$(python check.py 2>&1); echo "$out"; [[ "$out" == *GO* ]] && …` 처럼 **문자열로 판정**한다(꼭 파이프면 `set -o pipefail`).
②의 "5분 안" 판정에는 `GET /api/admin/scheduler-status` 의 `next_run_at` 을 써도 된다 — jitter 가 이미 반영된 확정값이라
interval 잡(crawl_details 30분±15)도 시각표 추정 대신 그 값으로 정확히 본다(세션 411 검사관 C 실측).

⚠ **①의 "running 0" 만으로는 부족하다 — 짧은 하위 잡을 이어 붙이는 수집은 잡 사이 틈에 0 으로 보인다**(세션 421 실사고:
일요일 03:00 새 단지 찾기 `discover_regions` 는 `complex_list` 행을 지역마다 몇 초씩 229개 이어 붙여 평소 03:00~03:49 에 도는데,
03:37 재시작이 그 틈에서 GO 를 받아 130/229 에서 끊었다). ①에 **최근 90초 안에 시작·종료된 행**도 본다 — 있으면 WAIT:
`SELECT job_type, count(*) FROM crawl_jobs WHERE greatest(started_at, coalesce(completed_at, started_at)) >= now() - interval '90 seconds' GROUP BY 1`.
**일요일 03:00~03:50 은 사실상 재시작 금지 구간**(아래 표는 시작 시각만 보여 준다).

```bash
# (1) running 잡 — 있으면 끝날 때까지 대기. 특히 official_price 는 3~7h 라 절대 중단 금지
cd /d/naver-estate-web/backend && PYTHONPATH=. PYTHONUTF8=1 python -c "
from sqlalchemy import text; from db.database import SessionLocal
with SessionLocal() as db:
    print(db.execute(text(\"SELECT job_type FROM crawl_jobs WHERE status='running'\")).fetchall())"
# (2) 5분 내 크론 — 현재 KST(요일·일자 포함)를 아래 전수 시각표와 대조
date "+%F(%a) %H:%M"
```

⚠ **(1)·(2) 는 재시작 명령 "직전"에 본다 — 확인과 `Restart-Service` 사이가 1분을 넘기면 (1) 을 다시 돌린다.**
세션 409 실사고(2026-09-17): 02:20 에 (1) "running 0건" 을 확인하고 다른 일을 하다가 02:24:42 에
재시작했는데, 그 사이 **02:21:49 에 `article_detail`(#53918) 이 시작**돼 있었다. 부팅 스윕
(`main.py _sweep_stale_running_jobs`)은 **시작 후 5분이 지난** running 잡만 cancelled 처리하므로
(세션 208 — 1h 는 오히려 오탐이라 낮춘 값, **되돌리지 말 것**) 방금 시작한 잡은 부팅 스윕엔 안 잡힌다.
⚠ 단 "영구 고착"은 아니다(세션 410 적대검증 정정): **크롤링 모니터(서버 일감 점검, 10분 interval)가 같은 조건으로
두 번째 스윕**을 돌려 `_STALE_HOURS_BY_TYPE` 임계(기본 1h)가 지나면 `stale running — swept by monitor`
마커로 자동 cancelled 처리한다(`crawler/monitor.py` — 90일 실측: monitor 스윕 20건·부팅 스윕 15건·현재
고착 0). 즉 짧은 잡은 **1시간 기다리면 저절로 정리**되고, 그 사이 `crawl_stale` 경보가 1건 날 뿐이다.
사람이 손대야 하는 경우는 임계가 긴 잡(official_price 16h·kapt_match 8h·kapt_costs 3h)을 끊었을 때뿐.

- 순서: (1)(2) 확인 → **곧바로** `Restart-Service`(같은 분 안에). 사이에 다른 일을 했으면 (1) 부터 다시.
- 이미 끊었으면(재시작 뒤에도 `status='running'` 인데 프로세스는 새것): 임계 1h 잡은 monitor 에 맡기고,
  임계가 긴 잡만 그 **한 건** 수동 정리 — (monitor 스윕과 경합해도 `AND status='running'` 가드로 no-op 이라 안전)
  ```sql
  UPDATE crawl_jobs SET status='cancelled', completed_at=now(),
         error_message = COALESCE(error_message || ' | ', '') || 'stale running — 재시작 직전 시작, 수동 정리'
   WHERE id = <id> AND status = 'running';   -- 가드 필수: 그 사이 끝났으면 no-op
  ```
  (부팅 스윕 마커와 같은 접두어라 `LIKE '%stale running%'` 한 조건으로 함께 조회된다.)
아래 표는 `backend/scripts/gen_restart_schedule_table.py` 가 scheduler.py·monitor.py 에서 생성한다.
손으로 고치지 말 것 — `tests/test_restart_schedule_table.py` 가 코드와의 드리프트를 막는다.
갱신 = `cd backend && python scripts/gen_restart_schedule_table.py --write ../.claude/rules/release.md`
interval 잡(시각 `—` 행)의 주기는 **코드 기본값**이다 — 라이브 `.env` 가 덮을 수 있고(`crawler_monitor`: 코드 30분·라이브 10분) jitter 도 붙으므로
5분 판정은 위 `next_run_at` 으로 한다. 표는 토글을 전부 켠 상태로 만들어 라이브에서 꺼진 잡(`billing_charge` 등)도 보인다 — "언제든 돌 수 있는 잡 전부"가 기준.
(상세: .claude/rules-detail/release.md §시각표 생성기 이력)

<!-- restart-schedule:start -->
<!-- 이 표는 backend/scripts/gen_restart_schedule_table.py 가 생성한다. 손으로 고치지 말 것. -->

| 시각 | 잡 | 주기 | 스윕 임계 |
|---|---|---|---|
| 00:20 | ⏰ `backfill_detail_dawn` | 매일 00:20 | 4h |
| 01:00 | ⏰ `collect_childcare` | 매월 첫째 목요일 01:00 | 3h |
| 01:00·13:00 | `crawl_articles` | 매일 01:00, 13:00 | 1h |
| 02:00 | `collect_air_quality` | 매일 02:00 | 1h |
| 03:00 | `collect_emergency` | 매월 첫째 월요일 03:00 | 1h |
| 03:00 | `discover_regions` | 주 1회 일요일 03:00 | 1h |
| 03:30 | ⏰ `backfill_price` | 매일 03:30 | 12h |
| 03:50 | `vacuum_maintenance` | 매일 03:50 | 1h |
| 04:00 | `collect_crime_stats` | 분기별 첫째 일요일 04:00 | 1h |
| 04:00 | ⏰ `collect_prices` | 주 1회 수요일 04:00 | 3h |
| 04:30 | `collect_metrics` | 매일 04:30 | 1h |
| 04:40 | `field_drift_monitor` | 매일 04:40 | 1h |
| 04:50 | `billing_charge` | 매일 04:50 | 1h |
| 05:00 | `collect_officetel_presale` | 주 1회 월요일 05:00 | 1h |
| 05:00 | ⏰ `collect_public_trades` | 주 1회 토요일 05:00 | 8h |
| 05:30 | `collect_rental_presale` | 주 1회 월요일 05:30 | 1h |
| 06:20 | ⏰ `kapt_costs` | 매일 06:20 | 3h |
| 06:30 | ⏰ `official_price` | 매월 15일 06:30 | 16h |
| 06:40 | `api_version_probe` | 주 1회 일요일 06:40 | 1h |
| 07:00 | `complex_detail_ABYG` | 주 1회 수요일 07:00 | 1h |
| 07:00 | `complex_detail_JGC` | 주 1회 화요일 07:00 | 1h |
| 07:00 | `complex_detail_OBYG` | 주 1회 목요일 07:00 | 1h |
| 10:45 | `popular_1030` | 매일 10:45 | 1h |
| 12:20 | ⏰ `backfill_detail_noon` | 매일 12:20 | 4h |
| 12:40 | ⏰ `kapt_costs_noon` | 매일 12:40 | 3h |
| 14:45 | `popular_1430` | 매일 14:45 | 1h |
| 14:50 | ⏰ `kapt_match` | 매월 21일 14:50 | 8h |
| 19:15 | `popular_1900` | 매일 19:15 | 1h |
| 21:00 | ⏰ `kapt_costs_evening` | 매일 21:00 | 3h |
| — | `crawl_details` | 30분마다 | 1h |
| — | `crawler_monitor` | 30분마다 | 1h |
| — | `complex_detail_APT` | 4시간마다 | 1h |
| — | `complex_detail_OPST` | 4시간마다 | 1h |

⏰ = 재시작 절대 금지 구간(스윕 임계 1h 초과 = 오래 도는 잡): backfill_detail_dawn(4h) · collect_childcare(3h) · backfill_price(12h) · collect_prices(3h) · collect_public_trades(8h) · kapt_costs(3h) · official_price(16h) · backfill_detail_noon(4h) · kapt_costs_noon(3h) · kapt_match(8h) · kapt_costs_evening(3h)
<!-- restart-schedule:end -->

겹치면 **그 회차가 끝난 뒤로 미룬다.** 여러 PR 을 묶어 한 번에 재시작하는 것도 겹침을 줄인다(§1 말미).

⚠ **(1) 의 running 조회는 DB 에 접속한다.** DB 장애로 재시작하려는 상황이면 이 명령도 실패한다 —
그때는 **조회 실패 자체를 "확인 불가"로 받아들이고** `scripts/backend.log` 마지막 줄과 위 시각표만으로
판단한다(DB 가 죽었으면 크론도 대부분 실패 중이므로 끊을 작업이 없을 가능성이 높다).
DB 다운 진단·처방은 `backend/.claude/details.md` §Supabase DB 전면 다운 런북과 재발 이력이 우선.

**3-1. 재시작 실행**

⚠ 창을 기다렸다가 재시작하는 루프를 **백그라운드로 걸 때는 "멈춤 파일"(예: `STOP` 파일이 있으면 exit)을 루프 안에 넣는다** —
Windows 에서 `TaskStop` 은 bash 껍데기만 끝내고 안쪽 스크립트가 고아로 살아남을 수 있다(세션 421: "멈췄다"고 보고한 뒤 그 스크립트가
재시작을 실행했다). 멈춘 뒤에는 명령줄에 스크립트 이름이 든 프로세스가 사라졌는지 확인한다.

```powershell
# 비관리자 셸 그대로 실행 가능 — 서비스 DACL 에 사용자 시작/중지 권한 등록됨
#   (install_orchestrator_service.ps1 1-b 단계)
# 고정 Sleep 금지 — 포트가 뜰 때까지 폴링(최대 120초). 세션 397 실측: 서비스 "중지 대기"에만
#   약 1분, 기동까지 약 65초라 45초 시점의 빈 포트 출력을 "실패"로 오판해 재실행할 뻔했다.
#   즉 판정 기준은 "얼마나 기다렸나"가 아니라 "포트 소유 PID 가 바뀌었나"다.
$before = (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue).OwningProcess
Restart-Service naver-orchestrator        # nssm 이 orchestrator+uvicorn 트리 통째 종료 후 재기동
$deadline = (Get-Date).AddSeconds(120)
do {
  Start-Sleep -Seconds 5
  $after = (Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue).OwningProcess
} while (-not $after -and (Get-Date) -lt $deadline)
"before=$before after=$after"                                 # 기대: 서로 다른 값 (같으면 재시작 미발생)
Get-Content D:\naver-estate-web\scripts\startup.log -Tail 8   # 기대: 새 "백엔드 정상 시작 완료"
Get-Content D:\naver-estate-web\scripts\orchestrator.pid      # 기대: 새 PID
curl.exe -s https://api.2u.pe.kr/health/db                    # 기대: {"status":"ok","db":"ok"}
```

**120초 안에 포트가 안 뜨면**(`$after` 가 빈값): 재실행하지 말고 **원인부터 본다.**
① `Get-Service naver-orchestrator` 상태 확인(Stopped 면 `Start-Service`) ②
`Get-Content scripts\startup.log -Tail 20` 으로 기동 실패 사유 확인 ③ `scripts\backend.log` 첫 줄
(uvicorn 부팅 로그)이 갱신됐는지 — 셋 다 이상 없는데 포트만 없으면 DB 연결 실패로 기동이 막힌 것일 수 있으니
`backend/.claude/details.md` §Supabase DB 전면 다운 런북과 재발 이력으로 넘어간다. **무작정 Restart-Service 재실행은 상황을 악화시킨다.**

- ⚠ **`Restart-Service` 는 조용히 실패할 수 있다 — 실행 후 "포트 소유 PID 가 바뀌었는지"로 판정한다**
  (세션 396 실측: 첫 시도 후 45초를 기다렸는데 `startup.log` 시각·8002 포트 소유 PID 가 그대로였다. 같은 명령을
  `try/catch` + 전후 상태 출력으로 감싸 재실행하니 정상 동작). **판정 지표 = `(Get-NetTCPConnection -LocalPort 8002
  -State Listen).OwningProcess` 가 재시작 전과 다른 값**. 기다림만으로 성공을 단정하지 말 것 — bash 파이프에서
  PowerShell 출력이 "Binary file matches" 로 가려지는 경우도 있어(로그가 cp949) 출력 부재 = 성공 아님.
- ⚠ **`orchestrator.pid` 는 검증 지표로 쓰기 전에 "존재하는지"부터 본다** — 파일이 사라진 상태(세션 396 사고로
  삭제)에서는 4중 cross-check 의 한 축이 조용히 무력화된다. 없으면 재시작 후 orchestrator 가 새로 쓰므로,
  그 전까지는 포트 소유 PID·`startup.log` 시각·`backend.log` 첫 줄 PID 세 축으로 판정한다.
- ⛔ **비관리자 `Stop-Process` 로 서비스 프로세스(orchestrator·backend)를 직접 죽이는 것은
  액세스 거부로 불가** — 서비스는 UAC 필터링 없는 전체 토큰으로 돌아서다 (세션 363 훈련 1차
  실측). 레거시(details.md 로 이동)의 "프로세스 kill 후 재기동" 흐름을 현행 환경에서 쓰지 말 것.
- ⚠ 서비스 orchestrator 는 session 0 이라 비관리자 조회에서 CommandLine=NULL — CommandLine
  grep 이 0건이어도 "orchestrator 없음" 단정 금지. 판정은 `orchestrator.pid` + `Get-Service
  naver-orchestrator` + startup.log 로.
- orchestrator 급사 시 nssm 이 60초 내 자동 재기동 — 개입 전 startup.log 최신 헤더부터 확인
  (이미 자가복구됐을 수 있다).

**레거시(nssm 서비스 제거·수동 운용 폴백 시에만 유효 — 옛 Startup BAT 시절 kill+schtasks 5단계)** 는 세션 412 에 `backend/.claude/details.md` §release 레거시 재기동 절차 로 원문 이동. 현행 환경에서 그 흐름(비관리자 Stop-Process·세션 셸 직접 기동)은 쓰지 말 것.

**통상은 현행 `Restart-Service` 1줄로 충분** (훈련 실측 중단 ~15초). PC 재부팅도 여전히 안전한
최후 수단 — 세션 363부터는 서비스가 부팅 시 자동 기동하므로 **로그인 없이도** 복구된다(옛
Startup BAT 시절엔 로그인해야 기동 — infra.md §자동 시작 사건 참조). 세션 셸 직접 기동만은
여전히 절대 금지.

### 4. 사건 박제 (왜 이 룰?)

(상세: .claude/rules-detail/release.md §4. 사건 박제 안내)

### 5. 본 룰 비적용 사례 (false trigger 방지)

다음은 본 룰 트리거 아님:

- **FE 만 변경 PR** (frontend/* 만) = backend 가동 무관
- **md 만 변경 PR** (CLAUDE.md, .claude/*, docs/* 만) = 본 PR 같은 문서 정합 작업 = 가동 무관
- **테스트 만 추가 PR** (backend/tests/* 만) = 새 import 없으면 가동 무관
- **`crawler/*`·`routers/*` 등 실행 코드 파일이 포함돼도, diff 전체가 순수 주석/docstring
  텍스트뿐이고 실행 가능한 코드 구조(함수 정의·SQL 호출·조건문·dict 리터럴 등)가 단 한 글자도
  안 바뀐 경우** = 가동 무관. **단 이 판정은 "diff를 눈으로 봤더니 주석 같다"는 직감만으로
  내리면 안 되고, AST(추상 구문 트리) 비교 등 기계적 방법으로 "실행 코드 구조 동일"을
  실제로 확인해야 한다** — 그렇지 않으면 §5-1이 금지하는 "정적 분석만으로 단정"과 같은
  실수가 된다 (세션 386 사후검증에서 발견).

### 5-1. 정적 분석만으로 "재시작 면제" 단정 금지 (세션 257 사고)

코드 읽기·git diff·pytest 통과로 "재시작 불필요"를 단정하지 말 것. 다음은 모두 **라이브 프로세스 상태를 증명하지 못한다**:

- lazy import (`함수 내부 from X import`) 는 X 모듈만 지연 — **그 import 문을 담은 호출처 모듈 본문(함수 정의)은 부팅 때 옛 버전으로 메모리 상주**. 옛 프로세스의 옛 함수는 새 lazy import 를 애초에 호출하지 않는다.
- pytest 통과 = **디스크 코드 self-consistency** 증명 (테스트는 디스크 fresh import + fresh scheduler 생성). 부팅한 프로세스 메모리 상태와 무관.

판정은 **라이브 실측**으로만: 살아있는 엔드포인트를 실제 호출 (`.env` SUPABASE_JWT_SECRET 로 admin 토큰 발급 → GET scheduler-status) 하거나, backend.log 의 trigger/next-run 로그로 현재 프로세스의 실제 등록값을 본다. 글로벌 `[[feedback-browser-measurement-overrides-plan]]` 와 같은 패턴.

⚠ **crawler_monitor(크롤링 모니터(서버 일감 점검)) 잡의 실동작 확인은 위 두 방법이 전부 무효**다(세션 391 실측) — monitor 는 CrawlJob 을 안 남겨 scheduler-status 의 last_run/runs 가 영구 null/0 이고, 정상 스캔은 로그도 안 찍는다(무음 설계). 유일한 유효 경로 = prod `pg_stat_user_tables` 에서 freshness 대상 4테이블(trades·complex_price_history·crawl_jobs·complexes)의 **동시 스캔 타임스탬프가 monitor 주기(10분) 간격으로 반복**되는지 확인.

(상세: .claude/rules-detail/release.md §5-1 사건 (세션 257))

### 6. Cross-link

(상세: .claude/rules-detail/release.md §Cross-link)
