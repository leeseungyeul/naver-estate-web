# release.md 상세 — 상시 로드 안 함

`.claude/rules/release.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## 룰 신설 배경

세션 230~231 backend zombie 사고 2 세션 연속 발생을 git 추적 룰로 박제. 박제 근거 = 글로벌 메모리 `[[feedback-orchestrator-restart-zombie-risk]]` + `[[feedback-backend-process-zombie-grep]]` 은 git 추적 0 → 다른 컴퓨터·새 협업자 보호 불가.

## 거짓양성 차단 — prod DB 직접 실측 (세션 301)

💡 **거짓양성 차단 — prod DB 직접 실측** (세션 301): 라이브 GET 정렬결과만으론 "새 코드 실행" 인지 "옛 코드 우연히 같은 결과" 인지 구분 못 할 수 있다 (예: SQL 경로 nullif vs Python fallback `or inf` 가 둘 다 0 맨뒤). `SessionLocal` 읽기전용 스크립트로 prod PG 에 **옛 ORDER BY / 새 ORDER BY 를 같은 데이터에 직접** 던져 비교하면, 라이브 프로세스 상태와 무관하게 디스크 코드 정합성을 결판 → "디스크는 새 코드 정상, 라이브만 옛 동작 = zombie" 를 확정. 실행 = `backend/` cwd + `PYTHONPATH=.` (임시 uvicorn 금지, §5-1 답습). 선례 = `memory/scripts/session301_verify_pp_nullif.py`.

## 시각표 생성기 이력

(세션 412 에 이 생성기가 옛 손글씨 표의 **세 번째 누락** — 주 1회 07:00 `complex_detail_JGC/ABYG/OBYG` 3행 — 을 찾아냈다.)

## 4. 사건 박제 안내

세션 229~411 의 사건 12행(zombie 3연속·정적분석 오판(257)·세션 셸 직접 기동 급사(352~353)·nssm 전환(363)·AST 미확인 면제(386)·
조용한 Restart-Service 실패(396)·사전 확인 생략(397)·재시작 직전 재조회 누락(409)·파이프가 게이트 종료코드 삼킴(411))은
세션 412 에 **`backend/.claude/details.md` §release 사건 박제 표** 로 원문 그대로 옮겼다. 새 사건은 그 표에 행을 추가하고, 절차가 바뀌면 위 §3 을 고친다.

3 세션 연속 backend 재시작 누락 = 글로벌 메모리 (사적) 박제로는 부족 → 본 룰로 git 추적.

## 5-1 사건 (세션 257)

> **사건**: 2026-06-01 세션 257 — PR #102 (표시 SSOT 자동생성) 후 "재시작 불필요"를 정적 분석으로 3회 단정. 라이브 GET 으로 화면 표시가 옛값(08:30/20분/6시간) 잔존 확인 = 재시작 필요로 정정. trigger 동작은 새값이나 표시 모듈 본문이 옛 코드라 split 발생.

## Cross-link

- `.claude/rules/infra.md` §스케줄러 (APScheduler) = 27 잡 + 운영 토글 (세션 402 실측: 상세 백필 2 + 채움률 감시 1 신설로 22 → 25. 세션 422 관리비 낮 회차로 25 → 26. 세션 426 관리비 저녁 회차로 26 → 27. ⚠ 라이브 `scheduler-status` 는 33개(세션 422 관리비 낮 회차 +1 · 세션 426 저녁 회차 +1)로 보이는데, popular 3회차·complex_detail 5유형이 개별 등록돼 정적 id 수와 다른 것이 정상이다 — 두 수를 맞추려 하지 말 것)
- `.claude/rules/infra.md` §IP 차단 방지 = 네이버 호출 보호
- 글로벌 메모리 박제 = `[[feedback-orchestrator-restart-zombie-risk]]` + `[[feedback-backend-process-zombie-grep]]`
- 사건 일지 = `~/.claude/projects/d--naver-estate-web/memory/session{229,230,231}_summary.md`
