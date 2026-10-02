"""매물 조회 쿼리 (필터 + 정렬 + 페이지네이션)"""

from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from db.models import Article
from db.query_helpers import _build_filter_conditions, _build_order_clause


def get_articles_by_complex(
    db: Session,
    complex_no: str,
    filters: Optional[dict] = None,
    sort_by: str = "rank",
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Article], int]:
    """단지별 매물 조회 (필터링 + 정렬 + 페이지네이션)

    Returns:
        (articles, total_count)
    """
    conditions = [
        Article.complex_no == complex_no,
        Article.is_active == True,  # noqa: E712
    ]

    if filters:
        conditions.extend(_build_filter_conditions(filters))

    count_stmt = (
        select(func.count())
        .select_from(Article)
        .where(and_(*conditions))
    )
    total_count = db.execute(count_stmt).scalar() or 0

    order_clause = _build_order_clause(sort_by)

    stmt = (
        select(Article)
        .where(and_(*conditions))
        .order_by(*order_clause if isinstance(order_clause, tuple) else [order_clause])
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    articles = db.execute(stmt).scalars().all()

    return articles, total_count


def get_article_by_no(db: Session, article_no: str) -> Optional[Article]:
    """매물번호로 매물 상세 조회"""
    return db.get(Article, article_no)
