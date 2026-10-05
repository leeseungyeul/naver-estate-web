# 프로젝트 자산 카탈로그 (Claude 작업 진입점)

세션 109 (2026-05-05) 신설. 다음 세션 Claude가 작업 시작 시 첫 참조하는 인덱스.

> **사용법**: 새 세션 시작 시 본 파일을 먼저 grep/Read하여 PDF·라이브러리·글로벌 위치를 1분 안에 파악. 새 자산 추가 시 같은 커밋에 본 파일 갱신 (drift 방지).

---

## §1 한국어 PDF 자산 매핑 (16장)

위치: `d:/naver-estate-web/종합부동산세/`

다음 세션에서 영문 키워드(`spouse-joint`, `corp-progressive` 등)로 grep 시 권위 출처 PDF 즉시 추적 가능. **한국어 파일명 직접 grep 금지** (Windows 경로 인코딩 깨짐 위험) — 본 표의 영문 alias 사용.

| # | 한국어 파일명 | 영문 alias | 주요 사용처 (NoticeKey / 산식) | 검수 세션 |
|---|---|---|---|---|
| 1 | 지방세법(법률)(제21308호)(20260424).pdf | local-tax-law | property-tax-brackets §111의2 / §122 (cap) / 시행령 §109 1주택 차등 | 103·105·108·110 |
| 2 | 국세청 종합부동산세 법령 안내자료.pdf | comprehensive-tax-overview | property-tax 전체 분기 / 시행령 §4의2 공제할 재산세액 | 103·110 |
| 3 | 국세청 세액계산 흐름도.pdf | tax-calc-flowchart | fair-market-ratio-60 / 4단계 산식 / 산출-공제할재산세-세액공제 흐름 | 103·108·110 |
| 4 | 국세청세율.pdf | tax-rates | COMPREHENSIVE_BRACKETS_2 / _3 | 103 |
| 5 | 국세청 가산세.pdf | penalty | tax-burden-cap-150 (참고) | 103 |
| 6 | 국세청 납부기한.pdf | payment-deadline | (안내성) | 103 |
| 7 | 국세청 종합부동산세 고지 및 납부 안내.pdf | notice-and-payment | (안내성) | 103 |
| 8 | 국세청합산배제 임대주택.pdf | exclusion-rental | exclusion-applied | 103·106 |
| 9 | 국세청합산배제 사원용 주택 등.pdf | exclusion-employee | exclusion-applied | 103·106 |
| 10 | 국세청주택신축용토지 합산배제 안내.pdf | exclusion-new-build-land | (토지분, 본 계산기 미적용) | 103 |
| 11 | 국세청공동명의 1주택자 과세특례.pdf | spouse-joint-special | spouse-joint-single-house-applied | 108 |
| 12 | 국세청1세대 1주택자 판단 시 주택 수 산정 제외 특례.pdf | single-house-judgement-exclusion | special-houses-applied / special-houses-credit-prorated / special-houses-corp-blocked / special-houses-multi-house-blocked / special-houses-spouse-joint-priority (5종 라디오 출시 세션 112) | 108·112 |
| 13 | 국세청세율 적용 시 주택 수 산정 제외 특례.pdf | rate-apply-exclusion | rate-apply-exclusion-applied / rate-apply-exclusion-downgraded / rate-apply-exclusion-no-effect / rate-apply-exclusion-corp-blocked (4종 라디오 출시 세션 113 — 3주택+ → BRACKETS_2 다운판정, BRACKETS 신규 정의 불필요) | 108·112·113 |
| 14 | 국세청법인 주택분 일반 누진세율 특례.pdf | corp-progressive-special | corporation-flat-rate-applied / corporation-general-rate-applied (9 카테고리 라디오 출시 세션 111) | 106·108·111 |
| 15 | 국세청 향교 및 종교단체에 대한 과세특례.pdf | religious-special | religious-property-tax-exempt / religious-comprehensive-payer-shift / religious-filing-deadline / religious-joint-liability-cap (안내 4 카드 출시 세션 114 — 산식 무영향, 체크박스 ON 시 자동 push. 지특법 §50 + 조특법 §104조의13) | 108·114 |
| 16 | 국세청 1세대 1주택자 보유기간 계산 특례.pdf | hold-period-special | hold-period-special-eligible / hold-period-special-planned / hold-period-special-applied / hold-period-precision-warn (라디오 3상태 출시 세션 115 — 산식 변경 0, holdYears 자동 재계산) | 108·115 |

