"""가격 이력 / 통계 / 추이 쿼리"""

from typing import Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from db.models import (
    Article,
    ArticlePriceHistory,
    ComplexOfficialPrice,
    ComplexPriceHistory,
    ComplexTradeRaw,
    KaptComplexMap,
    KaptManagementCost,
)


def get_article_price_history(
    db: Session, article_no: str, limit: int = 50
) -> list[ArticlePriceHistory]:
    """매물의 가격 변동 이력 조회"""
    stmt = (
        select(ArticlePriceHistory)
        .where(ArticlePriceHistory.article_no == article_no)
        .order_by(ArticlePriceHistory.recorded_at.desc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()



def get_price_stats_aggregated(db: Session, complex_no: str) -> dict:
    """단지 매물 가격 통계 — SQL 집계 (면적 5m² 버킷 + 층수 3티어)"""
    AREA_BUCKET = 5

    area_stmt = text("""
        SELECT
            ROUND(area2_m2 / :bucket) * :bucket AS area_bucket,
            trade_type_name,
            COUNT(*) AS cnt,
            ROUND(AVG(numeric_price)) AS avg_price,
            MIN(numeric_price) AS min_price,
            MAX(numeric_price) AS max_price
        FROM articles
        WHERE complex_no = :cno AND is_active = TRUE AND numeric_price IS NOT NULL
            AND area2_m2 IS NOT NULL AND area2_m2 > 0
        GROUP BY area_bucket, trade_type_name
        ORDER BY area_bucket, trade_type_name
    """).bindparams(cno=complex_no, bucket=AREA_BUCKET)
    area_rows = db.execute(area_stmt).fetchall()

    # floor_stmt 는 PostgreSQL `~` regex + `SPLIT_PART` 의존 → SQLite 미지원.
    # 테스트 엔진 (SQLite) 에서는 floor_rows 빈 배열로 우회 (by_floor 만 빈 결과,
    # by_area + tt_key_map 매핑 검증은 정상 동작). backend/CLAUDE.md §CI 답습.
    dialect_name = db.bind.dialect.name if db.bind else ""
    if dialect_name == "postgresql":
        floor_stmt = text("""
            SELECT
                CASE
                    WHEN floor_info ~ '^[0-9]+' THEN
                        CASE
                            WHEN CAST(SPLIT_PART(floor_info, '/', 1) AS INTEGER) BETWEEN 1 AND 5 THEN '저층(1-5)'
                            WHEN CAST(SPLIT_PART(floor_info, '/', 1) AS INTEGER) BETWEEN 6 AND 15 THEN '중층(6-15)'
                            WHEN CAST(SPLIT_PART(floor_info, '/', 1) AS INTEGER) > 15 THEN '고층(16+)'
                        END
                    WHEN LEFT(floor_info, 1) IN ('저', '중', '고') THEN
                        CASE LEFT(floor_info, 1)
                            WHEN '저' THEN '저층(1-5)'
                            WHEN '중' THEN '중층(6-15)'
                            WHEN '고' THEN '고층(16+)'
                        END
                END AS floor_tier,
                trade_type_name,
                COUNT(*) AS cnt,
                ROUND(AVG(numeric_price)) AS avg_price,
                MIN(numeric_price) AS min_price,
                MAX(numeric_price) AS max_price
            FROM articles
            WHERE complex_no = :cno AND is_active = TRUE AND numeric_price IS NOT NULL
                AND floor_info IS NOT NULL
            GROUP BY floor_tier, trade_type_name
            HAVING CASE
                    WHEN floor_info ~ '^[0-9]+' THEN
                        CASE
                            WHEN CAST(SPLIT_PART(floor_info, '/', 1) AS INTEGER) BETWEEN 1 AND 5 THEN '저층(1-5)'
                            WHEN CAST(SPLIT_PART(floor_info, '/', 1) AS INTEGER) BETWEEN 6 AND 15 THEN '중층(6-15)'
                            WHEN CAST(SPLIT_PART(floor_info, '/', 1) AS INTEGER) > 15 THEN '고층(16+)'
                        END
                    WHEN LEFT(floor_info, 1) IN ('저', '중', '고') THEN
                        CASE LEFT(floor_info, 1)
                            WHEN '저' THEN '저층(1-5)'
                            WHEN '중' THEN '중층(6-15)'
                            WHEN '고' THEN '고층(16+)'
                        END
                END IS NOT NULL
            ORDER BY floor_tier, trade_type_name
        """).bindparams(cno=complex_no)
        floor_rows = db.execute(floor_stmt).fetchall()
    else:
        floor_rows = []

    # 단기임대 → wolse 합산: 보증금 단위·구조 월세 동일, FE tradeKey 짝꿍 답습.
    # 새 거래유형 추가 시 본 dict + frontend/src/lib/trade-types.ts:18 양쪽 답습.
    # 주의: SQL GROUP BY 가 trade_type_name 별로 나누므로 wolse(월세) + wolse(단기임대)
    # 두 행이 같은 키에 들어옴 → count 합산 + 평균 가중평균 계산 의무.
    tt_key_map = {"매매": "maemae", "전세": "jeonse", "월세": "wolse", "단기임대": "wolse"}
    area_data: dict[float, dict] = {}
    # wolse 합산용 (count, sum) 임시 누적 — 가중평균 계산 후 entry 에 반영
    area_wolse_accum: dict[float, tuple[int, int]] = {}
    for row in area_rows:
        bucket = float(row[0]) if row[0] is not None else 0
        tt = row[1]
        key = tt_key_map.get(tt)
        if not key:
            continue
        cnt = int(row[2])
        avg = int(row[3]) if row[3] else 0
        entry = area_data.setdefault(bucket, {"label": f"{int(bucket)}m²"})
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

    by_area = [area_data[b] for b in sorted(area_data)]

    floor_data: dict[str, dict] = {}
    floor_wolse_accum: dict[str, tuple[int, int, int, int]] = {}  # (cnt, sum, min, max)
    for row in floor_rows:
        tier = row[0]
        tt = row[1]
        key = tt_key_map.get(tt)
        if not key or not tier:
            continue
        cnt = int(row[2])
        avg = int(row[3]) if row[3] else 0
        row_min = int(row[4]) if row[4] else 0
        row_max = int(row[5]) if row[5] else 0
        entry = floor_data.setdefault(tier, {"label": tier})
        if key == "wolse" and tier in floor_wolse_accum:
            prev_cnt, prev_sum, prev_min, prev_max = floor_wolse_accum[tier]
            new_cnt = prev_cnt + cnt
            new_sum = prev_sum + avg * cnt
            new_min = min(prev_min, row_min) if row_min else prev_min
            new_max = max(prev_max, row_max)
            floor_wolse_accum[tier] = (new_cnt, new_sum, new_min, new_max)
            entry[f"{key}_avg"] = new_sum // new_cnt if new_cnt else 0
            entry[f"{key}_min"] = new_min
            entry[f"{key}_max"] = new_max
            entry[f"{key}_count"] = new_cnt
        else:
            if key == "wolse":
                floor_wolse_accum[tier] = (cnt, avg * cnt, row_min, row_max)
            entry[f"{key}_avg"] = avg
            entry[f"{key}_min"] = row_min
            entry[f"{key}_max"] = row_max
            entry[f"{key}_count"] = cnt

    floor_order = ["저층(1-5)", "중층(6-15)", "고층(16+)"]
    by_floor = [floor_data[f] for f in floor_order if f in floor_data]

    total = sum(
        entry.get(f"{k}_count", 0)
        for entry in by_area
        for k in tt_key_map.values()
    )

    return {
        "complex_no": complex_no,
        "total_articles": total,
        "by_area": by_area,
        "by_floor": by_floor,
    }


def get_price_changed_articles(
    db: Session, complex_no: str | None = None, limit: int = 50
) -> list[Article]:
    """최근 가격 변동 매물 조회"""
    conditions = [
        Article.is_active == True,  # noqa: E712
        Article.price_changed_at.isnot(None),
    ]
    if complex_no:
        conditions.append(Article.complex_no == complex_no)

    stmt = (
        select(Article)
        .where(and_(*conditions))
        .order_by(Article.price_changed_at.desc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def get_complex_price_history(
    db: Session, complex_no: str, trade_type: Optional[str] = None,
    area_no: Optional[str] = None,
) -> list[dict]:
    """단지의 월별 가격 추이 (base_month를 YYYYMM으로 정규화 + 월별 집계)"""
    month_col = func.left(ComplexPriceHistory.base_month, 6).label("month")

    conditions = [ComplexPriceHistory.complex_no == complex_no]
    if trade_type:
        conditions.append(ComplexPriceHistory.trade_type == trade_type)
    if area_no:
        conditions.append(ComplexPriceHistory.area_no == area_no)

    stmt = (
        select(
            ComplexPriceHistory.trade_type,
            month_col,
            func.max(ComplexPriceHistory.price_upper).label("price_upper"),
            func.min(ComplexPriceHistory.price_lower).label("price_lower"),
            func.round(func.avg(ComplexPriceHistory.price_avg)).label("price_avg"),
        )
        .where(and_(*conditions))
        .group_by(ComplexPriceHistory.trade_type, month_col)
        .order_by(month_col.asc())
    )
    return [dict(row._mapping) for row in db.execute(stmt).all()]


def get_complex_trade_points(
    db: Session, complex_no: str,
    trade_type: Optional[str] = None,
    area2_m2: Optional[float] = None,
) -> list[dict]:
    """단지의 개별 실거래 점 (월별 평균 1점이 아니라 거래 1건 = 점 1건)"""
    conditions = [ComplexTradeRaw.complex_no == complex_no]
    if trade_type:
        conditions.append(ComplexTradeRaw.trade_type == trade_type)
    if area2_m2 is not None:
        conditions.append(ComplexTradeRaw.area2_m2 == area2_m2)

    stmt = (
        select(
            ComplexTradeRaw.deal_year_month.label("year_month"),
            ComplexTradeRaw.deal_day,
            ComplexTradeRaw.price,
            ComplexTradeRaw.area2_m2,
            ComplexTradeRaw.floor_number,
        )
        .where(and_(*conditions))
        .order_by(ComplexTradeRaw.deal_year_month.asc(), ComplexTradeRaw.deal_day.asc())
    )
    return [dict(row._mapping) for row in db.execute(stmt).all()]


def get_complex_official_prices(db: Session, complex_no: str) -> list[ComplexOfficialPrice]:
    """단지의 공동주택 공시가격 전체 행 조회 (연도 필터는 라우터에서 최신값만 선별)"""
    stmt = (
        select(ComplexOfficialPrice)
        .where(ComplexOfficialPrice.complex_no == complex_no)
    )
    return list(db.execute(stmt).scalars().all())


def get_latest_kapt_cost(db: Session, complex_no: str):
    """단지의 최신월 K-apt 관리비 1건 + 매칭정보. 매칭 자체가 없으면 None.

    반환은 (KaptManagementCost | None, KaptComplexMap) 튜플 — 화면이 관리비 금액과
    함께 "어느 K-apt 단지에 붙은 값인지"(kapt_name·복도유형)를 같이 보여줘야 해서
    한 번의 조인으로 가져온다.

    ⚠ **매칭 기준 LEFT JOIN** 이다(옛 구현은 관리비 기준 INNER JOIN).
    복도유형은 매칭 시점에 이미 KaptComplexMap 에 저장되므로 관리비가 없어도
    보여줄 수 있는데, INNER JOIN 이면 관리비가 없다는 이유로 복도유형까지 404 로
    함께 숨겨졌다 — 매칭 1,212건 중 관리비 보유는 19건뿐이라(2026-08-28 실측)
    사실상 대부분의 단지가 가진 정보를 못 보여주던 셈이다.

    따라서 반환 튜플의 첫 항목은 None 일 수 있고(매칭만 있고 관리비 미수집),
    호출자는 그 경우 금액 필드를 전부 null 로 내린다. 매칭 자체가 없을 때만
    None 을 돌려줘 라우터가 404 를 준다.
    """
    stmt = (
        select(KaptManagementCost, KaptComplexMap)
        .outerjoin(
            KaptManagementCost,
            KaptManagementCost.complex_no == KaptComplexMap.complex_no,
        )
        .where(KaptComplexMap.complex_no == complex_no)
        .order_by(KaptManagementCost.cost_month.desc())
        .limit(1)
    )
    return db.execute(stmt).first()
