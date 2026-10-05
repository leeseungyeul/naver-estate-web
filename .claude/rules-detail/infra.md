# infra.md 상세 — 상시 로드 안 함

`.claude/rules/infra.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## nssm 전환 사건·재발 검증

> **사건 (2026-08-12~13, 세션 363 규명 — nssm 전환 계기)**: Windows Update(KB5120249)가
> 야간(18:56) 계획 재부팅 → 옛 Startup BAT 는 사용자 Startup 폴더 소재라 "로그인 시"에만
> 실행 → PC 는 켜져 있는데 로그인 화면에서 13시간 backend 다운(watchdog 도 같이 미기동,
> 03:30 정기 백필 등 스케줄 전체 미실행). 로그인만으로 복구되던 사각지대를 서비스 전환으로
> 근본 해소 (부팅만으로 기동 + orchestrator 급사 자동복구까지 확보).
>
> **재발·검증 (2026-09-09 22:07, 세션 395)**: 같은 종류의 계획 재부팅(이벤트 1074: 22:05 svchost → 22:07 TrustedInstaller
> "업그레이드(계획됨)", OS 부팅 22:07:33)이 다시 났고, nssm 서비스가 **로그인 없이 22:10:35 자동 기동·22:10:51 health 성공(3분)**
> — 끊긴 잡·부팅 스윕 cancelled·경보 전부 0. 이 PC 는 Windows Update Active Hours 미설정(레지스트리 `WindowsUpdate\UX\Settings`
> 부재 = 자동 감지 기본값)이라 **재부팅 시각은 예측 불가**가 정상 — 크론(02:00~04:50)과 겹치면 부팅 스윕이 그 회차를 cancelled
> 처리하고 다음 회차가 이어받는 게 설계 동작이다. 사유 판별은 `.ps1` 파일 경유 `Get-WinEvent`(Id 1074/41/6008) —
> 인라인 `-Command` 는 bash 가 `$_` 를 먹는다(release.md 함정).

## Named Tunnel 셋업 명령

```bash
cloudflared tunnel create naver-estate-backend
cloudflared tunnel route dns naver-estate-backend api.2u.pe.kr
```

`~/.cloudflared/config.yml`:
```yaml
tunnel: naver-estate-backend
credentials-file: ~/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: api.2u.pe.kr
    service: http://localhost:8002
  - service: http_status:404
```

Vercel에 `NEXT_PUBLIC_API_URL=https://api.2u.pe.kr` 영구 설정 (설정 완료).

## Vercel 프로젝트 정보

- 프로젝트: `naver-estate-web`. **Root Directory = `frontend`** (세션 323 라이브 `vercel project inspect` 실측 정정 — 옛 "루트에서 배포" 기술은 틀림. 루트엔 package.json·next.config 둘 다 없음, Vercel 이 frontend 를 빌드 루트로 잡음).
- 도메인: `2u.pe.kr`, `www.2u.pe.kr`
- `frontend/vercel.json` 의 `ignoreCommand`(`git diff --quiet HEAD^ HEAD -- .`)로 frontend 무관 커밋은 빌드 스킵 (세션 323). Root Directory(frontend) 안에서 실행되므로 경로 `-- .`. exit 0=스킵·exit 1=진행.

## statement_timeout 예외 두 곳의 경위

  1. 관리자 상세 통계 `GET /api/admin/stats/detailed`(`routers/admin/jobs.py` `_cached_detailed_stats`, 2026-09-26): 운영 부하 시간대에 count 들이 8초를 넘겨 500 이 나서, **결과를 프로세스 안에 5분 캐시**(숫자가 최대 5분 늦는 것은 의도 — 버그 아님)하고 **다시 계산할 때만 그 트랜잭션에 `SET LOCAL statement_timeout = 30000`**. 계산이 실패하면 옛 값으로 대신하지 않고 500 그대로.
  2. 정보 안 채워지면 알림(`field_drift_monitor`) 잡의 집계 문장(`crawler/field_drift_monitor.py` `compute_fill_rates`, 세션 424): 09-29~10-01 사흘 연속 `QueryCanceled` 로 실패. **주원인** = WHERE 조건 모양이 V061 부분 인덱스(`ix_articles_field_drift_window`) 술어와 달라(`IS true` vs `= true`) PostgreSQL 이 그 인덱스를 한 번도 고르지 않은 것(운영 EXPLAIN 실측: `IS true` 모양 = 두 인덱스 합치고 본 테이블 스캔, 비용 77,452, 8초 초과 / `= true` 모양 = 부분 인덱스 스캔, 비용 9,465, 4.61초 cold·0.11초 warm) — `Article.is_active == True`·`Article.detail_crawled == True` 로 정정해 근본 해결. 여기에 48시간 창 모집단이 2026-09-13 실측 8,832건에서 상세 보강 강도 증가로 48,887건(5.5배)까지 불어난 것도 함께 작용해, `SET LOCAL statement_timeout = 30000` 을 안전망으로 얹었다.