**용어 정의**: `.claude/GLOSSARY.md` 참조 (공시가/공정시장가액비율/합산배제 등 14개).

---

## §2 계산기 라이브러리 인덱스 (14개 파일)

위치: `frontend/src/lib/`

| 도구 | 핵심 파일 | BRACKETS / 진입점 | NoticeKey | 테스트 | 권위 출처 |
|---|---|---|---|---|---|
| 양도세 | `transfer-tax.ts` (3 파일: tax + branches + types) | `transfer-tax-branches.ts` | 15개 | `__tests__/transfer-tax.test.ts` | 법제처 §95② + 국세청 표 (세션 98 9출처 교차검증) |
| 취득세 | `acquisition-tax.ts` (4 파일: tax + brackets + format + types) | `acquisition-brackets.ts` | 5개 | `__tests__/acquisition-tax.test.ts` | 지방세법 §11 (세션 95 9차 plan v1.8) |
| 보유세 | `property-tax.ts` (4 파일: tax + brackets + rules + types) | `property-tax-brackets.ts` (재산세 4구간 + 종부세 2주택이하/3주택이상 7구간) | **40개** (세션 117 재실측, PDF #15 4종 + PDF #16 4종 누적) | 6 파일 110 케이스: `property-tax.test.ts` (#B5-1~#B5-4 포함) + `property-tax-brackets.test.ts` + `property-tax-cap.test.ts` + `property-tax-rules.test.ts` + `property-tax-special-houses.test.ts` (PDF #12 + 자동 합산 SH-13~15 + B-3↔5종 상호작용 B23-1~4, 19 케이스) + `property-tax-rate-apply.test.ts` (PDF #13, 8 케이스) | PDF 16장 직접 (§1 표) — 세션 103·106·108·113·114·115 |
| 중개수수료 | `brokerage.ts` (3 파일: brokerage + brackets + format) | `brokerage-brackets.ts` | 미사용 (notes 배열 없음) | `__tests__/brokerage.test.ts` | 시행규칙 별표1 (세션 94) |
| 면적 변환 | `constants.ts`의 `convertArea` (L9) | M2_TO_PYEONG=3.3058 | — | `__tests__/format.test.ts` | (수학식, 세션 82) |

### NoticeKey union 정의 위치 (직접 참조용)
- 양도세: `transfer-tax-types.ts` `TransferNoticeKey` (15개)
- 보유세: `property-tax-types.ts` `PropertyTaxNoticeKey` (40개, 세션 117 재실측 갱신) + `SpecialHousesRateApplyInput` (PDF #13 4종, 세션 113) + `HoldPeriodSpecialMode` (PDF #16 라디오 3상태, 세션 115)
- 취득세: `acquisition-types.ts` `AcquisitionNoticeKey` (5개)

---

## §3 워크플로우 자산 (.claude/)

git 추적 자산만 다른 컴퓨터/CI에서 사용 가능. 사적 파일은 본인 PC에만 존재.

| 파일 | git 추적 | 한 줄 설명 |
|---|---|---|
| `rules/web-rules.md` | ✅ | React/Next.js + FastAPI 코딩 규칙, DON'T 목록 |
| `rules/testing.md` | ✅ | 테스트 작성·실행 규칙, 구조표 (시각회귀 절차·판정 정본은 `frontend/e2e/README.md` — 세션 412 이동) |
| `rules/infra.md` | ✅ | 서버 복구 절차, 스케줄러 26잡(정적 id 기준, 세션 422 실측 — 재시작 판정용 전수 시각표는 `rules/release.md` §3-0 생성 표), 공유 인프라(mibun). 잡 상세·DB 다운 런북·운영 배경 3절은 `backend/.claude/details.md` |
| `rules/codes.md` | ✅ | 거래/매물 코드, 핵심 상수, localStorage 키 |
| `rules/planning.md` | ✅ | /plan 모드 최소 규칙, 자동 트리거 |
| `rules/domain-mapping-ssot.md` | ✅ | BE-FE 매핑 SSOT + SQL 집계 N→1 가중평균 + dialect 분기 (세션 226 신설) |
| `rules/release.md` | ✅ | PR 머지 후 backend 가동 검증 4중 cross-check (세션 232 신설, 세션 257 라이브 표시값 지표 추가) |
| `settings.json` | ✅ | 프로젝트 권한·env (공용) |
| `ASSETS.md` (본 파일) | ✅ | 자산 인덱스 (Claude 진입점) |
| `GLOSSARY.md` | ✅ | 한국어 도메인 용어집 (30+) |
| `BLOG.md` | ✅ | /blog MDX 26편 라인업 + 4단 발행 절차 |
| `STRUCTURE.md` | ✅ | 코드베이스 구조 (자동 분석, 세션 232 신설) |
| `settings.local.json` | ❌ (.gitignore) | 사적 권한 (본인 PC 한정) |
| ~~`commands/harness.md`~~ ~~`commands/guard.md`~~ | (부재) | 세션 245 정리 — 실제로는 `.claude/commands/` 폴더 자체 부재. 그동안 plan·9 GATE 작업은 `rules/planning.md` 자동 트리거 + `rules/self-check.md` (글로벌) + `superpowers:writing-plans` 스킬 + 서브에이전트 3개 병렬 패턴으로 대체되어 실가치 0. 미래에 다시 만들 필요 발견 시 본 행 정정 + 자산 등재 |
| ~~`worktrees/agent-*/`~~ ✅ 세션 112 폴더 직접 삭제 (git worktree prune + rm -rf) | (해소) | git 무인식 stale 폴더 5개 모두 정리 |

---

## §4 글로벌 자산 포인터 (수정 금지, 참조만)

본 프로젝트에서 **글로벌 자산은 0 수정**. 위치만 알아두고 필요 시 Read·Grep만. 도구 자산은 §8 매트릭스 참조.

| 자산 | 위치 | 사용 시점 |
|---|---|---|
| 글로벌 룰 | `~/.claude/CLAUDE.md` | 모든 세션 자동 로드 |
| 사적 메모리 (이 프로젝트) | `~/.claude/projects/d--naver-estate-web/memory/` | 세션 42~231 일지·feedback·project 메모 (세션 212 D: 이사 PR #35 답습) |
| 메모리 인덱스 | 위 폴더의 `MEMORY.md` | 세션 시작 시 자동 컨텍스트 주입 |
| Plan 보관소 | `~/.claude/plans/` | 세션 109 plan 30+ 개. 명명 규칙: `<번호>-<형용사>-<명사>.md` |
| 플러그인·Skill·MCP (도구) | §8 도구 매트릭스 | 작업 종류별 트리거 표 |

**금지**:
- 글로벌 파일 직접 수정 (`~/.claude/CLAUDE.md`, `~/.claude/settings.json` 등)
- 백업 파일(`.bak-*`) 손대기
- `~/.claude/settings.json` `permissions` 수정

**예외**: 사용자가 명시적으로 "글로벌 ~ 수정해" 또는 "글로벌 룰에 박아" 같이 요청 시만.

---

## §5 도메인 코드 자산

| 자산 | 위치 | 용도 |
|---|---|---|
| 시군구 코드 (5자리) | `backend/data/sigungu_codes.json` | 103줄, 17개 시도 |
| 시군구·읍면동 한국어 | `backend/shared/constants.py` `KOREA_REGIONS` | 288줄, 자동완성/검색 (수정 금지) |
| 거래 코드 (A1·B1·B2·B3) | `.claude/rules/codes.md` | 매매·전세·월세·단기임대 |
| 매물 코드 (APT·OPST 등 7종) | `.claude/rules/codes.md` | 아파트·오피스텔·재건축 등 |
| localStorage 키 (10개) | `.claude/rules/codes.md` | search_history / favorite_complexes / mb_favorites 등 |
| 핵심 상수 | `backend/shared/constants.py` (수정 금지) | M2_TO_PYEONG=3.3058 / TTL / Naver API URL |
| Naver API URL | `backend/shared/constants.py` `NAVER_LAND_BASE` | new.land.naver.com (수정 금지) |
| 종부세 BRACKETS (한국어 정의) | `frontend/src/lib/property-tax-brackets.ts` | 재산세 4 + 종부세 7 + 법인 단일세율 |
| 양도세 BRACKETS | `frontend/src/lib/transfer-tax-branches.ts` | 누진/단기/중과 분기 |
| 취득세 BRACKETS | `frontend/src/lib/acquisition-brackets.ts` | 주택·오피스텔·법인 |
| 중개수수료 BRACKETS | `frontend/src/lib/brokerage-brackets.ts` | 시행규칙 별표1 4종 요율 |

---

## §6 운영 부채 박제 (본 작업 범위 외, 다음 세션 후보)

> 이 표는 **미해소 부채만** 담는다. 해소된 항목은 §6.1 아카이브로 이동.
> 새 부채 발견 시 이 표에 한 줄 추가, 해소 시 §6.1 로 이동 (세션 190 운영 룰).

| 우선순위 | 부채 | 위치 | 영향 |
|---|---|---|---|
| 🟡 2순위 | 가치 3필드 채움률 진행 중 | `complex_metric` cron 매일 04:30 KST | PR #61 (배치 1000) 가동 확정 (세션 234 4중 cross-check 통과). ~25일 자동 완주 = 능동 작업 불필요. 세션 428 부터 매일 전량 다시 계산(최근 6개월 매매 없는 단지는 마지막 값 유지, 배치 0 = 전량). backend zombie 회피 룰 = `release.md` |

### §6.1 해소 완료 아카이브 (이력 보존 — "왜 이렇게 됐나" 추적용)

| 해소 부채 | 해소 경위 | 효과 |
|---|---|---|
| 디자인 리뉴얼 PR 4~7 진행 중 | 완료 (PR 4~7 #66~#94 전량 머지, 세션 381 정정) | spec = `docs/superpowers/specs/2026-05-20-2upekr-redesign-design.md`. PR 0~7 전량 머지 (#28~#94, 세션 188~244) — 후속 UI 작업은 spec 의 디자인 원칙 답습 |
| backend 재시작 ritual (zombie 2 세션 연속) | 세션 232 `.claude/rules/release.md` 신설 + 세션 234 PR #61 부팅 로그 `(배치 1000)` 실측 4중 cross-check 통과 | PR 머지 후 3중 cross-check (orchestrator.pid mtime + backend.log 첫 줄 시각 + crawl_jobs 최신 row) 룰화. 세션 245 본 PR 답습 = backend 변경 PR 머지 시 의무 적용 |
| worktrees 잔재 5개 | 세션 110 prune + 세션 112 폴더 rm -rf 완료 | 세션 109+110 prune 후 잔재 5개 재생성 → 세션 112 rm -rf 완전 정리. 향후 git worktree 사용 후 prune 자동화 검토 권장 |
| R21 e2e 검증 미완 | 세션 110 재실행 통과 (run 25361059023 success: Frontend CI + Frontend E2E admin 둘 다 🟢) | 부부 공동명의 #10 strict mode 정정 진짜 통과 확증 |
| complex-visual baseline | 세션 147 근본 fix (98f1f94 — applyComplexMocks 에 /api/users/me + user_profiles mock 2종 추가, 141 010cbea 우연 통과의 진짜 원인 해소) | 세션 190 실측 = main 최근 20건 CI 중 complex-visual 실패 0건 (7건 연속 success). baseline png 마지막 변경 ffe23b0(135) 이후 안정 |
| v3-A ① 재산세 1주택 차등 | 세션 110 출시 (지방세법 시행령 §109 — 3억 43% / 6억 44% / 6억 초과 45%) | 면책 박스 2건 → 1건 |
| v3-A ② 종부세 공제할 재산세액 | 세션 110 출시 (시행령 §4의2 + 대법원 2019두39796 정합 — 분자·분모 누진세율, 1주택·다주택·법인 모두 적용, 세액공제는 차감 후 기준) | **면책 박스 노란불 0건 = 보유세 도구 100% 정확** |
| 1세대 1주택 5종 특례주택 (PDF #12) | 세션 112 출시 (5종 라디오 5칸 + 카테고리별 채수+공시가 입력 + 안분 산식 + 법인·다주택·자격 미충족 시 자동 차단 + B-5 우선 양립 + Notice 5 신규) | PDF #12 효과 (1주택 자격 + 12억 공제 + 세액공제 80% 안분) 100% 반영 |
| 세율 적용 시 4종 특례주택 (PDF #13) | 세션 113 출시 (4종 라디오 4칸 + count 입력 + 3주택+ → BRACKETS_2 다운판정 산식 + 법인 자동 차단 + Notice 4 신규 + RateApplyExclusionFields 컴포넌트 분리) | BRACKETS 신규 정의 불필요 (기존 BRACKETS_2 재사용). 종부세 1주택 공제는 effectiveHousesAfterExclusion 기준 (PDF #13 무관 분리) — 세율 분기만 영향 |
| 법인 9종 누진 토글 | 세션 111 출시 (PDF #14 페이지 2 표 직접 인용 9 카테고리 라디오 — 공익법인등 ①② 분리·공공주택사업자·주택조합·정비사업시행자·민간건설임대사업자·도시개발사업시행자·사회적기업등·종중) | 면책 박스 미반영 0건 유지 = 보유세 도구 100% 정확 |
| ASSETS.md drift 자동화 | 세션 113 출시 (.claude/settings.json hooks.PreToolUse — 신규 계산기 lib *.ts Write 시 ASSETS.md §2 등재 검증 자동 BLOCK) | 단위 검증 8/8 PASS. GLOSSARY.md 자동 검증은 도메인 용어 자유 형식이라 불가 — 수동 관행 유지 |

---

## §7 Claude 작업 관행 (자산 활용 시)

1. **PDF 인용 시**: §1 매핑 표에서 영문 alias 찾아 코드 주석/Notice 본문에 박제. 한국어 파일명 직접 grep 금지 (Windows 경로 인코딩).
2. **새 자산 추가 시**: 같은 커밋에 본 파일(`ASSETS.md`) 갱신 — drift 방지.
3. **글로벌 자산은 읽기만**: `~/.claude/*` 직접 편집 금지. 사용자 명시 요청 시만 예외.
4. **계산기 신규 추가 시**: §2 표에 한 줄 추가 + 권위 출처 PDF 번호 명시.
5. **운영 부채 발견 시**: §6 표에 한 줄 추가 → 다음 세션 plan 후보.
   **부채 해소 시**: §6 표에서 그 행을 빼 §6.1 아카이브 표로 옮긴다 (`~~취소선~~` 제거 + "해소 경위" 열로). §6 에는 미해소 부채만 남겨 "다음 할 일" 표를 살아 있게 유지 — 해소 항목 누적 금지 (세션 190 사고 답습).
6. **NoticeKey 신규 추가 시**: §2 NoticeKey 카운트 갱신 (예: 19 → 20).
7. **PDF 신규 추가 시**: §1 표 한 줄 추가 + 영문 alias 제정.

---

## §8 도구 자산 매트릭스 (작업 종류 → 도구 트리거)

세션 110 (2026-05-05) 신설. **다음 세션 Claude가 "이 작업에 어떤 도구 쓰지?"를 즉시 결정**할 수 있도록 작업 종류별 도구 트리거 표.

### §8.1 MCP 서버 (2개)

| 서버 | 위치 | 트리거 (언제 호출) | 호출 방법 |
|---|---|---|---|
| `context7` | 프로젝트 `.mcp.json` | 라이브러리/SDK/CLI 공식 문서 필요 시 (Next.js·React·Supabase·FastAPI·Tailwind 등). 학습 데이터에 없는 최신 API. | `mcp__context7__resolve-library-id` → `mcp__context7__query-docs` |
| `playwright` | 글로벌 `~/.claude/settings.json` | 브라우저 자동화·실제 웹페이지 스크린샷·로컬 dev 서버 시각 검증 | mcp playwright tool calls (브라우저 launch/click/screenshot) |

**MCP vs CLI 우선 규칙** (글로벌 CLAUDE.md): 동일 기능 시 CLI 우선. 단 context7·playwright 는 CLI 동등물 없어 MCP 유지.

### §8.2 슬래시 커맨드·Skill (작업 흐름별)

| 작업 흐름 | 도구 (슬래시 커맨드 / Skill) | 출처 | 트리거 시점 |
|---|---|---|---|
| **Plan→Guard→Work→Review 워크플로우** | `rules/planning.md` 자동 트리거 + `superpowers:writing-plans` 스킬 + 서브에이전트 3개 병렬 (Explore + code-reviewer + silent-failure-hunter) | `.claude/rules/planning.md` (자동 로드) | 새 기능·5+ 파일 수정 / 사용자 "plan 짜" 또는 plan mode 진입 |
| **9 GATE 검증** | 글로벌 `rules/self-check.md` §자가 점검 1+2 (서브에이전트 3개 병렬, 부재 단정 차단, 맹점·할루시네이션 발굴) | `~/.claude/rules/self-check.md` (글로벌 자동 로드) | 코드 작성 직후·ExitPlanMode 거부 시·사용자 "맹점 찾아라" 명시 |
| **커밋 작성** | 직접 `git commit -F <메시지 파일>` (전역 multi-repo §4: fetch→보고→허락) | — (commit-commands 플러그인은 2026-10-05 전역에서 꺼짐) | 변경 완료 후 사용자 "커밋해" |
| **커밋+푸시+PR** | 직접 `git commit -F` → `git push` → `gh pr create --body-file` | — (플러그인 꺼짐) | PR 만들 때 |
| **gone 브랜치 정리** | 직접 `git fetch --prune` → `git branch -vv` 의 `: gone]` 가지를 이름 목록으로 확인 뒤 삭제 | — (플러그인 꺼짐) | 원격 삭제된 로컬 브랜치 정리 |
| **PR 코드 리뷰** | 내장 `/code-review` 스킬 또는 이 레포 리뷰 에이전트(crawl·migration·payment·tax) | Claude Code 내장 (code-review 플러그인은 꺼짐) | PR 받은 직후 |
| **PR 종합 리뷰** | `/pr-review-toolkit:review-pr` | 글로벌 플러그인 | 큰 PR 다각도 리뷰 (test·comment·silent-failure·type-design) |
| **CLAUDE.md 갱신** | 직접 Edit (진행 박제는 메모리 — planning.md) | — (claude-md-management 플러그인 꺼짐) | 갱신 트리거 해당 시 |
| **CLAUDE.md 감사** | 전역 `doc-diet` 스킬 + 직접 편집 | 글로벌 스킬 (플러그인 꺼짐) | CLAUDE.md 품질·크기 점검 요청 시 |
| **hookify 룰 작성** | `/hookify:hookify` 또는 `/hookify:list` | 글로벌 플러그인 | 자동 차단 룰 만들 때 (예: "from now on..." 요청) |
| **코드 단순화** | `/code-simplifier:code-simplifier` 또는 Agent | 글로벌 플러그인 | 코딩 완료 후 가독성 개선 |
| **로컬 웹앱 테스트** | `webapp-testing` skill | 글로벌 `~/.claude/skills/` | dev 서버 띄운 후 UI 검증 |

### §8.3 Superpowers Skills (14개, 작업 흐름 가이드)

위치: `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.x/skills/`. **Skill 도구로 호출**.

| Skill | 트리거 시점 | 효과 |
|---|---|---|
| `superpowers:using-superpowers` | 세션 시작 (자동) | Skill 사용 규칙 주입 |
| `superpowers:brainstorming` | 새 기능·UI·동작 만들 때 (구현 전) | 사용자 의도/요구/디자인 탐색 |
| `superpowers:writing-plans` | 다단계 작업 plan 작성 시 | 정형 plan 템플릿 |
| `superpowers:executing-plans` | 작성된 plan 실행 시 | 체크포인트 단계별 실행 |
| `superpowers:test-driven-development` | 기능 구현·버그픽스 시 | TDD 강제 (테스트 먼저) |
| `superpowers:systematic-debugging` | 버그·테스트 실패·예상외 동작 발견 시 | 가설 → 격리 → 검증 절차 |
| `superpowers:requesting-code-review` | 작업 완료·머지 전 | 자가 점검 + 외부 리뷰 요청 형식 |
| `superpowers:receiving-code-review` | 리뷰 피드백 받은 후 | 기술적 검증 후 반영 (맹목 동의 금지) |
| `superpowers:verification-before-completion` | "완료" 단언 직전 | 검증 명령 실행 후만 success 표기 |
| `superpowers:dispatching-parallel-agents` | 2+ 독립 작업 병렬 가능 시 | Agent 병렬 호출 패턴 |
| `superpowers:subagent-driven-development` | 큰 plan 서브에이전트 분할 실행 | 단일 세션 내 SubAgent 활용 |
| `superpowers:using-git-worktrees` | 격리 작업공간 필요 시 | worktree 신규 생성. **사용 후 `git worktree prune + rm -rf .claude/worktrees/agent-*/` 의무** (세션 112 답습) |
| `superpowers:finishing-a-development-branch` | 구현 완료·테스트 통과 후 | 머지/PR/cleanup 옵션 결정 |
| `superpowers:writing-skills` | 새 Skill 만들거나 기존 Skill 수정 시 | Skill 작성 표준 |

### §8.4 LSP (실시간 진단)

| 도구 | 출처 | 활용 |
|---|---|---|
| VS Code IDE 진단 (`<new-diagnostics>`) + `npx tsc --noEmit` | 편집기 내장 (typescript-lsp 플러그인은 2026-10-05 전역에서 꺼짐 — 꼭 필요하면 이 레포 settings 에서만 켜기) | TS 진단 |
| `ruff check .` + IDE 진단 | 프로젝트 CLI (pyright-lsp 플러그인 꺼짐) | Python 정적 검사 |

### §8.5 프로젝트 CLI / npm scripts

| 명령 | 용도 | 위치 |
|---|---|---|
| `npm run dev` | 프론트엔드 dev 서버 (port 3000=sangse / 3100=legal 점유, naver 는 8090 사용 — 세션 114 박제) | `frontend/` |
| `npm test` / `npx vitest run` | FE 단위·컴포넌트·훅 테스트 (카운트 = 루트 `CLAUDE.md` §테스트 현황 SSOT) | `frontend/` |
| `npm run test:e2e` / `npx playwright test` | E2E (카운트 = 루트 `CLAUDE.md` §테스트 현황 SSOT, --webpack 모드) | `frontend/` |
| `npx tsc --noEmit` | 타입 체크 (커밋 전 필수) | `frontend/` |
| `npm run lint` (eslint) | 린트 (커밋 전 필수) | `frontend/` |
| `python -m pytest --tb=short -q` | BE 단위·통합 (카운트 = 루트 `CLAUDE.md` §테스트 현황 SSOT) | `backend/` |
| `ruff check .` / `ruff check --fix .` | BE 린트 (커밋 전 필수) | `backend/` |
| `python -m uvicorn main:app --host 0.0.0.0 --port 8002` | BE 수동 실행 | `backend/` |
| `cloudflared tunnel run naver-estate-backend` | 집 서버 Named Tunnel 수동 | 글로벌 |

### §8.6 운영 자동화 스크립트

| 스크립트 | 위치 | 용도 |
|---|---|---|
| `scripts/startup_orchestrator.py` | 프로젝트 (수정 금지, 자동 시작 BAT가 호출) | Windows Startup 시 BE+Tunnel+Watchdog |
| `scripts/start-server.bat` | 프로젝트 | 수동 백엔드+터널 동시 실행 |
| `backend/scripts/check_crime_stats.py` | BE | 범죄통계 수집 점검 |
| `backend/scripts/diagnose_crime_keys.py` | BE | data.go.kr 쿼터 키 진단 |
| `backend/scripts/run_crime_stats.py` | BE | 범죄통계 수동 트리거 |
| `backend/scripts/test_childcare_api.py` | BE | CPMS cpmsapi030 API 점검 |

### §8.7 GitHub CLI (gh)

| 명령 | 용도 |
|---|---|
| `gh run list --branch main --limit 5` | 최근 CI 결과 |
| `gh run view <id> --json jobs --jq '.jobs[] | {name, conclusion}'` | CI job별 상세 |
| `gh run view <id> --log-failed` | 실패 로그 추출 |
| `gh pr create` | PR 생성 (HEREDOC body) |
| `gh api repos/<owner>/<repo>/pulls/<n>/comments` | PR 리뷰 코멘트 가져오기 |

### §8.8 작업 종류별 도구 픽업 가이드

| 작업 종류 | 1순위 도구 | 2순위 도구 |
|---|---|---|
| **새 기능 만들기** | `superpowers:brainstorming` → `/harness` | `superpowers:writing-plans` |
| **버그 수정** | `superpowers:systematic-debugging` | TDD skill |
| **타입·라이브러리 문서 필요** | `mcp__context7__query-docs` | WebFetch |
| **UI 시각 검증** | `webapp-testing` skill (Playwright Python) | `playwright` MCP |
| **PR 리뷰** | `/pr-review-toolkit:review-pr` | 내장 `/code-review` |
| **커밋·푸시·PR** | 직접 `git commit -F` + `gh pr create --body-file` | (없음) |
| **CLAUDE.md 갱신** | 직접 Edit | 전역 `doc-diet` 스킬 |
| **CI 결과 확인** | `gh run list` + `gh run view` | (없음) |
| **자동 차단 룰** | `/hookify:hookify` | (없음) |
| **9 GATE 검증** | 글로벌 `rules/self-check.md` 자가 점검 1+2 (서브에이전트 3개 병렬) | `superpowers:verification-before-completion` |
| **plan 작성** | `superpowers:writing-plans` | `/harness` Phase 1 |
| **계산기 산식 권위 출처** | §1 PDF 매핑 | `mcp__context7` (법령) |

---

## 검증 시나리오 (다음 세션 Claude 자가 점검용)

다음 질문에 30초 안에 본 파일 grep으로 답할 수 있어야 함:

1. "공동명의 PDF 어디?" → `grep spouse-joint .claude/ASSETS.md` → §1 #11
2. "양도세 NoticeKey 정의 어디?" → `grep "TransferNoticeKey" .claude/ASSETS.md` → §2 NoticeKey 정의 위치
3. "법인 단일세율 권위 출처?" → `grep corp-progressive .claude/ASSETS.md` → §1 #14
4. "글로벌 메모 위치?" → `grep memory .claude/ASSETS.md` → §4 사적 메모리
5. "worktrees 잔재 정리 명령?" → `grep "worktree prune" .claude/ASSETS.md` → §6
6. "라이브러리 문서 어떻게 찾지?" → `grep context7 .claude/ASSETS.md` → §8.1
7. "버그 디버깅 도구?" → `grep debugging .claude/ASSETS.md` → §8.3 systematic-debugging
8. "커밋은 어떻게?" → `grep "커밋 작성" .claude/ASSETS.md` → §8.2 (직접 `git commit -F`)
9. "CI 결과 확인 명령?" → `grep "gh run" .claude/ASSETS.md` → §8.7
10. "백엔드 수동 실행 명령?" → `grep "uvicorn" .claude/ASSETS.md` → §8.5
