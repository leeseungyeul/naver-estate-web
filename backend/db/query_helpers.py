"""쿼리 공통 헬퍼 — 필터 조건 빌더 + 정렬 빌더"""

import calendar
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, text

from db.models import Article


def _move_in_cutoff(now: datetime, months: int) -> str:
    """입주가능일 "N개월 이내" 필터의 상한 날짜 (YYYYMMDD 문자열).

    오늘로부터 N개월 뒤의 같은 일자까지 포함한다. N개월 뒤 달에 오늘 일자가
    없으면(예: 1/31 → 4월엔 31일 없음) 그 달의 말일로 clamp 한다. 옛 코드는
    무조건 28일로 잘라 월말(29~31일) 입주 매물을 며칠 누락했다 — calendar 로
    실제 말일을 계산해 손실 제거.
    """
    new_month = now.month + months
    new_year = now.year + (new_month - 1) // 12
    new_month = (new_month - 1) % 12 + 1
    last_day = calendar.monthrange(new_year, new_month)[1]
    day = min(now.day, last_day)
    return f"{new_year:04d}{new_month:02d}{day:02d}"


def _build_filter_conditions(filters: dict) -> list:
    """필터 딕셔너리를 SQLAlchemy WHERE 조건 리스트로 변환"""
    conditions = []

    # 거래유형
    if trade_types := filters.get("trade_types"):
        conditions.append(Article.trade_type_name.in_(trade_types))

    # 가격 범위 (만원)
    if (min_price := filters.get("min_price")) is not None:
        conditions.append(Article.numeric_price >= min_price)
    if (max_price := filters.get("max_price")) is not None:
        conditions.append(Article.numeric_price <= max_price)

    # 월세 범위
    if (min_rent := filters.get("min_rent")) is not None:
        conditions.append(Article.numeric_rent_price >= min_rent)
    if (max_rent := filters.get("max_rent")) is not None:
        conditions.append(Article.numeric_rent_price <= max_rent)

    # 면적 범위 (m²)
    if (min_area := filters.get("min_area_m2")) is not None:
        conditions.append(Article.area2_m2 >= min_area)
    if (max_area := filters.get("max_area_m2")) is not None:
        conditions.append(Article.area2_m2 <= max_area)

    # 방 수
    min_rooms = filters.get("min_rooms")
    if min_rooms is not None and min_rooms > 0:
        conditions.append(Article.room_count >= min_rooms)

    # 욕실 수
    min_baths = filters.get("min_baths")
    if min_baths is not None and min_baths > 0:
        conditions.append(Article.bathroom_count >= min_baths)

    # 방향
    if direction := filters.get("direction"):
        conditions.append(Article.direction == direction)

    # 평당가 범위
    if (min_ppyeong := filters.get("min_ppyeong")) is not None:
        conditions.append(Article.price_per_pyeong >= min_ppyeong)
    if (max_ppyeong := filters.get("max_ppyeong")) is not None:
        conditions.append(Article.price_per_pyeong <= max_ppyeong)

    # 관리비 범위
    if (min_maint := filters.get("min_maintenance")) is not None:
        conditions.append(Article.numeric_maintenance_cost >= min_maint)
    if (max_maint := filters.get("max_maintenance")) is not None:
        conditions.append(Article.numeric_maintenance_cost <= max_maint)

    # 동 (건물명)
    if building := filters.get("building_name"):
        conditions.append(Article.building_name == building)

    # 층수 범위
    if (min_floor := filters.get("min_floor")) is not None:
        conditions.append(Article.floor_number >= min_floor)
    if (max_floor := filters.get("max_floor")) is not None:
        conditions.append(Article.floor_number <= max_floor)

    # 검증 매물만
    if filters.get("verified_only"):
        conditions.append(Article.is_verified == True)  # noqa: E712

    # 태그 필터
    if tags := filters.get("tags"):
        for tag in tags:
            conditions.append(
                text("(:tag)::text = ANY(articles.tags)").bindparams(tag=tag)
            )

    # 준공년도 (N년 이내)
    if (max_age := filters.get("max_building_age")) and max_age > 0:
        min_year = datetime.now(ZoneInfo("Asia/Seoul")).year - max_age
        conditions.append(
            text("SUBSTRING(articles.use_approve_ymd, 1, 4)::INTEGER >= :min_year").bindparams(min_year=min_year)
        )

    # 매물유형 필터
    estate_type = filters.get("estate_type")
    if estate_type == "presale":
        conditions.append(Article.is_presale == True)  # noqa: E712
    elif estate_type == "apt":
        conditions.append(Article.article_real_estate_type_name == "아파트")
    elif estate_type == "opst":
        conditions.append(Article.article_real_estate_type_name == "오피스텔")
    elif estate_type == "jgc":
        conditions.append(Article.article_real_estate_type_name == "재건축")
    elif estate_type == "rdv":
        conditions.append(Article.article_real_estate_type_name == "재개발")

    # 수익률 범위 (%, SQL 계산식 — DB 컬럼 없음)
    _yield_base = (
        "articles.trade_type_name = '월세' "
        "AND articles.numeric_price > 0 "
        "AND articles.numeric_rent_price > 0"
    )
    if (min_yield := filters.get("min_yield")) is not None:
        conditions.append(
            text(
                f"{_yield_base} "
                "AND (articles.numeric_rent_price * 12.0) / articles.numeric_price * 100 >= :min_yield"
            ).bindparams(min_yield=min_yield)
        )
    if (max_yield := filters.get("max_yield")) is not None:
        conditions.append(
            text(
                f"{_yield_base} "
                "AND (articles.numeric_rent_price * 12.0) / articles.numeric_price * 100 <= :max_yield"
            ).bindparams(max_yield=max_yield)
        )

    # 입주가능일 타입
    move_in = filters.get("move_in_type")
    if move_in == "즉시입주":
        conditions.append(Article.move_in_date.in_(["즉시입주", "즉시"]))
    elif move_in == "협의":
        conditions.append(Article.move_in_date.in_(["협의", "협의가능"]))
    elif move_in and move_in.endswith("개월"):
        months_match = re.match(r"(\d+)개월", move_in)
        if months_match:
            months = int(months_match.group(1))
            cutoff = _move_in_cutoff(datetime.now(ZoneInfo("Asia/Seoul")), months)
            conditions.append(
                or_(
                    Article.move_in_date.in_(["즉시입주", "즉시"]),
                    and_(
                        Article.move_in_date.op("~")(r"^\d{8}$"),
                        Article.move_in_date <= cutoff,
                    ),
                )
            )

    return conditions


