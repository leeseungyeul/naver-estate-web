# 아파트 실거래·호가 분석 화면 Implementation Plan

> **For Hermes:** 이 문서는 실행 전 계획이다. 사용자 검토 전 Orca worker, 크롤러, DB 변경, 배포, 모델 호출을 시작하지 않는다. 실행 시 Orca version-matched `orca skills get orchestration --full`을 다시 읽고 Task별 검증 계약을 적용한다.

**Goal:** 호스트 PC 브라우저에서 단지명·주소·희망 평형·최근 N개월을 입력해 정확한 단지/가장 가까운 면적을 확인하고, 같은 단지·면적·매매 유형의 실거래와 네이버 현재 호가 및 *실제로 보유한* 호가 이력을 출처와 기준일을 분리해 시각화한다.

**Architecture:** 기존 Next.js 16 / FastAPI / Supabase 데이터 모델과 검색·수집 경로를 재사용한다. 신규 분석 API는 단지 식별·면적 매칭·두 데이터 계열 집계를 독립 처리해 명시적 provenance와 결측을 반환한다. UI는 기존 인증/React Query/Recharts 패턴을 따른다. 운영 DB 및 기존 크롤러의 무분별한 재수집을 막는다.

**Tech Stack:** Next.js 16 App Router, React Query, Recharts, FastAPI, SQLAlchemy, 기존 네이버 크롤러/공공 실거래 DB, Vitest, pytest, Playwright, Orca Run/Task/Dispatch.

---

## 0. 읽기 전용 실측과 주의사항

- 2026-09-29 `main` HEAD `9391bab7`; 기존 미커밋 변경 `frontend/CLAUDE.md` 존재. 해당 변경을 건드리거나 덮어쓰지 않는다.
- FE `:3100`와 BE `:8002`는 서버에서 LISTEN, localhost HTTP health 200. 현재 UFW에서 두 포트의 Windows Tailscale 접근 허용 규칙은 보이지 않는다. `frontend/.env.local`의 `NEXT_PUBLIC_API_URL`은 `http://100.93.169.113:8002`; `backend/.env`의 `FRONTEND_URL`은 `http://localhost:3000`으로 관찰했다. **Windows 브라우저 직접 호출에는 네트워크 허용·CORS 확인이 선행**. CORS OPTIONS 실측은 승인 게이트가 차단했으므로 반복 금지, 미검증으로 표시.
- `backend/routers/live/search.py`는 네이버 검색→upsert/DB 폴백, `backend/routers/complexes.py`는 단지 면적·시세 API. `backend/routers/live/price.py`의 수집은 승인 중개사/관리자 권한, 하루 쿼터, 24h TTL, 동시성 제한을 적용. 신규 분석에서 이 제한을 우회하지 않는다.
- `backend/crawler/service_price.py`는 네이버 주별 시세와 `/prices/real` 월별 집계 실거래를 같은 `complex_price_history`에 upsert한다. 이 테이블에는 **source 구분 필드가 없다**. 기본 areaNo의 `/prices/real` 자료를 선택 평형의 실거래로 주장하면 안 된다. `backend/db/mb_models.py:163`의 `trades`는 공공 실거래이지만 `complex_no`가 없으므로 단지명/지역/면적 매칭의 오연결 위험이 있다.
- `articles`는 현재 네이버 호가(`numeric_price`, `area2_m2`, `is_active`, `last_seen_at`), `article_price_history`는 개별 매물 가격 *변경* 이력이다. 이것만으로 월별 전체 매물 호가 분포를 복원할 수 없다. 결측월을 0이나 보간값으로 채우지 않는다.
- `frontend/src/components/complex/PriceChartSection.tsx`는 면적 선택과 기존 이력 차트가 있으나 N개월 입력·호가 대비/출처 분리 기능은 없다. `frontend/src/components/complex/ComplexDashboard.tsx`에 기존 실거래 섹션이 있어 중복 UI를 피해야 한다.
- 상세 분석은 기존 B2B `get_approved_user` 게이트를 유지. 공개 페이지로 신규 데이터 권한을 넓히지 않는다. 서비스의 외부 배포(Vercel/Cloudflare)와 DB 마이그레이션은 이번 시험 범위 밖.

## 1. 기능 계약(구현 전 합의·테스트)

