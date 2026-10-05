# 네이버 아파트·오피스텔 매물 조회 — 웹 버전

Next.js + FastAPI + Supabase 기반 웹 서비스. 실시간 네이버 부동산 크롤링.

## 진입점

새 컨텍스트 읽기 순서 = ① `.claude/rules/` 11종 상시 + `infra-scheduler.md` 1종(필요할 때 — 아래 표) → ② `.claude/ASSETS.md` · `.claude/GLOSSARY.md` · `.claude/BLOG.md` (필요 시 참조) → ③ FE/BE 깊이 토픽 5종 (FE/BE 작업 시 명시 참조) → ④ `memory/MEMORY.md` (세션 누적 박제).

(상세: .claude/rules-detail/CLAUDE-root.md §자료 위치 표)

## 비즈니스 모델

**공인중개사 B2B 구독 단독** (세션 91~92 결정 박제 + 세션 209 재확인 박제: "B2B 단독은 맞다, 단 사용자가 쓰기 편해야"). 단지 6만개 색인 = **SEO 자산 + 구독자가 보는 핵심 데이터** (B2C 확대 아님). 가치 데이터 무료 공개 + 도구 100% 정확 산정 + /pricing 7일 무료 체험.

## 디자인·UX 리뉴얼 (완료 — 세션 188~244, PR 0~7 전량 머지)

**진실의 원천**: [docs/superpowers/specs/2026-05-20-2upekr-redesign-design.md](docs/superpowers/specs/2026-05-20-2upekr-redesign-design.md) (역사 기록·디자인 원칙 참조용).

