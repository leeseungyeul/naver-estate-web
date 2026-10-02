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
    # 네이버 실측 묶음(sameAddrCnt>1 저장분): 네이버는 같은 호실도 층표시(고/36·중/36)와
    # 등록 대표별로 행을 나눠 보여주므로 시그니처에 층표시를 포함한다(실측: 파크리오 84㎡
    # 매매 네이버 UI 177 = 대표 행 수 그 자체).
    if same_count is not None and same_count > 1 and trade and building \
            and area is not None and price is not None:
        return ("naver", trade, building, floor, area, price)
    # cnt<=1: 네이버도 이런 등록은 대표 행 각각을 보여준다 — 같은 (동·층·면적·가격)
    # 시그니처끼리 1그룹으로 모아되 각 행은 원본 유지(실측: 파크리오 single 82행 →
    # 네이버식 70행).
    if (same_count is None or same_count <= 1) and trade and building \
            and floor is not None and area is not None and price is not None \
            and not (trade in ("월세", "단기임대") and rent is None):
        return ("unique", trade, building, floor, area, price,
                rent if trade in ("월세", "단기임대") else None)
    # 폴백: 속성 일부 누락 — 보수적으로 각각 분리
    return ("single", article_no)


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