def _build_order_clause(sort_by: str):
    """정렬 키워드를 SQLAlchemy ORDER BY 절로 변환"""
    sort_map = {
        "rank": Article.article_confirm_ymd.desc(),
        "price_asc": Article.numeric_price.asc(),
        "price_desc": Article.numeric_price.desc(),
        "area_asc": Article.area2_m2.asc(),
        "area_desc": Article.area2_m2.desc(),
        "ppyeong_asc": Article.price_per_pyeong.asc(),
        "ppyeong_desc": Article.price_per_pyeong.desc(),
        "maintenance_asc": Article.numeric_maintenance_cost.asc(),
        "maintenance_desc": Article.numeric_maintenance_cost.desc(),
        "confirm_asc": Article.article_confirm_ymd.asc(),
        "confirm_desc": Article.article_confirm_ymd.desc(),
        # 동별 정렬 — 같은 동끼리 모아 보기. 길이+이름 순으로 2동<10동 꼬임 방지,
        # 2차 정렬은 가격 내림(같은 동에서 비싼 매물부터).
        "building_asc": (
            func.length(Article.building_name).asc(),
            Article.building_name.asc(),
            Article.numeric_price.desc(),
        ),
    }
    return sort_map.get(sort_by, Article.article_confirm_ymd.desc())