1. **검색:** 단지명과 주소를 각각 입력(주소는 선택/보조 필터가 기본안). `/api/live/search` 또는 DB 검색 후보에 단지명·도로명/지번·지역을 표시하고 사용자가 `complex_no`를 명시 선택. 동명이단지 자동 1순위 확정 금지. 검색의 `source=db_fallback`이면 저장 데이터임을 표시.
2. **면적:** 사용자가 `평` 또는 `전용㎡` 단위를 선택해 수치 입력. `complex_pyeong_details.exclusive_area`를 파싱해 가장 가까운 전용면적을 선택하고 선택된 **실제 면적㎡·평형명·areaNo·입력 대비 차이**를 보여준다. 입력이 공급면적이라면 별도 공급면적 기준으로만 비교(혼합 금지). 큰 차이면 확인을 요구하는 임계값은 실행 전 확정; 잠정 후보 `max(3㎡, 입력 면적의 5%)`. 면적 메타가 없으면 무조건 다른 타입으로 대체하지 않고 미확정 표시.
3. **기간:** N은 정수(기본 12개월, 예시 상한 60개월 제안; 확정 필요). 달력월 기준 시작/끝 경계, 시간대(Asia/Seoul), 취소 거래 제외, 월별 표본 0건 표시를 명시. 조회 기간이 소스 보유 기간보다 길면 불완전 범위를 고지.
4. **실거래:** 매매만 먼저 지원. 공공 `trades`의 후보 연결이 단지명+지역+전용면적만으로 유일하지 않으면 *검증 대기* 처리; Naver `/prices/real`은 areaNo가 결과에 실제 명시·검증된 경우에만 면적별 집계로 사용. 두 출처를 합치거나 출처 없는 `complex_price_history`를 실거래라 재명명하지 않는다. 데이터 확보 불가 시 정확히 '확인 가능한 실거래 없음'.
5. **호가:** 네이버 `articles`의 활성 매매 매물 중 해당 단지·확인된 전용면적 타입만 사용. 현재 호가 분포(건수·중앙값·최저/최고·갱신시각)는 제공 가능. n개월 호가 추이는 *관측시점별 동일 조건의 스냅샷*이 존재하는 구간에서만 계산. `article_price_history`로 동일 매물 가격 변경 사례를 보여줄 수 있지만 전체 월별 호가를 대체하지 않음. 스냅샷이 없다면 신규 수집/마이그레이션은 별도 게이트, 현재 추이는 '기록 없음'.
6. **변동률:** 동일 출처·동일 타입·동일 통계량의 양 끝 관측값이 있을 때 `(마지막-첫값)/첫값×100`; 첫값 0/결측·표본 부족이면 계산 불가. 실거래는 월별 중앙값(거래 건수 병기), 호가는 관측일별/월별 중앙값(매물 건수 병기)을 각각 별도 선/축 또는 카드로 표시. 실거래-현재 호가 괴리율은 동기간 자료가 있을 때만 *참고용*이며 거래 성사 가격처럼 표현하지 않음.
7. **보조 정보:** 선택 타입·면적 차이, 실제 거래 표본 수, 활성 호가 표본 수, 최신 관측일/수집상태, 데이터 출처/빈 구간, 취소 거래 여부, 중복매물 정리 규칙. 평균·중앙값 등은 단위 '만원'을 명시.

## 2. Orca 멀티 에이전트 배치 및 DAG

Coordinator는 **Hermes + Orca Run ledger**이며 소스 직접 수정하지 않는다. `orca skills get orchestration --full`을 현재 버전에서 재로딩하고 Run objective·Task 의존성·각 Dispatch의 완료조건을 기록한다. 사용자 Windows 클라이언트의 Manual 권한은 사용자 완료 보고 기준이며, 실제 worker 시작 전 *해당 클라이언트의 effective launch*에서 bypass 인자가 없는지 재확인한다. 모델 full ID·비용/쿼터 pin은 임의 선택하지 않는다.

| Wave/Task | Agent·권한 | Worktree/산출물 | 선행 | 완료 게이트 |
|---|---|---|---|---|
| A1 데이터 감사 | Claude Code **읽기 전용**(`Read,Grep,Glob`만; 무제한 Bash 금지) | 별도 자식 worktree; 실거래 소스 provenance/면적 키/호가 시계열 가능 구간 표 | 없음 | 실데이터 경로·표본·불가 케이스 증거; 원본 변경 0건 사전차단 |
| A2 API/UX 계약 감사 | Codex **읽기 전용**(sandbox read-only, approval 제한) | 별도 자식 worktree; API 스키마·인증·브라우저 요청 흐름·UI 접근성 계약 | 없음; A1과 병렬 | endpoint·타입·에러/빈상태 계약 + 테스트 목록 |
| G0 결정 게이트 | Hermes/사용자 | 데이터 소스·면적 임계·N 상한·모델/비용·배포 범위 pin | A1+A2 | 증거가 부족한 항목은 `<PIN-보류: 사유>`로 남기고 쓰기 worker 정지 |
| B 백엔드 구현 | Claude Code 또는 Codex 중 **한 명만 writer**, 최소 권한 | 전용 child worktree; 읽기 전용 API/집계·테스트 | G0 | mock/SQLite 단위·통합 테스트, 인증·소스 분리·빈 구간 검증, 기존 테스트 |
| C 프런트 구현 | 반대편 구현 agent **한 명만 writer** | 별도 child worktree; 페이지/컴포넌트/타입·Vitest | B의 계약/응답 fixture 확정(코드 작업은 독립 worktree에서 병렬 가능) | 동일 계약 fixture로 테스트, 모바일·데스크톱 상태 확인 |
| D 독립 리뷰 | A단계와 다른 모델/agent의 read-only reviewer (예: Antigravity 인증 확인됨, 모델·비용 pin 후 선택) | review 전용 child worktree, 소스 쓰기 없음 | B+C | 출처 혼합/면적 오매칭/CORS/권한/기존 미커밋 파일 침범 검토 |
| E 통합·브라우저 검증 | Hermes + 단일 integrator | 승인한 diff만 통합, clean 테스트 브랜치 | D 통과 | FE+BE 회귀, Windows Tailscale 브라우저에서 실주소 접속, 빈/성공/오류 스크린샷 |

