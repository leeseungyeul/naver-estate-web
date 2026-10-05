# browser-automation-isolation.md 상세 — 상시 로드 안 함

`.claude/rules/browser-automation-isolation.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## chrome-devtools MCP 영속 프로필

chrome-devtools MCP 는 기본값으로 자체 Chrome 인스턴스 + 전용 프로필을 띄우지만, 그
프로필은 **영속(persistent)** 이다 — `%HOMEPATH%/.cache/chrome-devtools-mcp/chrome-profile*`
에 저장되고 "run 간 삭제되지 않으며 모든 인스턴스가 공유"(공식 README, 2026-08-09 확인).
즉 **과거 어느 세션에서든 한 번 로그인했으면 지금도 로그인 상태**다. `--browserUrl` /
`--wsEndpoint` 로 사용자가 쓰는 실제 크롬에 붙는 모드면 실프로필 그 자체를 공유한다.
일회용이 필요하면 `--isolated`(종료 시 자동 삭제 임시 프로필).

## 사건 (왜 이 룰?)

2026-08-07 세션 351 — 멀티탭 로그인 튕김 버그(auth-js#213)를 chrome-devtools MCP 로
라이브 반복 재현하던 중, 자동화 브라우저가 사장님의 실제 로그인 세션 쿠키를 쥐고 있어
**실 JWT 토큰 값이 조사 결과 텍스트에 그대로 노출**. 사장님이 "본인 계정이라 괜찮다"며
진행을 승인했으나, 재발방지 P0 로 박제 → 세션 353 본 룰 신설.

## Cross-link

- `.claude/skills/live-verify/SKILL.md` — 라이브 실측 진입점 (본 체크가 선행 조건)
- `~/.claude/rules/prod-key-injection-and-test-phone.md` — "실부수효과·실값 노출 방지" 자매 룰 (글로벌)
- `.claude/rules/testing.md` — E2E 계정 운용
