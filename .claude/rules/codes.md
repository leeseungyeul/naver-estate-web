# 도메인 코드·상수·저장소

## 핵심 상수

- `M2_TO_PYEONG = 3.3058` (프론트/백엔드 동일)
- `get_dynamic_ttl()` (live 엔드포인트 시간대별 동적 캐시: 새벽 2시간 / 오전 15분 / 오후 30분 / 저녁 1시간)
- `_PRICE_COLLECT_TTL = 86400` (실거래가 수집 24시간 TTL)
- `PRICE_COLLECT_POLL_MS = 5_000` (실거래가 수집 폴링 간격 5초, 네이버 IP 차단 방지 — spec §네이버 보호 답습)
- `MAX_PRICE_COLLECT_POLLS = 36` (폴링 최대 36회 × 5초 = 3분 타임아웃 유지)

## 크롤 지표 컬럼 (진단 시 의미 구분)

- `complexes.last_crawled_at` — **매물 크롤 시각** 지표. 단지 상세 수집 여부와 무관 (2026-04-13 SQL 일괄 UPDATE 로 허수 다수 — `infra.md` IP 차단 방지 사건 참조).
- `complexes.detail_crawled_at` — **단지 상세 수집** 지표. 단지 상세 진단·backfill 우선순위는 이 컬럼 기준.
- `articles.detail_crawled` — 매물 상세 크롤 완료 여부 (bool).
- `articles.detail_fail_count` — 상세 API 가 그 매물에 **매물 단위 오류**(error 가 dict 이고 code 가 `errorCode.NotExistInformation` 이 아님)를 연속으로 답한 횟수 (V056, 세션 395). `_DETAIL_FAIL_CAP`(6 ≈ 30분 주기 × 6 = 3시간) 이상이면 상세 보강 선정 쿼리에서 제외돼 무한 재시도가 멈춘다 — **is_active 는 불변**("시도 중단"이지 "매물 비활성화"가 아니다). 시스템성 transient(error 가 문자열: 401/403/429/5xx/네트워크)는 세지 않으며, **배치(≥20)가 전수 매물오류면 그 회차는 카운트 보류**(네이버 앱 레벨 소프트 차단 오탐 방지). **일일 정비 잡(정기 VACUUM 유지보수(자료 보관함 정리), 매일 03:50)이 상한 도달 매물의 카운터를 CAP-1(5)로 되돌려 하루 1회 재시도 자격을 준다** — 네이버 쪽 오류가 풀리면 자동 복귀(세션 395 사후검증, 그 전엔 수동 SQL 이 유일 탈출구라 영구 방치 사각이었다). 수동 복구 = `UPDATE articles SET detail_fail_count = 0 WHERE article_no = '...';` 상수 정의는 `shared/constants.py DETAIL_FAIL_CAP`(세션 396 — 배치와 **온디맨드 상세 워커**가 같은 상한을 보며, 온디맨드 선정 쿼리도 상한 매물을 제외한다. 온디맨드는 카운터를 올리지 않아 정비 잡과 경합 0).

## 거래유형 코드

| 코드 | 이름     | 설명                   |
| ---- | -------- | ---------------------- |
| A1   | 매매     | 매매 거래              |
| B1   | 전세     | 전세 거래              |
| B2   | 월세     | 월세 (보증금/월세)     |
| B3   | 단기임대 | 단기임대 (보증금/월세) |

> 매핑·집계 SSOT = `.claude/rules/domain-mapping-ssot.md` 룰 1. 표 행 변경 시 양쪽 답습.

## 매물유형 코드

| 코드 | 이름           | 설명            |
| ---- | -------------- | --------------- |
| APT  | 아파트         | 일반 아파트     |
| ABYG | 아파트분양권   | 아파트 분양권   |
| JGC  | 재건축         | 재건축 단지     |
| PRE  | 분양권         | 분양권 (레거시) |
| OPST | 오피스텔       | 오피스텔        |
| OBYG | 오피스텔분양권 | 오피스텔 분양권 |
| RDV  | 재개발         | 재개발 단지     |

## 클라이언트 저장소 (localStorage)

(상세: .claude/rules-detail/codes.md §localStorage 키 표)