- 모든 Task는 Orca `run-create → task-create(의존성) → worker-start → worker_done(taskId+dispatchId)`로 추적. 질문은 `ask`, 장시간은 heartbeat, 완료 후 `worker-read` 검수·release. 재시도는 새 Dispatch로, 오래된 worker의 완료가 현재 Task를 덮지 못하게 한다.
- 피드백: builder↔reviewer는 coordinator 경유로 한 방향당 최대 **3회**. 초안은 횟수 제외, 메시지는 `feedback 1/3` 식으로 counter 기록. 같은 쟁점 2회 반복/3회 소진 시 decision gate로 승격하고 무한 루프 금지.
- 역할별 full model ID·effort·비용 상한은 실행 전 공급자 실측으로 고정. Gemini CLI 개인 계정 로그인은 공급자가 거부했으므로 worker 후보에서 제외. Antigravity의 `agy models` 성공은 인증/목록만 입증하며 실제 모델 비용·성능은 입증하지 않는다. Orca의 Manual은 대화 승인 UI일 뿐 읽기 전용 보증이 아니므로 reviewer의 쓰기 도구를 launch 전 사전 차단.
- 시작 전에 `git status`의 기존 `frontend/CLAUDE.md` 수정 스냅샷을 확인·보존. 각 worker는 원본 main checkout에 직접 쓰지 않고 새 worktree만. 운영 DB·네이버 실호출·배포·방화벽 변경은 G0 별도 범위 판단 후에만.

## 3. 실행용 소단계(승인 후)

### Task 1: 계약 고정 및 실패 테스트
**Files:** 신규 `backend/tests/test_apartment_analysis.py`, `frontend/src/lib/__tests__/apartment-analysis.test.ts` (정확한 위치는 기존 테스트 패턴 확인 후 확정). 기존 `backend/routers/live/search.py`, `backend/db/models.py`, `frontend/src/types/estate.ts` 읽기.
- 검색 동명이단지/주소 불일치, ㎡↔평 선택, 정확 타입·근접 타입·원거리 타입, 기간 경계/취소 거래, 소스 미확정, 빈 호가·빈 실거래, 첫값 0 케이스 테스트를 먼저 실패시킨다.
- 실거래·호가 구분과 프로비넌스 포함 API 응답 fixture를 FE/BE 공통으로 확정한다.

### Task 2: 백엔드 읽기 전용 분석 API
**Files (후보):** 신규 `backend/services/apartment_analysis.py`, `backend/routers/apartment_analysis.py`, 등록 `backend/main.py`, 테스트 `backend/tests/test_apartment_analysis.py`. 기존 `backend/db/mb_models.py`, `backend/db/models.py`, `backend/db/price_queries.py`는 가능한 읽기만.
- `complex_no`, `area_no`, `months`, `trade_type=A1`을 검증한 뒤 단지/면적/가격 출처별 집계를 반환한다. SQL은 매개변수 바인딩, DB 조회는 read-only; 미확정 매칭을 자동 JOIN하지 않는다.
- 네이버 현재 호가는 기존 적재 `articles`에서 조회; 신규 크롤은 기존 `start-crawl`의 권한·TTL·동시성 경로를 재사용할 때만 별도 승인한다.
- 개별 변경 이력과 집계 스냅샷을 구분한다. 스키마 변경이 필요해지면 **여기서 중지**하고 별도 설계/승인을 요청한다.

