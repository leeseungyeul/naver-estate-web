"""Read-only grouping of agent registrations in one complex.

Two-stage strategy:
- Articles whose naver_group_sync saved a real sameAddrCnt (>1) are grouped by
  that count's signature (동·층·면적·가격) — matches what Naver shows.
- Everything else falls back to the conservative exact-attribute estimate.
Never delete rows; a missing attribute stays a separate listing.
"""
from collections import defaultdict

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from db.models import Article
from db.query_helpers import _build_filter_conditions, _build_order_clause


def _candidate_key(row):
    (article_no, trade, estate_type, building, floor, area, price, rent,
     direction, same_count) = row
    # 네이버 실측 묶음(sameAddrCnt>1 저장분): 동·층정보·면적·가격 시그니처로 묶음
    if same_count is not None and same_count > 1 and trade and building \
            and area is not None and price is not None:
        return ("naver", trade, building, area, price)
    # 폴백: 보수적 정확 속성 추정 (기존 규칙)
    if (same_count is None or same_count <= 1 or not trade or not estate_type
            or not building or floor is None or area is None or price is None
            or not direction or (trade in ("월세", "단기임대") and rent is None)):
        return ("single", article_no)
    return ("conservative", trade, estate_type, building, floor, area,
            price, rent if trade in ("월세", "단기임대") else None,
            direction)


def get_grouped_articles_by_complex(
    db: Session, complex_no: str, filters: dict | None = None,
    sort_by: str = "rank", page: int = 1, page_size: int = 50,
) -> tuple[list[tuple[Article, list[Article]]], int, int]:
    """Filter/order first; group before pagination; fetch full rows only for page.

    The first sorted member represents a group. Sorting members by the same
    order lets a different sort choose a different, appropriate representative.
    """
    conditions = [Article.complex_no == complex_no, Article.is_active.is_(True)]
    if filters:
        conditions.extend(_build_filter_conditions(filters))
    order = _build_order_clause(sort_by)
    order_cols = list(order) if isinstance(order, tuple) else [order]
    narrow = select(
        Article.article_no, Article.trade_type_name,
        Article.article_real_estate_type_name, Article.building_name,
        Article.floor_number, Article.area2_m2, Article.numeric_price,
        Article.numeric_rent_price, Article.direction, Article.same_addr_cnt,
    ).where(and_(*conditions)).order_by(*order_cols, Article.article_no.asc())
    rows = db.execute(narrow).all()
    grouped: dict[tuple, list[str]] = {}
    for row in rows:
        grouped.setdefault(_candidate_key(row), []).append(row[0])
    group_ids = list(grouped.values())
    page_groups = group_ids[(page - 1) * page_size:page * page_size]
    ids = [no for group in page_groups for no in group]
    if not ids:
        return [], len(group_ids), len(rows)
    articles_by_no = {a.article_no: a for a in
                      db.execute(select(Article).where(Article.article_no.in_(ids))).scalars()}
    order = _build_order_clause(sort_by)
    page_data = [
        (articles_by_no[group[0]], [articles_by_no[no] for no in group])
        for group in page_groups
    ]
    return page_data, len(group_ids), len(rows)