## 텔레그램 알림 사전 위치 표

| 사전 | 위치 | 키 체계 |
|---|---|---|
| 작업 이름 30종 | `crawler/plain_words.py` `JOB_WORDS` | **DB `job_type`** |
| 매물 필드 15종 | `crawler/field_drift_monitor.py` `_FIELD_WORDS` | `articles` 컬럼명 |
| 잡 라벨 31종 | `crawler/job_error_listener.py` `_JOB_LABEL_FALLBACK` | **스케줄러 잡 id** |
| 에러 번역·행동 안내·조사 | `crawler/plain_words.py` `explain_error`·`action_words*`·`eul_reul` — ⚠ 못 알아본 에러는 **원문 없이 고정 문장**만 나간다(세션 410, 원문은 로그·`crawl_jobs.error_message` 에), 결제 사유는 PortOne 상태별 4규칙이 **목록 맨 앞** | — |

## data.go.kr 남은 횟수 알림 문턱

- **대응**: 우리 잡이 시작·끝의 남은 횟수를 로그로 남기고 부족하면 알린다(세션 421 PR). 알림 문턱 = 시작 남은 횟수 < 예상(주간 6,072) + 여유 1,000 = 7,072 — 평소 토요일(≈9,300~9,700)엔 조용, KOSPI 소급 3,000 뒤(≈6,280)엔 울린다(의도), 05:00 전 2,928 넘게 쓰였을 때 울림(사장님 확정 2026-09-27). 여유 1,000 은 소급(03:30)에도 똑같이 붙는다(소급 문턱 = 단지 수 × 24 + 1,000). 여유분 = `service_public._REMAINING_MARGIN`(1,000건 넘는 달은 여러 쪽이라 예상보다 많이 쓴다) · 알림의 "최대 약 N번" 은 예상값 그대로, 문턱은 로그 한 줄에(세션 422).

## CPMS 별도 키 발급 불가 실측

- 별도 키 발급은 불가 실측(2026-08-14): 포털은 1계정 1API 1키(재신청 버튼 숨김) + 일 한도
  1,000 하드캡(증량 불가) + 새 키는 신규 회원가입 필요. 상세 = 글로벌 메모리 `[[session366-summary]]`.

## 네이버 크롤링 시간 분리 표

| 시간 | 프로젝트 | 작업 | 실행일 |
|------|----------|------|--------|
| 02:00 | naver-estate-web | collect_air_quality | 매일 |
| 03:00 (첫째 월) | naver-estate-web | collect_emergency | 매월 첫째 월 |
| 03:00 | naver-estate-web | discover_regions | 일요일 |
| 03:30 | naver-estate-web | backfill_price (data.go.kr, 네이버 0) | 매일 (PUBLIC_DATA_ENABLED) |
| 04:00 | naver-estate-web | collect_prices | 수요일 |
| 06:20 | naver-estate-web | kapt_costs (data.go.kr, 네이버 0 — 관리비 아침 회차) | 매일 |
| 06:30 (15일) | naver-estate-web | official_price (V-WORLD, 네이버 0) | 매월 15일 (OFFICIAL_PRICE_ENABLED) |
| 05:30 | mibunyang | KOSIS 로컬 러너 10종 (kosis.kr, 네이버 0 — Windows 작업 MibunyangKosisLocal, 세션 289 GH→집서버 이전) | 매일 (일자 디스패치) |
| 4h interval | naver-estate-web | 단지 상세 backfill APT/OPST(아파트·오피스텔 단지 정보 채우기) | 매일 |
| 07:00 | naver-estate-web | 단지 상세 backfill JGC·ABYG·OBYG(재건축·분양권 단지 정보 채우기) | 화·수·목 |
| 08:00 | mibunyang | 로컬 naver-collect.py | 월/목 |
| 10:45/14:45/19:15 | naver-estate-web | popular 크롤링 | 매일 |
| 12:40 | naver-estate-web | kapt_costs_noon (data.go.kr, 네이버 0 — 세션 422 관리비 낮 회차) | 매일 |
| 21:00 | naver-estate-web | kapt_costs_evening (data.go.kr, 네이버 0 — 세션 426 관리비 저녁 회차, 길면 약 23:30 끝) | 매일 |
| 01:00 / 13:00 | naver-estate-web | crawl_articles (cron, ±45분 jitter — 세션 402 에 12h interval 에서 전환) | 매일 |
| 00:20 / 12:20 | naver-estate-web | 상세 백필 — backfill_detail_dawn(배치 1500·약 38분) / backfill_detail_noon(배치 4000·실측 113~134분), 상세 API. 키 드리프트로 빈 채 굴러간 필드(난방·총층수 등)를 사후 보강한다. 토글 `BACKFILL_DETAIL_ENABLED`(코드 기본 false — 2026-09-14 라이브 .env 에서 ON). 배치 조절은 `BACKFILL_DETAIL_BATCH_SIZE` | 매일 |
| 30m interval | naver-estate-web | crawl_details | 매일 |

