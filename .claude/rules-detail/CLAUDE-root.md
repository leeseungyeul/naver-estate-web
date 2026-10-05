# CLAUDE-root.md 상세 — 상시 로드 안 함

루트 `CLAUDE.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## 자료 위치 표

| 자료 | 위치 | 용도 |
|---|---|---|
| **자산 인덱스** | `.claude/ASSETS.md` | 한국어 PDF 16장 / 계산기 라이브러리 14개 / 글로벌 자산 / 운영 부채 |
| **도메인 용어집** | `.claude/GLOSSARY.md` | 한국어 부동산 도메인 용어 30+ 개 |
| **블로그 라인업** | `.claude/BLOG.md` | /blog MDX 26편 (시세 분석 5 / 세금 6 / 도구 활용 9 / 미분양 6) + 새 글 발행 4단 절차 |
| **FE 깊이 토픽 4종** | `frontend/.claude/{hooks-and-state,ui-patterns,pages-and-mb,tools-lineup}.md` | FE 작업 시 명시 참조 (자동 로드 안 됨) — 훅·UI 패턴·페이지 흐름·도구 5종. **E2E·시각회귀 정본 = `frontend/e2e/README.md`**(세션 412 이동 — spec·baseline 수정 전 필독) |
| **BE 깊이 토픽 1종** | `backend/.claude/details.md` | BE 작업 시 명시 참조 (자동 로드 안 됨) — 실거래가·mibunyang·검증·중복 제거·**스케줄러 잡 상세 6절**(infra.md 표에서 이동, 세션 411)·**Supabase 다운 런북·스케줄러 운영 배경 3절·release 레거시/사건표**(세션 412 이동) |
| **세션 박제 메모리** | `C:\Users\user\.claude\projects\d--naver-estate-web\memory\` | 세션 43~231 일자별 정리 + 박제 룰 + 사고 회고 (세션 212 D: 이사 PR #35 답습) |
| **세션 79~112 archive** | 메모리 폴더 `sessions_79_112_archive.md` | 도구 5종 라인업 진화 + 박제 룰 진화 한 표 요약 |

## 아키텍처 그림

```
[브라우저] → [Next.js (Vercel, 2u.pe.kr)]
                ↓ API 호출 (NEXT_PUBLIC_API_URL)
           [Cloudflare Named Tunnel (api.2u.pe.kr)]
                ↓
           [FastAPI (집 서버 DESKTOP-Q5999EI, localhost:8002)]
                ↓ 실시간 크롤링 + 스케줄러
           [네이버 부동산 API] → [PostgreSQL (Supabase)]
           [국토교통부 공공데이터 API] ↗
           [에어코리아 대기질 API] ↗
           [응급의료기관 API (NEMC)] ↗
           [어린이집 API (CPMS, cpmsapi030)] ↗
           [경찰청 범죄통계 API (odcloud)] ↗