### Task 3: 프런트 분석 화면
**Files (후보):** 신규 `frontend/src/app/tools/apartment-trends/page.tsx`, `frontend/src/components/apartment-analysis/{AnalysisForm,AreaMatch,PriceTrendChart,SourceStatus}.tsx`, `frontend/src/lib/api/analytics.ts`, `frontend/src/types/estate.ts`, `frontend/src/lib/query-keys.ts` 및 대응 `__tests__`. 기존 `frontend/src/components/complex/PriceChartSection.tsx`를 읽고 중복 기능/URL 상태 연동 검토.
- 단지 검색 후보를 주소와 함께 표시→명시 선택→가장 가까운 타입 확인→N개월 조회. 로딩/데이터없음/권한없음/네이버 실패/DB 폴백/부분 수집 상태를 구분.
- 차트/표의 실거래·호가 출처, 표본수, 날짜·만원 단위, 변동률 산식 툴팁. 모바일 대응·키보드/스크린리더 접근성.
- 기존 `frontend/.claude/ui-patterns.md`, `frontend/.claude/pages-and-mb.md` 규약 확인. `frontend/CLAUDE.md`의 사용자 미커밋 변경은 건드리지 않는다.

### Task 4: Windows 브라우저 검증 및 통합
**Files:** `frontend/e2e/README.md` 읽은 후, 필요한 경우 `frontend/e2e/apartment-trends.spec.ts` 추가; 시각 기준선 변경은 기존 가이드 및 별도 검토 후.
- `backend/.venv/bin/python -m pytest backend/tests/test_apartment_analysis.py -q`는 repo의 import 환경에 따라 `backend/` cwd에서 `./.venv/bin/python -m pytest tests/test_apartment_analysis.py -q`로 실행; FE `npm test -- --run ...`가 아니라 package script 규격에 맞춰 `npm test -- src/...`로 대상 실행 후 전체 `npm test`, `npm run lint`, `npm run build`.
- 프런트·백엔드의 3100/8002 포트가 Windows 브라우저에서 실제 접근 가능한지, Tailscale 특정 PC만 허용한 방화벽/정확한 CORS origin이 필요한지 **별도 승인 후** 검증. 차단된 OPTIONS 요청을 재시도하지 않는다. 가능한 경우 같은 origin 프록시로 API 직접 포트 노출을 줄이는 방안 우선 비교.
- Playwright/실브라우저에서 `http://100.93.169.113:3100/tools/apartment-trends`에 접속해 검색→단지 선택→면적 확인→기간 변경→결과/오류/빈 상태를 확인. 인증 필요 시 사용자가 직접 로그인. 실제 네이버 데이터가 막히면 mock 성공과 실데이터 접근성은 따로 보고.

## 4. 위험·결정 필요 항목

1. **실거래 출처 선택:** `trades`는 complex_no가 없고 `/prices/real`은 기본 areaNo만 수집. 정확한 단지·면적 연결을 입증할 때까지 'N개월 해당 타입 실거래'를 보장하지 않는다. G0에서 검증된 소스를 선택하거나 미지원 표시.
2. **과거 호가의 정의:** 현재 매물 표와 가격변경 이력만으로 월별 전체 호가 중위값을 소급할 수 없다. 관측 스냅샷 신규 적재는 마이그레이션/크롤 빈도/보관정책이 필요한 별도 확장 단계.
3. **운영 보호:** 모델/계정 비용, 네이버 차단, 공공 API 쿼터, 승인 중개사 권한, Supabase 프로덕션 쓰기, 배포는 자동 허용하지 않는다. 실데이터 테스트는 사전 범위 결정.
4. **접속성:** 현재 FE/BE localhost health만 확인; PC에서 3100/8002 접근은 미검증. CORS preflight 조회는 승인 게이트가 차단했으므로 그 결과를 추측하지 않는다.
5. **모델 pin:** Orca `--model`은 agent별 실제 slug가 달라 실측 필요. Claude/ Codex/Antigravity 역할별 ID·사용량 한도는 `<PIN-보류: 사용자 비용/모델 기준 미확정>`. `--dangerously-skip-permissions`, `--yolo`, 무제한 Bash 금지.

## 5. 완료 조건 (DoD)

- [ ] 동명이단지/주소 후보 중 사용자가 단지를 명시 선택한다.
- [ ] 입력 평형과 선택된 실제 전용(또는 공급) 면적 및 차이가 표시되고 먼 타입은 경고한다.
- [ ] N개월 정확한 범위·출처·단위가 명시되고 실거래와 네이버 호가가 혼합되지 않는다.
- [ ] 거래 건수/활성 매물 건수/관측일·결측/수집 오류가 표시되며 변동률은 비교 가능한 관측값에서만 계산된다.
- [ ] 회귀 테스트·인증/권한 테스트·독립 리뷰 통과, 기존 `frontend/CLAUDE.md` 수정 보존.
- [ ] Windows 호스트 브라우저에서 실제 URL 접속 및 UI 흐름 확인(운영 배포와 별개).
- [ ] Orca 각 Dispatch ID, worker_done, 검증 명령/exit code, 비용(실호출 시) 기록. 미충족은 미충족으로 보고.
