"""단지 조회 쿼리"""

import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from db.models import Article, Complex, ComplexPyeongDetail, SubwayStation
from utils import utcnow

logger = logging.getLogger(__name__)


def get_all_subway_stations(db: Session):
    """전국 도시철도 역사 전량 조회 (1,099행).

    좌표 프리필터를 두지 않는 것은 의도 — 소형 테이블이고 호출부가 단지별 12시간
    캐시를 씌우므로, bounding box 분기를 더하는 복잡도가 이득을 넘지 않는다.
    """
    return db.execute(select(SubwayStation)).scalars().all()


def search_complexes(db: Session, keyword: str, limit: int = 50):
    """단지명 키워드 검색 (pg_trgm 유사도)"""
    escaped = keyword.replace("%", "\\%").replace("_", "\\_")
    stmt = (
        select(Complex)
        .where(Complex.complex_name.ilike(f"%{escaped}%"))
        .order_by(Complex.complex_name)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def get_complexes_by_region(
    db: Session, sido: str, sigungu: Optional[str] = None, dong: Optional[str] = None,
    limit: int = 500,
):
    """지역별 단지 조회"""
    conditions = [Complex.sido == sido]
    if sigungu:
        conditions.append(Complex.sigungu == sigungu)
    if dong:
        conditions.append(Complex.dong == dong)

    stmt = (
        select(Complex)
        .where(and_(*conditions))
        .order_by(Complex.complex_name)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def get_complex_by_no(db: Session, complex_no: str) -> Optional[Complex]:
    """단지번호로 단지 조회"""
    return db.get(Complex, complex_no)


def get_complex_pyeong_details(db: Session, complex_no: str) -> list[ComplexPyeongDetail]:
    """단지 면적별 상세 정보 조회 (공급면적 순)"""
    stmt = (
        select(ComplexPyeongDetail)
        .where(ComplexPyeongDetail.complex_no == complex_no)
        .order_by(ComplexPyeongDetail.supply_area_double)
    )
    return db.execute(stmt).scalars().all()


def get_complex_article_count(db: Session, complex_no: str) -> int:
    """단지의 활성 매물 수"""
    stmt = (
        select(func.count())
        .select_from(Article)
        .where(and_(Article.complex_no == complex_no, Article.is_active == True))  # noqa: E712
    )
    return db.execute(stmt).scalar() or 0


def get_article_counts_by_complexes(db: Session, complex_nos: list[str]) -> dict[str, int]:
    """복수 단지의 활성 매물 수를 한 번에 조회 (N+1 방지)"""
    if not complex_nos:
        return {}
    stmt = (
        select(Article.complex_no, func.count())
        .where(and_(Article.complex_no.in_(complex_nos), Article.is_active == True))  # noqa: E712
        .group_by(Article.complex_no)
    )
    results = db.execute(stmt).all()
    return {row[0]: row[1] for row in results}


# 거래유형 4종 고정 (codes.md 답습 — trade_type_name 한국어 값)
_TRADE_TYPES = ("매매", "전세", "월세", "단기임대")


def get_trade_type_counts(db: Session, complex_no: str) -> dict[str, int]:
    """단지의 거래유형별 활성 매물 수. 4종 키 항상 포함(0 채움)."""
    stmt = (
        select(Article.trade_type_name, func.count())
        .where(and_(
            Article.complex_no == complex_no,
            Article.is_active == True,  # noqa: E712
            Article.trade_type_name.in_(_TRADE_TYPES),
        ))
        .group_by(Article.trade_type_name)
    )
    rows = dict(db.execute(stmt).all())
    return {t: rows.get(t, 0) for t in _TRADE_TYPES}


def get_trade_type_counts_by_complexes(
    db: Session, complex_nos: list[str]
) -> dict[str, dict[str, int]]:
    """복수 단지의 거래유형별 활성 매물 수 (N+1 방지)."""
    if not complex_nos:
        return {}
    stmt = (
        select(Article.complex_no, Article.trade_type_name, func.count())
        .where(and_(
            Article.complex_no.in_(complex_nos),
            Article.is_active == True,  # noqa: E712
            Article.trade_type_name.in_(_TRADE_TYPES),
        ))
        .group_by(Article.complex_no, Article.trade_type_name)
    )
    result: dict[str, dict[str, int]] = {
        no: {t: 0 for t in _TRADE_TYPES} for no in complex_nos
    }
    for cno, tname, cnt in db.execute(stmt).all():
        result[cno][tname] = cnt
    return result


def get_complexes_for_article_crawl(db: Session, limit: int = 50) -> list[Complex]:
    """매물 수집 배치 대상 단지 — 활성 lane + 발굴 lane 두 몫 (세션 402, V058).

    2026-04-13 에 `has_article.asc()`(매물 0건 단지 우선)를 넣은 것은 그 시점엔
    정당했다 — 당시 `last_crawled_at` 이 SQL 일괄 UPDATE 로 약 75% 허수라, 매물
    0건 단지(약 3.6만 개)가 "크롤한 척"하며 영원히 후순위로 밀렸기 때문이다.

    그런데 2026-09-13 prod 실측으로 그 전제가 반전됐다: 매물 0건 풀이
    53,581 로 불어나 있어 `has_article.asc()` 1차 정렬이 걸리는 한 활성 매물을
    가진 10,567 단지에는 사실상 도달하지 못한다. 그 결과 활성 단지의 76%
    (8,066개)가 30일 넘게, 그중 2,429개는 90일 넘게 목록 갱신을 못 받고
    있었다 — "매물 0건 단지를 먼저 본다"는 원래 선의가 정반대로 활성 단지를
    영구 사각으로 밀어낸 것이다.

    처방 = 몫 분할(lane). 발굴을 완전히 배제하면 `articles_crawled_at` 이
    한 번도 안 찍힌 14,923 단지가 이번엔 반대로 영구 사각이 되므로, 완전
    배제 대신 활성 80% + 발굴 20% 로 몫을 고정해 양쪽 다 굶기지 않는다.
    한쪽이 모자라면(활성 단지가 적거나 발굴 대상이 바닥나면) 남는 몫을
    다른 lane 이 흡수해 limit 을 최대한 채운다.

    - 활성 lane: 활성 매물이 있는 단지. `articles_crawled_at` 오래된 순
      (NULL 우선 — 아직 완주 스탬프가 없는 단지가 최우선), 동률은
      `last_crawled_at` 오래된 순.
    - 발굴 lane: 활성 매물이 없고 `articles_crawled_at` 도 없는(=한 번도
      완주한 적 없는) 단지. `last_crawled_at` 오래된 순(NULL 우선).

    "호출 총량 불변"은 **단지 수** 기준이지 **네이버 호출 수** 기준이
    아니다 — 매물을 가진 단지는 페이지네이션이 붙어 단지당 호출이 여러 번
    나갈 수 있다(발굴 lane 단지는 대개 0~1 페이지). 실제 네이버 호출량
    변화는 `record_call("crawl_articles_batch")` 로 1주 관찰 대상이다.

    인덱스: 이 PR 에서는 새 인덱스를 만들지 않는다. V058 적용 직후(신규
    컬럼 전부 NULL) prod EXPLAIN (ANALYZE, BUFFERS) 실측(2026-09-13 14:38) —
    활성 lane(LIMIT 120): 180ms · Buffers 70,841(전부 shared hit,
    `ix_articles_complex_active` 로 Index Only Scan). 발굴 lane(LIMIT 30):
    413ms · Buffers 208,497(NOT EXISTS 가 64,148 단지를 전수 프로브). 이
    쿼리는 배치가 하루 2회(cron 01:00/13:00)만 호출하므로 비용 무시 가능 —
    다음에 재측정할 사람을 위해 수치를 남긴다.
    """
    n_active = max(1, round(limit * 0.8))

    has_active_article = (
        select(Article.complex_no)
        .where(and_(Article.complex_no == Complex.complex_no, Article.is_active == True))  # noqa: E712
        .exists()
    )

    def _fetch_active(n: int) -> list[Complex]:
        stmt = (
            select(Complex)
            .where(has_active_article)
            .order_by(
                Complex.articles_crawled_at.asc().nullsfirst(),
                Complex.last_crawled_at.asc().nullsfirst(),
            )
            .limit(n)
        )
        return list(db.execute(stmt).scalars().all())

    active_complexes = _fetch_active(n_active)

    # 발굴 lane 부족분 = 활성 lane 이 다 못 채운 몫까지 흡수
    n_discover_actual = limit - len(active_complexes)
    discover_stmt = (
        select(Complex)
        .where(and_(~has_active_article, Complex.articles_crawled_at.is_(None)))
        .order_by(Complex.last_crawled_at.asc().nullsfirst())
        .limit(n_discover_actual)
    )
    discover_complexes = list(db.execute(discover_stmt).scalars().all())

    # 발굴 lane 이 모자라면(대상 고갈) 활성 lane 을 더 큰 limit 으로 재조회해 채운다
    # (같은 정렬 기준의 접두어 확장이라 앞서 뽑은 것과 중복되지 않는다)
    remaining = limit - len(active_complexes) - len(discover_complexes)
    if remaining > 0:
        active_complexes = _fetch_active(len(active_complexes) + remaining)

    return active_complexes + discover_complexes


def get_complexes_for_popular_crawl(db: Session, limit: int) -> list[Complex]:
    """인기 단지 선제적 크롤링 대상 — 최근 7일 사용자 클릭 우선 (세션 402, V058).

    기존 선정 키 `last_crawled_at DESC` 는 이 컬럼이 배치·자매 프로젝트의
    일괄 스탬프에 함께 오염돼 있어, "사용자가 최근 조회한 단지"가 아니라
    "아무나 최근에 건드린 단지"를 뽑고 있었다. 실측(2026-09-13, 최근 7일
    1,050회 인기 크롤 중 846회=81%)이 직전 24시간 안에 배치가 이미 긁은
    단지를 그대로 재방문한 낭비였음을 보여준다.

    처방 = `last_viewed_at`(V058, 사용자가 `start-crawl` 을 호출한 시각)을
    1순위로 쓴다. 최근 7일 안에 조회된 단지만 인정하고(그보다 오래된
    조회는 "최근 인기"로 보기 어렵다), 그 조건을 만족하는 단지가 limit 에
    못 미치면 활성 lane(articles_crawled_at 오래된 순)에서 부족분을 채워
    배치를 놀리지 않는다.

    7일 컷오프는 Python 에서 계산해 파라미터로 넘긴다 — SQL `now()` 함수는
    SQLite 테스트 환경에서 못 쓴다(domain-mapping-ssot.md 룰 3 dialect
    분기 원칙과 같은 결).
    """
    cutoff = utcnow() - timedelta(days=7)

    # V069 — 관심 호가 추적 단지 중 20시간 넘게 완주 수집이 없는 단지를 맨 앞에 둔다.
    # 같은 limit 안에서 순서만 바꾸므로 회차당 네이버 호출 총량은 그대로다.
    # 실패(예: V069 미적용 DB)해도 원래 선정으로 그대로 진행한다 — 인기 갱신 자체를 막지 않는다.
    from services.price_watch import watched_complex_nos_needing_crawl
    try:
        # 관심 단지는 몫의 절반까지만 — "최근 조회" 단지가 통째로 밀려나지 않게
        watched_nos = watched_complex_nos_needing_crawl(db, max(1, limit // 2))
    except Exception as e:
        logger.warning("관심 단지 우선 선정 건너뜀(원래 선정으로 진행): %s", e)
        db.rollback()
        watched_nos = []
    watched_complexes = []
    if watched_nos:
        by_no = {c.complex_no: c for c in db.execute(
            select(Complex).where(Complex.complex_no.in_(watched_nos))).scalars().all()}
        watched_complexes = [by_no[no] for no in watched_nos if no in by_no]

    viewed_stmt = (
        select(Complex)
        .where(and_(Complex.last_viewed_at.isnot(None), Complex.last_viewed_at > cutoff))
        .order_by(Complex.last_viewed_at.desc())
        .limit(limit)
    )
    if watched_nos:
        viewed_stmt = viewed_stmt.where(Complex.complex_no.notin_(watched_nos))
    viewed_complexes = watched_complexes + list(db.execute(viewed_stmt).scalars().all())
    viewed_complexes = viewed_complexes[:limit]

    remaining = limit - len(viewed_complexes)
    if remaining <= 0:
        return viewed_complexes

    picked_nos = [c.complex_no for c in viewed_complexes]
    has_active_article = (
        select(Article.complex_no)
        .where(and_(Article.complex_no == Complex.complex_no, Article.is_active == True))  # noqa: E712
        .exists()
    )
    fallback_stmt = (
        select(Complex)
        .where(has_active_article, Complex.complex_no.notin_(picked_nos))
        .order_by(
            Complex.articles_crawled_at.asc().nullsfirst(),
            Complex.last_crawled_at.asc().nullsfirst(),
        )
        .limit(remaining)
    )
    fallback_complexes = list(db.execute(fallback_stmt).scalars().all())

    return viewed_complexes + fallback_complexes


def get_complexes_for_detail_enrich(db: Session, real_estate_type: str, limit: int = 500) -> list[str]:
    """단지 상세 미수집 단지의 complex_no 목록 (유형별 backfill 용).

    real_estate_type 으로 매물유형을 분리해 backfill 한다 (전 유형 일괄 금지).
    detail_crawled_at IS NULL 인 단지만 반환 — V022 인덱스
    (real_estate_type_code, detail_crawled_at) 가 가속.
    """
    stmt = (
        select(Complex.complex_no)
        .where(and_(
            Complex.real_estate_type_code == real_estate_type,
            Complex.detail_crawled_at.is_(None),
        ))
        .limit(limit)
    )
    return [row[0] for row in db.execute(stmt).all()]