## IP 차단 사건 (2026-04-13)

> **사건**: 2026-04-13 — `last_crawled_at` 이 하루에 29,944개(전체 75%) 동일 날짜로 찍힘. 그날 `crawl_jobs` 0건 → 크롤이 아니라 SQL 직접 일괄 UPDATE. 그 단지들의 단지상세 채움률은 2.6%뿐 — `last_crawled_at` 이 허수가 되어 데이터 진단을 장기간 어지럽힘.

## infra·air_quality_stations 컬럼 분담

  - `infra`: naver 가 `air_updated_at`(env_air.py:88) · `crime_updated_at`(env_crime.py:119·186) · `emergency_*`(env_emergency.py:53~56) · `childcare_*`(env_childcare.py:93~102, 신규 INSERT 포함) write. mibunyang 은 나머지 인프라 컬럼 write.
  - `air_quality_stations`: naver 가 에어코리아 측정소 캐시 `_do_upsert(AirQualityStation)` write (env_air.py:112~126).

## DB 백업 실태·도구 (2026-08-14 실측)

**실태 (2026-08-14 실측)**: **Pro 플랜 확정** — 사장님 대시보드 스크린샷 실측(developer-duno's Org **PRO** 뱃지, 프로젝트 naver-estate, main PRODUCTION). Supabase 공식 정책상 Pro = **일일 자동 백업·7일 보존**(PITR 은 별도 유료 애드온 — 가입 여부는 대시보드 Database > Backups 탭 소관). 같은 프로젝트를 쓰는 mibunyang 데이터도 동일 백업에 함께 담긴다. 이 절 신설 전까지 레포에 백업 스크립트·문서 0건. (참고: Free 였다면 자동 백업 0 — 플랜 다운그레이드 시 이 절의 수동 덤프가 유일 안전망으로 승격됨을 유의.)

**도구 (이 PC 실측)**: supabase CLI 2.84.2(scoop shims) + pg_dump 18.4 설치됨. ⚠ 이 PC 의 supabase CLI 활성 로그인은 **플라워 그룹 계정**이라 naver-estate 프로젝트가 `projects list` 에 안 뜬다(gh 계정 전역 스위치와 같은 함정). 단 `supabase db dump --db-url` 방식은 **로그인·link 불필요** — 백업 실행엔 지장 0.

## DB 백업 덤프 명령

```bash
# backend cwd. DATABASE_URL 은 dotenv 로드로만 사용 — 값 echo·화면 출력 절대 금지
# (~/.claude/rules/secret-output-commands.md 답습. .env 직접 read 는 deny 라 python 경유가 표준)
cd backend && python -c "
from dotenv import load_dotenv; load_dotenv('.env')
import os, subprocess, datetime
os.makedirs('D:/db-backups/naver-estate', exist_ok=True)
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
subprocess.run(['pg_dump','--schema-only','--no-owner','--no-privileges','--schema','public',
                '-f', f'D:/db-backups/naver-estate/schema_{ts}.sql', os.environ['DATABASE_URL']], check=True)
# DROP/ALTER/대량 UPDATE 동반 마이그레이션이면 '--schema-only' 대신 '--data-only' 로 한 번 더 (data_<ts>.sql)
"
```

## DB 백업 덤프 범위·첫 실전

- `--schema public` 이라 Supabase 관리 스키마(auth·storage 등) 자연 제외 — 앱 스키마만 담긴다.
- 첫 실전 = 2026-08-14 V047 사전덤프 `schema_20260814_072529.sql` (141KB, 정상).
