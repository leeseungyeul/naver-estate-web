# codes.md 상세 — 상시 로드 안 함

`.claude/rules/codes.md` 에서 옮긴 표·예시·실측 수치·사건 경위 원문(세션 430, 글자 그대로). 규칙 문장은 핵심 파일에 남아 있고, 옮긴 자리마다 `(상세: … §제목)` 링크가 있다.

## localStorage 키 표

| 키                   | 용도                    | 제한                  |
| -------------------- | ----------------------- | --------------------- |
| `search_history`     | 최근 검색 (키워드/지역) | 최대 10개, 중복 제거  |
| `favorite_complexes` | 즐겨찾기 단지           | 무제한, 토글 방식     |
| `compare_complexes`  | 비교 대상 단지          | 최대 4개              |
| `mb_favorites`       | 미분양 즐겨찾기         | 최대 200개, 토글 방식 |
| `mb_compare`         | 미분양 비교 대상        | 최대 4개              |
| `mb_search_history`  | 미분양 검색 히스토리    | 최대 10개, 중복 제거  |
| `mb_compare_history` | 미분양 비교 히스토리    | 최대 10개, 자동 저장, ids 정렬 중복 제거 |
| `mb_compare_bookmarks` | 미분양 비교 북마크    | 최대 20개, 수동 저장, 이름 지정 가능 |
| `mb_radar_settings`  | 레이더 축 선택+가중치  | 축 13개, 가중치 1-5, 프리셋 3종 |
| `favorite_articles`  | 매물 즐겨찾기           | 무제한, 토글 방식 |
| `article_view_mode`  | 매물 카드 모양 (compact/medium/large) | 값 1개, default = medium |
| `article_page_size`  | 한 페이지당 매물 개수 (10/20/30/50) | 값 1개, default = 10 |
| `mb_view_mode`       | 미분양 탭 보기 방식 (list/map)          | 값 1개, default = list |
| `favorite_price_snapshot` | 즐겨찾기 단지 가격 변동 배지용 마지막 조회가 (complex_no→가격 맵) | 승인 중개사 전용(B2 게이트), 표시용 캐시라 유실돼도 무해 |
| `search_view_mode`   | 매물 검색 결과 보기 방식 (list/map)     | 값 1개, default = list, mb_view_mode 와 물리적으로 분리된 키(탭 간 의도치 않은 결합 방지) |