PR 0~7 전부 머지 (#28~#94). 후속 UI 작업은 spec 의 디자인 원칙을 따른다 = Claude 디자인 5색 + Pretendard 단일 + shadcn/Radix (모방 전략) + 사용자 명시 잣대 "사용자가 쓰기 쉽게"·"기능 다 만들지 말고 GitHub 가져다 쓴다" + 네이버 크롤링 IP 차단 방지.

`frontend/.claude/{ui-patterns,hooks-and-state,pages-and-mb,tools-lineup}.md` 의 UI 컴포넌트·페이지 박제는 **UI 변경 시 함께 갱신**. spec 와 drift 시 spec 우선.

## 기술 스택

- **Frontend**: Next.js 16 (App Router) + TypeScript + Tailwind CSS 4 + React Query (TanStack Query v5) + Recharts 3 + MDX
- **Backend**: FastAPI + SQLAlchemy 2.0 + curl_cffi + requests + APScheduler
- **DB**: Supabase (PostgreSQL) + Supabase Auth
- **배포**: Vercel (frontend, 2u.pe.kr) + 집 서버 (backend, Cloudflare Named Tunnel api.2u.pe.kr)

## 아키텍처

(상세: .claude/rules-detail/CLAUDE-root.md §아키텍처 그림)

**핵심**: 사전 크롤링이 아닌 **실시간 크롤링** — 사용자 검색 시 네이버 API 호출 → DB upsert → 결과 반환

## 데이터 흐름

(상세: .claude/rules-detail/CLAUDE-root.md §데이터 흐름 (매물·미분양·환경 수집))

## 주요 기능·구현 사항

> **인프라·운영**: 상세 = `.claude/rules/infra.md` §스케줄러 (APScheduler) + 서버 자동 시작 / Named Tunnel / 공유 쿼터 / NullPool / CSP·Hydration.
>
> **공인중개사 검증 (B2B 구독 모델)**: FE = `/verify` + `/admin/users` + Header 전문가 뱃지 (role=expert). BE 워크플로 상세 = `backend/.claude/details.md` §공인중개사 검증 워크플로 참조.

## 환경변수

### 필수 (3곳 동기화: Vercel + backend/.env + frontend/.env.local)
- `ADMIN_USER_IDS` — 관리자 user_id(Supabase `auth.users.id`, 쉼표 구분). BE `deps.is_admin_user`(= `role == "admin"` 또는 이 목록) + FE `src/proxy.ts`(/admin 은 이 목록만, 서버 전용 env) 가 같은 값을 쓴다. 미설정이면 BE 는 role=admin 만·FE /admin 은 전원 차단. CI e2e 는 secret `TEST_ADMIN_USER_ID` 로 주입. ⛔ 옛 `ADMIN_EMAIL` 은 세션 417 에 폐지 — **이메일로 관리자 판정 금지**(가입 안 된 주소가 목록에 들어가면 그 주소로 가입한 사람이 관리자가 된다)
- `NEXT_PUBLIC_API_URL` — 백엔드 API URL (Named Tunnel: https://api.2u.pe.kr)

### SEO (Vercel 등록 완료, 세션 388 `vercel env ls` 실측 확인)
- `NEXT_PUBLIC_SITE_URL=https://2u.pe.kr`
- `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` / `NEXT_PUBLIC_NAVER_SITE_VERIFICATION` (서치 콘솔 인증)

### 백엔드 전용 (backend/.env)
- `AIR_QUALITY_ENABLED`, `EMERGENCY_ENABLED`, `CHILDCARE_ENABLED`, `CRIME_STATS_ENABLED` — 수집 토글
- `CHILDCARE_DETAIL_API_KEY` — cpmsapi030 운영키
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` — Gmail SMTP SSL 465
- `PAYMENT_ENABLED` — 결제 기능 전역 스위치 (**코드 기본값 false = 꺼짐**, 세션 400 무료 전환). 꺼져 있으면 결제 API 7종(`/api/payment/{prepare,complete,webhook}`·`/api/payment/billing/{prepare,register,list,cancel}`)이 전부 **403**(`결제 기능이 비활성화되어 있습니다`)이고 04:50 빌링키 자동결제 잡도 미등록. 라이브 `.env` 에 항목이 없으므로 배포·재시작만으로 잠긴다(`.env` 편집 불필요). 매출 시작 시 `PAYMENT_ENABLED=true` 한 줄 추가 + 재시작으로 결제 코드 그대로 재개. 게이트 구현 = `config/payment_flags.py`, 회귀 = `tests/test_payment_disabled.py`
  - ⚠ **재개는 BE·FE 를 반드시 한 묶음으로** (세션 405 적대검증 HIGH). BE 는 집서버 `.env`+재시작, FE 는 Vercel 커밋+배포라 **배포 경로가 완전히 다르다.** BE 만 켜면 결제 API 는 열렸는데 `/terms`·`/refund`·`/privacy` 는 "지금은 무료로 운영 중입니다" 를 계속 띄운다 — **실제로는 과금되는데 화면은 안 된다고 고지**하는 상태라, 환불 분쟁 시 사업자에게 불리한 증거가 된다. 재개 체크리스트 = ①BE `.env` 에 `PAYMENT_ENABLED=true` + 재시작 ②FE `lib/locked-paths.ts` 의 `LOCKED_PATHS` 에서 `/pricing` 제거 + 헤더 메뉴·sitemap·robots 원복 ③`pricing/page.tsx:83` 등 "7일 무료 체험" 문구가 **그때 가격 정책과 맞는지** 재확인(잠긴 동안 방치돼 낡아 있다) ④라이브에서 세 문서의 배너 소멸 확인(`curl -s https://2u.pe.kr/terms | grep -c "무료로 운영 중"` = 0). 배너 판정 = `isPaidServicePaused()`(= `/pricing` 잠금 파생)

## 테스트 현황 (BE = 세션 427 직접 실측 2026-10-02 · FE = 세션 427 CI 실측 2026-10-02)

| 영역 | 도구 | 테스트 수 |
|------|------|----------|
| FE Vitest | `frontend/src/**/__tests__/` + `frontend/scripts/__tests__/` | **2332개** (세션 427 CI 실측 2026-10-02, PR #637 Frontend CI: Test Files 256). RegionSelector 는 세션 416 에 구조 수정 — 이 파일이 타임아웃으로 실패하면 **새 원인**이다 |
| FE E2E | `frontend/e2e/*.spec.ts` | **21 파일** (Playwright, --webpack 모드) · 시각회귀 baseline PNG **22장**(세는 법 = `find frontend/e2e -name "*.png" \| wc -l`). 재생성 순서·판정·함정 = `frontend/e2e/README.md` |
| BE pytest | `backend/tests/` | **2323개** (세션 427 직접 실측 `--collect-only` 2026-10-02, main a6a2a957). ⚠ `backend/` 안에서 실행이 표준 · 작업반 보고를 옮기지 말고 **매번 직접 재실측** |

> 숫자마다의 옛 값·근거 run·증감 사유(세션 396~427)는 `.claude/history/test-baseline-history.md` 로 옮겼다(세션 430). 숫자를 갱신하면 옛 값을 그 파일에 한 줄 더한다.

## 커밋 전 필수 검증

```bash
# BE 변경 시
cd backend && ruff check . && python -m pytest --tb=short -q

# FE 변경 시 — ⚠ tsc·lint·test 만으로는 CI 를 통과 못 한다. 게이트 3종을 같이 돌릴 것
cd frontend && npx tsc --noEmit && npm run lint && npm test \
  && npm run check:ad-compliance && npm run check:mdx-jsx && npm run check:job-labels \
  && npm run check:visual-guard
```

> ⚠ **게이트 3종 누락이 CI 왕복을 만든다 (세션 401 실사고)**: `src/app`·`src/components`·
> `src/content/blog` 하위 텍스트는 `check:ad-compliance` 가 광고법 위험 단어(최고·유일한·100% 등,
> `scripts/check-ad-compliance.mjs` RISKY)를 검사한다. **코드 주석도 검사 대상**이다 — 세션 401 에
> 주석에 쓴 "유일한" 한 단어로 Frontend CI 가 실패했고, 그 여파로 e2e job 이 통째로 skip 돼
> baseline 재촬영 dispatch 까지 헛돌았다. 표현을 바꿔 해결할 것 — **WHITELIST 추가는 금지**
> (내 주석 하나 때문에 법령 준수 게이트를 느슨하게 만드는 잘못된 교환).
>
> **CI 보안 게이트 (세션 339)**: CI 는 BE `pip-audit -r requirements.txt --strict`(prod 취약점 자동 차단) + FE `npm audit --omit=dev --audit-level=high`(prod high/critical 자동 차단)를 상시 실행한다. 의존성 추가·bump PR 은 이 게이트를 통과해야 머지된다. 로컬 사전 확인 = `cd frontend && npm audit --omit=dev`. ⚠ 윈도우 로컬 `pip-audit` 은 requirements.txt UTF-8 한글 주석을 cp949 로 읽어 `UnicodeDecodeError` 로 죽으니 `PYTHONUTF8=1 pip-audit ...` 로 실행(CI 리눅스는 정상). dependabot PR 재생성·secrets 처리는 메모리 `[[dependabot-secrets-gate]]` 참조.

## 규칙 & 커맨드

### 항상 로드 (`.claude/rules/`)
| 파일 | 내용 |
|------|------|
| `infra-scheduler.md` (**필요할 때만** — `paths`) | 잡별 주기·배치·토글 표·잡 이름 대조표·알림 창구 적용 현황·관찰성·data.go.kr 호출 일정 표 (세션 430 infra.md 에서 이동). `backend/crawler`·`scripts`·`routers/admin`·`services`·`tests` 등을 열면 자동 로드 — **DB 만 조회하거나 수동 실행을 정할 땐 직접 연다** |

(상세: .claude/rules-detail/CLAUDE-root.md §항상 로드 규칙 표)

### 프로젝트 자율자산 (`.claude/agents/` · `.claude/skills/` — 세션 309 신설)

repo 에 박혀 git 으로 전파되는 도메인 특화 자산. description 매칭으로 자동 발동 (글로벌 `~/.claude` 가 아니라 프로젝트 추적).

(상세: .claude/rules-detail/CLAUDE-root.md §프로젝트 자율자산 표·안전장치)

### 플랜·검증 (글로벌 스킬 — 타이핑 0 자동 발동)

(상세: .claude/rules-detail/CLAUDE-root.md §플랜·검증 스킬 표)

## 자율 발동 도구 (타이핑 0 — Claude 스스로 판단해 발동)

**진실의 원천**: `~/.claude/rules/auto-tool-usage.md` (글로벌, 자동 로드). 사용자가 `/명령어` 를 타이핑하지 않아도 Claude 가 작업 성격을 보고 아래 스킬을 자동 발동한다. 메커니즘 = 스킬 `description` 매칭 (공식 model-invocation) + UserPromptSubmit 훅 매 턴 상기.

(상세: .claude/rules-detail/CLAUDE-root.md §자율 발동 스킬 표)

**역할 분리 (충돌 방지)**: goal-setting=단발 목표 / loop-goal=여러 이슈 루프 / ulw-safe=실행 안전 엔진. 한 task 에 `/goal`·`ralph`·`ulw-safe` 중 1개만 (auto-tool-usage.md §충돌 회피).

(상세: .claude/rules-detail/CLAUDE-root.md §loop-goal 산출물)

## 양쪽 영향 체크리스트 (FE↔BE 동기화)

### FE → BE (frontend 변경 시 확인)

- [ ] 새 API 호출 추가? → `frontend/src/lib/api/` 9 모듈에 함수 추가 + 백엔드 라우터 존재 확인
- [ ] 새 타입 필드 사용? → `frontend/src/types/` + `backend/db/models.py` + `backend/routers/*serializers.py` 동기화
- [ ] 인증 필요 엔드포인트? → Authorization 헤더 전달 확인 (`session.access_token`)
- [ ] 관리자 전용? → `frontend/src/proxy.ts` 라우트 보호 확인 (Next 16: middleware → proxy)

### BE → FE (backend 변경 시 확인)

- [ ] BE 라우터 변경 시 → FE `lib/api/` 9 모듈 동기화 (새 함수·시그니처 갱신)
- [ ] serializers 변경 시 → FE `types/` 인터페이스 동기화 (필드 추가/삭제)
- [ ] `.env` 변경 시 → `.env.local` (FE) + Vercel 환경변수 동기화
- [ ] V021+ 마이그레이션 시 → FE 영향 검토 (테이블 컬럼 변경 시 타입·UI 영향)

## 세션 종료 시 마무리

**진실의 원천**: `.claude/rules/planning.md` "세션 종료 시 마무리" 섹션. 핵심 = 진행 박제는 글로벌 메모리에만 (`~/.claude/projects/.../memory/session{N}_summary.md`), CLAUDE.md 진행 박제 금지.
