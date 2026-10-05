# domain-mapping-ssot.md 상세 — 상시 로드 안 함

`.claude/rules/domain-mapping-ssot.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## 근거 사건 출처

근거 사건은 모두 세션 225 (PR #57, 커밋 3461078, 2026-05-25) 의 단기임대 매물 wolse 시세 합산 silent failure 추적에서 도출.

## 룰 1 짝꿍 주석 위치·확장 후보

### 현재 짝꿍 주석 박힘 위치 (실측)

- BE `backend/db/price_queries.py:95~99`: `"단기임대 → wolse 합산 ... FE tradeKey 짝꿍 답습 ... 본 dict + frontend/src/lib/trade-types.ts:18 양쪽 답습"`
- FE `frontend/src/lib/trade-types.ts:14~15`: `"BE db/price_queries.py:99 tt_key_map 과 짝꿍 ... 새 거래유형 추가 시 본 함수 + BE tt_key_map 양쪽 답습"`

### 확장 후보 (현재 트리거 표 본행 아님, 미래 작업자 판단 근거)

- `CrawlJob.status` (`backend/db/models.py:171`) ↔ `JOB_STATUS_STYLES` (`frontend/src/lib/admin/job-status-styles.ts:38`) — 세션 223 PR #52 답습 패턴이나 양방향 짝꿍 주석 미박힘. 짝꿍 주석 추가가 본행 승격의 전제.
- `brokerage.ts` `TradeType` — FE 단독, BE 짝꿍 없음 (공인중개사법 시행규칙 계산 전용 도메인이라 BE 영향 없음).
- `mb-house-type.ts` `HOUSE_TYPE_LABELS` — FE 단독, BE serializer 짝꿍 없음 (raw 노출 방지용 라벨만).

## 룰 1 사건

### 사건

2026-05-25 세션 224~225, 단기임대 매물 모달의 월세 시세 탭이 빈 박스로 표시된 silent confusion. 원인은 BE `tt_key_map` 에 `"단기임대"` 키가 없어 집계에서 누락된 반면 FE `tradeKey()` 는 이미 `"단기임대" → "wolse"` 를 반환하고 있었다. 양쪽 비대칭이 silent 였다. PR #57 (3461078) 로 양쪽 동시 정렬.

## 룰 2 코드 인용

### 코드 인용 (`backend/db/price_queries.py:100~157`)

area 버킷 합산 핵심 패턴:

```python
area_wolse_accum: dict[float, tuple[int, int]] = {}  # (count, price_sum)
for row in area_rows:
    key = tt_key_map.get(tt)
    if key == "wolse" and bucket in area_wolse_accum:
        prev_cnt, prev_sum = area_wolse_accum[bucket]
        new_cnt = prev_cnt + cnt
        new_sum = prev_sum + avg * cnt
        area_wolse_accum[bucket] = (new_cnt, new_sum)
        entry[key] = new_sum // new_cnt if new_cnt else 0
        entry[f"{key}_count"] = new_cnt
    else:
        if key == "wolse":
            area_wolse_accum[bucket] = (cnt, avg * cnt)
        entry[key] = avg
        entry[f"{key}_count"] = cnt
```

floor 버킷 (`backend/db/price_queries.py:128~157`) 도 동일 패턴 + min/max 누적.

## 룰 2 현재 적용 범위

`get_price_stats_aggregated()` **1건 특수 사례**. 세션 225 에서 silent-failure-hunter 서브에이전트가 BE 전수 점검 (db/, routers/, services/, crawler/) 한 결과 다른 잠복 후보 0건 확정 (`get_trade_type_counts` 류는 4종 키 보존, 다른 GROUP BY 함수는 DB 가 묶어준 키를 그대로 출력 키로 사용해 충돌 없음).

## 룰 2 사건

### 사건

세션 225 Step 2, "매핑 1줄만 추가하면 충분" 가설로 BE `tt_key_map` 에 `"단기임대": "wolse"` 만 추가했더니 회귀 테스트 `wolse_count` 가 1만 나와야 할 자리에 2가 안 나왔다. SQL `GROUP BY trade_type_name` 이 월세·단기임대 두 행을 분리 반환하고 Python 루프가 `entry["wolse"]` 를 덮어쓰고 있었음. 가중평균 누적 로직 + 테스트 3 케이스 추가로 완전 해결.

## 룰 3 dialect 분기 예시·선례

    ```python
    dialect_name = db.bind.dialect.name if db.bind else ""
    if dialect_name == "postgresql":
        ...  # PostgreSQL 전용 SQL
    else:
        ...  # SQLite 우회 (빈 결과 또는 ORM 대체)
    ```

- 같은 패턴 적용 기존 함수:
    - `backend/services/upsert.py:16` `_do_upsert()` (dialect 분기 line 24, pg_insert / sqlite_insert 자동 분기)
    - `backend/services/naver_call_counter.py:41` `_record_call()` (dialect 분기 line 41)
    - `backend/routers/live/search.py:133` `_search_all_types()` (SQLite 순차 실행 분기 주석 시작)

## 룰 3 사건

### 사건

세션 225, `get_price_stats_aggregated()` 의 테스트 0건의 진짜 이유 추적 결과 = `floor_stmt` 에 PostgreSQL `~` regex 연산자 + `SPLIT_PART` 함수가 박혀 있어 SQLite 에서 실행 자체가 안 됐기 때문. dialect 분기 추가 후 `by_area` 집계 경로만 테스트로 회귀 가드, `by_floor` 는 SQLite 에서 빈 결과로 처리.

## 부록 Cross-link 나머지 행

| 연관 파일 | 관련 내용 |
| --- | --- |
| `backend/CLAUDE.md` §CI 테스트 인프라 | SQLite dialect 분기 선례 (`_search_all_types()`, `_do_upsert()`) |
| `backend/tests/test_price_queries.py` | 룰 1+2 회귀 테스트 3 케이스 실체 |
| `frontend/src/lib/trade-types.ts` | FE 짝꿍 `tradeKey()` 전체 |
| `backend/db/price_queries.py` | BE 짝꿍 `tt_key_map` + 합산 로직 전체 |
