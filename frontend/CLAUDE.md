# 네이버 아파트 매물 조회 웹

> Next.js 16 (App Router) + TypeScript + Tailwind CSS 4 + React Query + Supabase Auth + FastAPI Backend

## 기술 스택

- **프론트엔드**: Next.js 16.1.6, React 19, TypeScript 5, Tailwind CSS 4
- **서버 상태 관리**: React Query (TanStack Query v5) — 캐싱, 중복 제거, 폴링
- **클라이언트 저장소**: localStorage (검색 히스토리, 즐겨찾기, 비교 목록, 미분양 즐겨찾기/비교)
- **지도**: Naver Maps v3 SDK (CDN, vanilla JS + useRef)
- **인증**: Supabase SSR (쿠키 기반 JWT)
- **차트**: Recharts 3 (dynamic import)
- **테스트**: Vitest + @testing-library/react + MSW

## 디렉토리 구조 (2026-05-25 실측, 세션 232)

```
frontend/src/
├── app/           # Next.js App Router (31 페이지 = page.tsx 실측, mibunyang/* + tools/* 5종 + admin/* + blog/* + search/favorites 매물 즐겨찾기 포함)
├── components/    # 재사용 컴포넌트 (mb/47 — 세션 314~319 분양탭·지도뷰·인프라 누적 / admin/21 + ui/13 + complex/7 + article/7 + filter/4 + search/2 + blog/2 + 루트 45, `__tests__/` 제외 — 루트에 ArticleFavoritesTab 등 누적)
├── hooks/         # 커스텀 훅 (21개, useLocalStorageList + useLocalStorageFavorites 제네릭 훅 포함)
├── lib/           # 47개 (최상위 37 + api/ 9 모듈 + admin/ 1, `__tests__/` 제외 — storage/format/query-keys 별도 폴더 아니라 최상위 .ts 통합)
├── types/         # TypeScript 인터페이스 (estate + Mb* 10개 + naver-maps.d.ts)
├── content/blog/  # MDX 26편 (.claude/BLOG.md SSOT 참조)
└── proxy.ts       # Supabase 세션 + 관리자 라우트 보호 (Next 16: middleware → proxy)
```

## 토픽 인덱스 (FE 깊이 자료, 명시 참조 — 자동 로드 안 됨)

| 토픽 파일 | 내용 |
|---|---|
| `frontend/.claude/hooks-and-state.md` | 커스텀 훅 21표 + FilterBar 구조 |
| `frontend/.claude/ui-patterns.md` | UI 패턴 8 하위 (FilterBar / 뱃지 / 차트 / RegionSelector / 비교 / 레이더 / 히스토리·북마크 / 즐겨찾기) |
| `frontend/.claude/pages-and-mb.md` | 페이지별 데이터 흐름 28 페이지 + 미분양 컴포넌트 + URL 상태 관리 |
| `frontend/.claude/tools-lineup.md` | /tools 도구 5종 라인업 + 매물 상세 모달 + 모바일 반응형 + 코드 구조 |
| `frontend/e2e/README.md` | **E2E·시각회귀 정본** — project 구조·로컬 실행·baseline 재생성 7단계·촬영 전 대기 조건 두 갈래·헤더 전용 스냅샷·`check:visual-guard` (세션 412 에 `.claude/rules/testing.md` 에서 원문 이동 — 자동 로드 아님. **`e2e/*.spec.ts`·baseline PNG 를 고치기 전에 반드시 읽는다**) |

## Critical Rules

### 1. 인증 패턴
- 항상 `createClient()` from `@/lib/supabase` 사용 (`createBrowserClient` 직접 호출 금지)
- 보호된 API 호출 시 `session.access_token`을 Authorization 헤더로 전달
- proxy.ts에서 `/admin/*` 경로 보호 (role 체크) — Next 16 middleware 명칭 변경

### 2. API 호출 패턴 (React Query)
- 모든 데이터 페칭은 `useQuery`/`useMutation` + `api.ts` 함수 조합
- `api.ts`의 `fetchApi()` 래퍼: 타임아웃(15초/120초), 401 자동 로그아웃, Supabase 폴백 내장
- React Query가 요청 중복 제거 + 캐싱 + 자동 재시도 담당
- `queryKeys` (`lib/query-keys.ts`): 모든 쿼리 키 팩토리 (admin 키에 token 미포함)
- `Providers.tsx`: QueryClientProvider + 로그아웃 시 `queryClient.clear()`
- 폴링: `refetchInterval` 옵션 사용 (크롤 상태 3초, 매물 목록 8초, 가격 수집 5초 — 네이버 IP 차단 방지, spec §네이버 보호)

### 3. HTML 유효성
- `<table>` 내부에 `<Link>`(`<a>`) 래퍼 사용 금지 (hydration 에러)
- 테이블 행 클릭: `<tr onClick={router.push()}>` 패턴 사용
- 모든 모달: focus trap + ESC 키 닫기 필수

### 4. 컴포넌트 메모이제이션
- `ArticleTable`, `ComplexRow`: `memo()` 적용
- `FilterBar`: `memo()` + useReducer, debounce 500ms (입력), immediate (셀렉트/체크박스)
- `PriceHistoryChart`: `dynamic(() => import(...), { ssr: false })` 동적 임포트

### 5. 관리자 화면 공통 래퍼
- `/admin` 영역에 새 카드형 UI (헤더 + 본문 구조) 추가 시 **반드시 `AdminCard` 컴포넌트 사용**
- Props: `title` (string, required), `children` (ReactNode), `action?` (ReactNode, 헤더 우측 슬롯)
- 외부 여백은 래퍼 div 로 처리 (className prop 도입 금지) — 예: `<div className="mt-6"><AdminCard ...>...</AdminCard></div>`
- 제외 케이스: 타이틀 없는 stat 박스 grid(StatsCards 패턴) 또는 편집모드 분기가 복잡한 카드(settings/page 패턴) 는 AdminCard 부적합. 판단은 `<h3>` 헤더가 자연스러운지 기준

### 6. 타입 안전성
- 프론트 타입(`types/estate.ts`/`analytics.ts`/`progress.ts`/`mibunyang.ts`, `index.ts` 는 barrel) ↔ 백엔드 모델(`db/models.py`) 동기화 유지
- 새 필드 추가 시 양쪽 모두 업데이트 필수
- optional (`?`) 필드에 대해 `??` (nullish coalescing) 사용 (`||` 금지)

### 7. localStorage 패턴
- SSR에서 접근 불가 → 반드시 `"use client"` + `useEffect` 내부에서 읽기
- `lib/storage.ts` 래퍼 사용 (try/catch로 에러 방어)
- 브라우저별 독립 (기기 간 동기화 없음)
- 키 목록 = `.claude/rules/codes.md` §클라이언트 저장소 참조 (12개 키 SSOT)

> **양쪽 영향 체크리스트** (FE↔BE 동기화 의무) = 루트 `CLAUDE.md` §양쪽 영향 체크리스트 참조.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
