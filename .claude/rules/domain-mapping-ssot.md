# 도메인 매핑 SSOT + SQL 집계 패턴

BE Python dict ↔ FE TypeScript 함수 짝꿍 매핑, SQL `GROUP BY` 의 N→1 합산 함정, BE 테스트 dialect 의존성 답습 규칙.

(상세: .claude/rules-detail/domain-mapping-ssot.md §근거 사건 출처)

## 룰 1 — BE-FE 매핑 dict 짝꿍 답습

### 트리거

다음 짝꿍 파일 어느 한쪽에 **매핑 dict 의 키 또는 값을 추가·변경·삭제** 할 때.

(주석·JSDoc·타입 시그니처만 변경하는 경우는 트리거 아님)

| BE | FE | 매핑 종류 |
| --- | --- | --- |
| `backend/db/price_queries.py:99` `tt_key_map` | `frontend/src/lib/trade-types.ts:17` `tradeKey()` | 거래유형 한글명 → 집계 키 |

### 답습

1. **양쪽 짝꿍 주석에 상대 파일경로:라인 명시** — 한쪽만 보고도 짝꿍이 어디 있는지 한 번에 찾을 수 있어야 한다.
2. **같은 세션에서 BE + FE + 회귀 테스트 동시 수정** — 한 쪽만 머지하면 silent confusion 이 발생한다. 회귀 테스트는 룰 2 의 시나리오 3종 답습.
3. **라인 번호 drift 점검 의무** — 파일 위·아래에 줄을 추가하면 짝꿍 주석에 박힌 라인 번호가 어긋난다. 매핑 변경 PR 마지막에 `grep "짝꿍 파일경로:" 양쪽_파일` 로 라인 번호 재확인.

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 1 짝꿍 주석 위치·확장 후보)

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 1 사건)

## 룰 2 — N→1 매핑 dict + SQL `GROUP BY` 덮어쓰기 검증 의무

### 트리거 (3 조건 AND)

1. 매핑 dict 가 **N→1 패턴** — 서로 다른 키가 같은 값을 가리킬 때 (예: `{"월세": "wolse", "단기임대": "wolse"}`).
2. SQL 이 **원본 값 기준 `GROUP BY trade_type_name`** 으로 행을 분리 반환.
3. Python 루프가 **출력 dict 키에 누적 없이 단순 대입** (`entry[key] = avg` 형태).

세 조건이 모두 참일 때만 트리거. 1대1 매핑이거나 합산 누적이 이미 있으면 트리거 아님.

### 답습

- SQL `GROUP BY` 가 같은 출력 키에 두 행 반환하면 **Python 루프 두 번째 행이 첫 번째를 덮어쓴다** — silent failure.
- **임시 누적 dict 로 가중평균 합산** — `area_wolse_accum`, `floor_wolse_accum` 같은 `dict[버킷, (count, sum)]` 으로 누적 후 가중평균 계산해 출력.
- 회귀 테스트는 **시나리오 3종** 의무 (이름 패턴은 권장, 강제 아님):
    1. **공존** (`_합산_to_X` 권장) — N개 키가 동일 출력 키로 들어올 때 카운트 합산 + 가중평균 정확.
    2. **단독** (`_X_only` 권장) — N개 중 1개만 있을 때 정상 집계.
    3. **미매핑** (`_unmapped_skipped` 권장) — 매핑 dict 에 없는 키는 카운트에 영향 0.

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 2 코드 인용)

### 현재 BE 적용 범위

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 2 현재 적용 범위)

미래에 새 N→1 매핑 dict 가 추가될 때 본 룰 트리거.

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 2 사건)

## 룰 3 — 테스트 0건 발견 시 dialect 의존성 의심 (BE 전용)

### 트리거 (3 조건 AND)

1. `backend/tests/` 에서 함수 X 의 직접 테스트가 **0건**.
2. 함수 내부에 `text("""...""")` **raw SQL**.
3. raw SQL 안에 **PostgreSQL 전용 문법** — grep 패턴: `~ '` (정규식) / `SPLIT_PART(` / `JSONB` / `ARRAY[`.

세 조건이 모두 참일 때만 트리거. ORM 쿼리이거나 SQLite 호환 raw SQL 은 자동 제외 — false positive 차단.

### 답습

- BE CI 엔진 = **SQLite** (`backend/tests/conftest.py`). PostgreSQL 전용 문법은 SQLite 에서 실행 불가 → 테스트 작성 자체가 불가능해 0건이 누적된다 (단순 누락이 아님).
- 해결책 = **dialect 분기** (`backend/db/price_queries.py:48` 답습):

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 3 dialect 분기 예시·선례)

(상세: .claude/rules-detail/domain-mapping-ssot.md §룰 3 사건)

## 부록 — Cross-link

| 연관 파일 | 관련 내용 |
| --- | --- |
| `.claude/rules/codes.md` §거래유형 코드 | A1/B1/B2/B3 원본 표 (상위 SSOT). 표 행 변경 시 본 파일 룰 1 트리거 표도 갱신 |

(상세: .claude/rules-detail/domain-mapping-ssot.md §부록 Cross-link 나머지 행)