```

## 데이터 흐름 (매물·미분양·환경 수집)

### 매물 (estate)
```
검색 → 홈(/)에서 직접 (SearchExperience 공용, /search→/ 리다이렉트 — 세션 314 홈/검색 통합)
검색 → /api/live/search (네이버 API → DB upsert → 반환)
단지 클릭 → DB 즉시 표시 + 자동 매물 크롤링 (start-crawl → 10/20/30초 refetch)
필터 변경 → /api/complexes/{no}/articles (SQL WHERE) + URL 파라미터 동기화
실거래가 → /api/live/{no}/price-history/start-collect (24시간 TTL, 자동 트리거)
가까운 지하철 → /api/complexes/{no}/subway (subway_stations 전국 1,099역, 3km 최대 3역·환승 그룹핑·12h 캐시, 연 1회 수동 재적재 — 세션 367)
관리비·복도유형 → /api/complexes/{no}/kapt (K-apt 단지 매칭 월 1회 + 관리비 매일 3회(06:20·12:40·21:00), 회차당 약 200단지(K-apt 1.5초 간격) 회전 — **매월 최신 공개월로 갱신**(보유한 가장 최신 달보다 새 달만 시도, 달마다 행이 쌓이고 화면은 최신월 1건 표시)·화면에 기준월 표시, 12h 캐시, 매칭만 있으면 200+금액 null, 미매칭 404 — 세션 388)
단지 비교 → /compare?ids=no1,no2,... (useQueries 병렬 + 평당가 + 인쇄/엑셀)
엑셀(매물) → /api/articles/export (xlsxwriter)
엑셀(비교) → 클라이언트 xlsx (safeCellValue 수식 인젝션 방어)
```

### 미분양 (mibunyang)
```
미분양 조회 → /api/mb/apartments?sort_by=&keyword= (정렬+검색+중복제거)
분양 조회 → /api/mb/presale, /api/mb/competition (분양 탭: 민간분양/LH공공분양/분양결과 — 세션 314) · /api/mb/presale/officetel-rental (오피스텔·민간임대 목록, 둘 다 주소 포함 — 오피스텔 주소는 V066 세션 417)
분양 상세 → 청약 일정·평형별 공급·D-day (getMbPresaleDetail, 세션 314)
지도 뷰 → list↔map 토글 (MbClusterMap 다중마커, 접속자 GPS 위치 기준, mb_view_mode — 세션 315~316)
미분양 비교 → /mibunyang/compare?ids= (17행 우위 + 레이더13축 + 가중치 + 분양가/추이 차트)
미분양 즐겨찾기 → localStorage (최대 200개, 일괄 비교, FavSortBy)
미분양 히스토리/북마크 → localStorage (자동 저장 10개 / 수동 저장 20개)
레이더 설정 → localStorage (축 선택 + 가중치 1-5, 프리셋 3종)
```

### 환경 데이터 수집 (스케줄러 — 상세는 `.claude/rules/infra.md` 참조)
```
대기질 → 매일 02:00 (에어코리아 API → infra.air_*)
응급의료 → 매월 첫째 월 03:00 (NEMC → infra.emergency_*)
어린이집 → 매월 첫째 목 01:00 (CPMS cpmsapi030 → infra.childcare_*, mibunyang 과 키 공유라 01:00 고정 — infra.md §CPMS 키 공유)
범죄통계 → 분기별 첫째 일 04:00 (경찰청 odcloud → infra.crime_*, CSV 폴백)
공공데이터 → 토요일 05:00 (국토교통부 실거래가)
관리자 트리거 → POST /api/admin/collect/{name} (수집기 8종, 백그라운드 스레드로 시작하고 곧바로 started — 같은 수집기가 이미 돌면 409, 결과는 그 잡의 crawl_jobs 행으로 본다(세션 420). 버튼 = /admin/crawl)
```

## 항상 로드 규칙 표

| 파일 | 내용 |
|------|------|
| `web-rules.md` | React/Next.js + FastAPI 코딩 규칙, DON'T 목록 |
| `testing.md` | 테스트 작성·실행 규칙, 구조표 |
| `infra.md` | 서버 복구 절차, 스케줄러, 공유 인프라, DB 풀 |
| `codes.md` | 거래/매물유형 코드, 핵심 상수, localStorage 키 |
| `planning.md` | /plan 모드 최소 규칙 + 세션 종료 시 메모리 활용 |
| `domain-mapping-ssot.md` | BE-FE 매핑 SSOT + SQL 집계 N→1 가중평균 + dialect 분기 (세션 226 신설) |
| `derived-display-ssot.md` | 파생 표시값(시각·주기 문구)은 source(trigger)에서 자동생성, 손글씨 중복 금지 (세션 256 신설, PR #102) |
| `error-propagation.md` | FE 데이터 래퍼 에러 삼킴 금지 + 래퍼 레벨 MSW 가드 의무 (폴백 삼킴 3사고, 세션 298 신설) |
| `release.md` | PR 머지 후 backend 가동 검증 4중 cross-check (세션 230~231 zombie 답습 신설, 세션 257 라이브 표시값 지표 추가) |
| `seo-metadata.md` | og:image SVG 금지(PNG 필수)·openGraph 직접지정 시 root opengraph-image 상속 끊김·클라 본문 Suspense 함정·sitemap lastModified 고정일자 (세션 336 신설, PR #260) |
| `browser-automation-isolation.md` | 브라우저 자동화 라이브 조사 전 실계정 프로필 분리 확인 의무 — 자동화 브라우저 로그인 상태=레드 플래그, 토큰·쿠키 원문 dump 금지 (세션 351 실토큰 노출 사고, 세션 353 신설) |

## 프로젝트 자율자산 표·안전장치

| 종류 | 이름 | 발동 시점 |
|------|------|----------|
| agent | `crawl-safety-reviewer` | `backend/crawler/`·`routers/live` 변경 시 — throttle 경유·IP차단 방지(infra.md §IP차단) 검증 |
| agent | `tax-law-verifier` | `frontend/src/lib/` 계산기(`*tax*.ts`·`brokerage*.ts`) 변경 시 — 법령 cross-check + 결함 박제 테스트 감지(testing.md) |
| agent | `migration-safety-reviewer` | `backend/db/migrations/V*.sql`·`db/models.py` 변경 시 — 공용 DB(mibunyang) 영향 + prod 컬럼 선행실행 게이트 |
| agent | `payment-safety-reviewer` | `routers/payment.py`·`routers/billing.py`·`crawler/billing_charge.py` 변경 시 — 서버측 금액재산정·PortOne 대조·웹훅 서명검증·3일 중단룰·TOCTOU 원자적 전환 검증 |
| skill | `release-verify` | backend PR 머지 직후 — zombie cross-check(release.md §2, PR 성격별 3중/4중) |
| skill | `live-verify` | "재시작 반영됐나"·정적분석으로 "재시작 불필요" 단정 시 — 라이브 실측 3대 방법 |

> 안전장치(세션 309): `.claude/settings.json` deny(force-push·rm -rf·.env 읽기) + PostToolUse hook(backend .py 저장 시 ruff 경고형).
>
> 안전장치 강화(세션 311, Claude Code 신기능 자동적용): ① **`gh pr merge` 직후 zombie 자동 리마인더** — PostToolUse(Bash) hook `.claude/hooks/post-merge-zombie-reminder.js` 가 머지 커밋이 backend 변경이면 release.md §2 cross-check(PID·부팅시각·라이브 GET) 자동 상기, FE/md 전용이면 면제 안내(세션 257~311 zombie 반복 사고 구조 차단). ② **deny .env 우회 읽기 차단 확대** — head/tail/less/more/od/xxd/printf/sort/strings 의 .env 대상 추가(세션 310 heredoc 우회 답습). ③ **글로벌 `fallbackModel: [sonnet, haiku]`** (글로벌 settings, repo 밖) — Opus 과부하 시 Claude 자동 폴백(워크플로 대량 서브에이전트 rate limit 전멸 완화).

## 플랜·검증 스킬 표

> 옛 `/harness`·`/guard` 커맨드는 글로벌 스킬로 이전됨 (`.claude/commands/` 없음). 기능은 아래 스킬이 대체.

| 스킬 | 내용 |
|--------|------|
| `plan-9gate` | 9 GATE 검증 (크기/영향/순서/완전성/적정성/보안/연동/롤백/UX) — ExitPlanMode·커밋 직전 자동 |
| `ulw-safe` | Plan→Work→Review 통제 ultrawork (체크포인트+자기정지) — 큰 작업 자동 |

## 자율 발동 스킬 표

| 스킬 (글로벌) | 자동 발동 시점 | 역할 |
|---|---|---|
| `session-boot` | 새 세션 첫 작업 / "시작하자"·"이어서" | 부팅 체크리스트 (git·Actions·메모리) |
| `decision-session` | 작업 2개+ 순서 모호 / "뭐부터"·"순서" | 의존관계 실측 → 실행 순서 확정 |
| `plan-9gate` | ExitPlanMode·커밋 직전 / "검증해"·"맹점" | 9-GATE 플랜 검증 |
| `tool-discovery` | "도구 뭐 있어" / 새 외부 연동 직전 | MCP·플러그인 공식 소스 탐색 |
| `goal-setting` | 완료 조건 모호 / "알아서"·"완벽하게" | 단발 측정가능 `/goal` 한 줄 설계 |
| `loop-goal` | 여러 이슈 자율 루프 / "이슈 다 구현"·"끝까지 자율로" | DECISION_LOG·CORE/MINOR·STOP 박힌 `/goal` 루프 설계 |
| `ulw-safe` | 30분+·7파일+·풀스택·마이그 | 통제된 ultrawork (체크포인트+자기정지) |

## loop-goal 산출물

**루프 산출물 데이터 관리**: loop-goal 루프는 `docs/loop/DECISION_LOG.md` (런타임 체크포인트, .gitignore) + `reports/` (이슈 구현 보고서, git 추적) 를 만든다. `/명령어` 타이핑도 여전히 동작 (하위호환).
