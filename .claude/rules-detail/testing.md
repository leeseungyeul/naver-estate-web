# testing.md 상세 — 상시 로드 안 함

`.claude/rules/testing.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## 결함 박제 사건 (세션 264·292·384)

> 사건: 세션 264 — 양도세 단기+중과 경합을 결함으로 오판(실제는 §104① 단서 의도된 max).
> 세션 292(역방향) — 취득세 "다주택 60m² 면적무관 농특 부과"(line 261)·보유세 9억초과 1주택
> SINGLE 단언(#2·#3·#CPC-2) 3건이 **실제 결함을 정답으로 박제**. 법령 확인(행안부 질의회신·
> 지방세법 §111의2) 후 테스트 정정 + 회귀 신규. PR #147·#148.
>
> 세션 384 — 법률 용어 하나를 잘못 해석해 결론이 한 번 뒤집힌 사례. 종부세 이중과세 공제
> (시행령 §4의2) 판례 원문의 "재산세 **표준세율**로 계산한 재산세 상당액"이라는 문구를,
> 처음엔 "표준세율=지자체 조례 가감 전 법정 기본세율"(조례 가감 여부와 무관, 누진 유지)로
> 해석해 "기존 코드(누진공제 차감)가 맞다"고 오판했다. 그런데 elitelaw.kr 의 **구체적 숫자
> 계산례**("④ 구간세율로 적용하지 않고(3억 초과 구간 570,000원 누진공제 더하지 않음) 표준
> 세율만 적용")를 직접 대조하자 "표준세율=누진공제를 빼지 않고 세율만 곱하는 방식"이 맞다는
> 게 드러나 결론이 뒤집혔다. 교훈: **법률 용어의 뜻은 사전적 정의나 다른 맥락(예: 지방세법
> §111③ 조례 가감의 "표준세율")으로 유추하지 말고, 그 조문이 실제로 쓰이는 구체적 숫자
> 계산례로 검증**해야 한다 — 같은 단어("표준세율")가 조문마다 다른 걸 가리킬 수 있다.
> PR #423.

## StrictMode 선례 (세션 395)

3. 선례 = `frontend/src/components/__tests__/Header.strictmode.test.tsx`(세션 395, next 16.3.4 admin E2E 회귀 근본수정 — E2E 는
   dev 서버라 StrictMode 결함이 드러났고 prod 빌드는 이중 실행이 없어 사용자 영향 0 이었다).

## fixture 사건 (세션 372)

> 사건: 세션 372 — `service_official_price.py` silent-failure 가드가 `remaining`(법정동
> 코드 리스트)을 "단지 수"라고 표시하는 단위 오류를, 기존 `seeded` fixture(단지1=법정동1)가
> 숫자를 우연히 일치시켜 61개 테스트가 다 통과하는 채로 하루 넘게 방치했다. 적대검증
> 워크플로우가 fixture 구조를 직접 읽어 이 함정을 지적, 단지 2개·법정동 1개인 새 fixture로
> `test_collect_silent_failure_guard_counts_complexes_not_ld_codes` 를 추가하고 뮤테이션
> 검증(수정 전 코드로 되돌리면 실제로 실패)까지 거쳐 PR #399 로 반영.

## 레벨별 실행 명령

```bash
# FE 전체
cd frontend && npm test

# BE 전체
cd backend && python -m pytest

# FE 특정 파일
cd frontend && npx vitest run src/lib/__tests__/format.test.ts

# BE 특정 파일/함수
cd backend && python -m pytest tests/test_queries.py
cd backend && python -m pytest tests/test_queries.py::test_search_complexes_by_name -v

# E2E (서버 실행 필요)
cd frontend && npx playwright test
cd frontend && npx playwright test --headed  # 브라우저 보면서
cd frontend && npx playwright test --ui      # 인터랙티브 모드
```

## 결과 읽기

- **Vitest**: checkmark = 통과, X = 실패 + expected/received diff
- **pytest**: . = 통과, F = 실패, s = 스킵 + traceback
- **Playwright**: PASS/FAIL + 실패 시 스크린샷 test-results/
