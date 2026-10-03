"""단지 관련 API 엔드포인트"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from crawler.utils import haversine_km
from db import queries
from db.article_grouping import get_grouped_articles_by_complex
from deps import get_approved_user, get_db
from routers.serializers import (
    article_to_dict,
    build_filter_dict,
    complex_to_dict,
    kapt_cost_to_dict,
)
from services.cache import TTLCache, get_cache

router = APIRouter()

# 필터 옵션 & 가격 통계 캐시 (시간대별 동적 TTL) — 레지스트리 기반으로 live.py에서 무효화 가능
_cache = get_cache("complexes", dynamic=True)
# 가격 추이 캐시 — immutable 데이터이므로 고정 12시간 TTL
_price_history_cache = TTLCache(ttl=43200, max_size=1000)


@router.get("/search")
def search_complexes(
    q: str = Query(..., min_length=1, description="검색 키워드"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """단지명 키워드 검색"""
    results = queries.search_complexes(db, q, limit=limit)
    # 매물 수 배치 조회 (region 엔드포인트와 동일 패턴)
    complex_nos = [c.complex_no for c in results]
    counts = queries.get_article_counts_by_complexes(db, complex_nos)
    trade_counts = queries.get_trade_type_counts_by_complexes(db, complex_nos)
    return {
        "complexes": [
            {
                **complex_to_dict(c),
                "article_count": counts.get(c.complex_no, 0),
                "trade_type_counts": trade_counts.get(c.complex_no),
            }
            for c in results
        ],
        "total": len(results),
    }


@router.get("/region")
def get_complexes_by_region(
    sido: str = Query(...),
    sigungu: Optional[str] = Query(None),
    dong: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """지역별 단지 조회"""
    cache_key = f"region:{sido}:{sigungu or ''}:{dong or ''}:{limit}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    results = queries.get_complexes_by_region(db, sido, sigungu, dong, limit=limit)
    # 매물 수 배치 조회
    complex_nos = [c.complex_no for c in results]
    counts = queries.get_article_counts_by_complexes(db, complex_nos)
    trade_counts = queries.get_trade_type_counts_by_complexes(db, complex_nos)
    result = {
        "complexes": [
            {
                **complex_to_dict(c),
                "article_count": counts.get(c.complex_no, 0),
                "trade_type_counts": trade_counts.get(c.complex_no),
            }
            for c in results
        ],
        "total": len(results),
    }
    _cache.set(cache_key, result)
    return result


@router.get("/{complex_no}")
def get_complex_detail(
    complex_no: str,
    db: Session = Depends(get_db),
):
    """단지 상세 정보 (캐시 적용)"""
    detail_key = f"complex_detail:{complex_no}"
    cached = _cache.get(detail_key)
    if cached is not None:
        return cached

    cpx = queries.get_complex_by_no(db, complex_no)
    if not cpx:
        raise HTTPException(status_code=404, detail="단지를 찾을 수 없습니다")

    article_count = queries.get_complex_article_count(db, complex_no)
    fo_key = f"filter_options:{complex_no}"
    filter_options = _cache.get(fo_key)
    if filter_options is None:
        filter_options = queries.get_filter_options(db, complex_no)
        _cache.set(fo_key, filter_options)
    result = {
        **complex_to_dict(cpx),
        "article_count": article_count,
        "trade_type_counts": queries.get_trade_type_counts(db, complex_no),
        "filter_options": filter_options,
    }
    _cache.set(detail_key, result)
    return result



@router.get("/{complex_no}/filter-options")
def get_filter_options(
    complex_no: str,
    db: Session = Depends(get_db),
):
    """단지 내 필터 옵션 (동, 태그, 방향)"""
    cache_key = f"filter_options:{complex_no}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    result = queries.get_filter_options(db, complex_no)
    _cache.set(cache_key, result)
    return result


@router.get("/{complex_no}/articles")
def get_complex_articles(
    complex_no: str,
    # 필터
    trade_types: Optional[str] = Query(None, max_length=100, description="거래유형 (쉼표 구분: 매매,전세,월세)"),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    min_rent: Optional[int] = Query(None, ge=0),
    max_rent: Optional[int] = Query(None, ge=0),
    min_area_m2: Optional[float] = Query(None, ge=0),
    max_area_m2: Optional[float] = Query(None, ge=0),
    min_rooms: Optional[int] = Query(None, ge=0),
    min_baths: Optional[int] = Query(None, ge=0),
    direction: Optional[str] = Query(None),
    min_ppyeong: Optional[int] = Query(None, ge=0),
    max_ppyeong: Optional[int] = Query(None, ge=0),
    min_maintenance: Optional[int] = Query(None, ge=0),
    max_maintenance: Optional[int] = Query(None, ge=0),
    building_name: Optional[str] = Query(None, max_length=100),
    verified_only: bool = Query(False),
    max_building_age: Optional[int] = Query(None),
    move_in_type: Optional[str] = Query(None),
    estate_type: Optional[str] = Query(None),
    min_floor: Optional[int] = Query(None, ge=0),
    max_floor: Optional[int] = Query(None, ge=0),
    tags: Optional[str] = Query(None, max_length=200, description="태그 (쉼표 구분)"),
    min_yield: Optional[float] = Query(None, ge=0, le=100, description="최소 수익률 (%)"),
    max_yield: Optional[float] = Query(None, ge=0, le=100, description="최대 수익률 (%)"),
    # 정렬/페이지
    sort_by: Literal["rank", "price_asc", "price_desc", "area_asc", "area_desc", "ppyeong_asc", "ppyeong_desc", "maintenance_asc", "maintenance_desc", "confirm_asc", "confirm_desc", "building_asc"] = Query("rank"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    group_duplicates: bool = Query(False),
    db: Session = Depends(get_db),
    user: dict = Depends(get_approved_user),  # B2 게이트: 승인 중개사 전용 (매물 목록)
):
    """단지별 매물 조회 (필터 + 정렬 + 페이지네이션, 기본 조회 캐시) — 승인 중개사 전용"""
    filters = build_filter_dict(
        trade_types=trade_types, min_price=min_price, max_price=max_price,
        min_rent=min_rent, max_rent=max_rent,
        min_area_m2=min_area_m2, max_area_m2=max_area_m2,
        min_rooms=min_rooms, min_baths=min_baths, direction=direction,
        min_ppyeong=min_ppyeong, max_ppyeong=max_ppyeong,
        min_maintenance=min_maintenance, max_maintenance=max_maintenance,
        building_name=building_name, verified_only=verified_only,
        max_building_age=max_building_age, move_in_type=move_in_type,
        estate_type=estate_type,
        min_floor=min_floor, max_floor=max_floor, tags=tags,
        min_yield=min_yield, max_yield=max_yield,
    )

    if group_duplicates:
        groups, total, raw_total = get_grouped_articles_by_complex(
            db, complex_no, filters=filters, sort_by=sort_by,
            page=page, page_size=page_size,
        )
        return {
            "articles": [
                {**article_to_dict(rep), "group_count": len(members),
                 "group_members": [article_to_dict(a) for a in members]}
                for rep, members in groups
            ],
            "total": total, "raw_total": raw_total,
            "page": page, "page_size": page_size,
        }

    # 필터 없는 첫 페이지 기본 조회 → 캐시 (페이지 진입 속도 향상)
    is_default = (
        page == 1 and sort_by == "rank" and page_size == 50
        and not filters
    )
    if is_default:
        art_cache_key = f"articles_default:{complex_no}"
        cached = _cache.get(art_cache_key)
        if cached is not None:
            return cached

    articles, total_count = queries.get_articles_by_complex(
        db, complex_no, filters=filters, sort_by=sort_by,
        page=page, page_size=page_size,
    )

    result = {
        "articles": [article_to_dict(a) for a in articles],
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }

    if is_default:
        _cache.set(art_cache_key, result)

    return result


@router.get("/{complex_no}/pyeong-details")
def get_pyeong_details(
    complex_no: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_approved_user),  # B2 게이트: 승인 중개사 전용 (면적별 상세)
):
    """단지 면적별 상세 정보 (캐시 적용) — 승인 중개사 전용"""
    pyeong_key = f"pyeong_details:{complex_no}"
    cached = _cache.get(pyeong_key)
    if cached is not None:
        return cached

    details = queries.get_complex_pyeong_details(db, complex_no)
    if not details:
        from services.enricher import enrich_complex_detail
        enrich_complex_detail(db, complex_no)
        db.commit()
        details = queries.get_complex_pyeong_details(db, complex_no)
    result = {
        "pyeong_details": [
            {
                "pyeong_no": p.pyeong_no,
                "pyeong_name": p.pyeong_name,
                "supply_area": p.supply_area,
                "supply_area_double": p.supply_area_double,
                "exclusive_area": p.exclusive_area,
                "exclusive_rate": p.exclusive_rate,
                "household_count_by_pyeong": p.household_count_by_pyeong,
                "entrance_type": p.entrance_type,
                "room_count": p.room_count,
                "bathroom_count": p.bathroom_count,
                "avg_maintenance_cost": p.avg_maintenance_cost,
                "summer_maintenance_cost": p.summer_maintenance_cost,
                "winter_maintenance_cost": p.winter_maintenance_cost,
                "floor_plan_url": p.floor_plan_url,
                "supply_pyeong": p.supply_pyeong,
                "exclusive_pyeong": p.exclusive_pyeong,
                "latest_maintenance_cost": p.latest_maintenance_cost,
                "maintenance_cost_basis": p.maintenance_cost_basis,
            }
            for p in details
        ]
    }
    _cache.set(pyeong_key, result)
    return result



@router.get("/{complex_no}/price-stats")
def get_price_stats(
    complex_no: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_approved_user),  # B2 게이트: 승인 중개사 전용 (시세 통계)
):
    """단지 매물 가격 통계 — 거래유형별 면적/층수 비교 (SQL 집계) — 승인 중개사 전용"""
    cache_key = f"price_stats:{complex_no}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    result = queries.get_price_stats_aggregated(db, complex_no)
    _cache.set(cache_key, result)
    return result


_TT_LABELS = {"A1": "매매", "B1": "전세", "B2": "월세", "B3": "단기임대"}


@router.get("/{complex_no}/price-history")
def get_price_history(
    complex_no: str,
    trade_type: Optional[Literal["A1", "B1", "B2", "B3"]] = Query(None),
    area_no: Optional[str] = Query(None, max_length=20, pattern=r"^[0-9]+$"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_approved_user),  # B2 게이트: 승인 중개사 전용 (가격 추이)
):
    """단지 월별 가격 추이 (실거래가 + 시세) — 승인 중개사 전용"""
    cache_key = f"price_history:{complex_no}:{trade_type or 'all'}:{area_no or 'all'}"
    cached = _price_history_cache.get(cache_key)
    if cached is not None:
        return cached

    rows = queries.get_complex_price_history(db, complex_no, trade_type, area_no=area_no)
    result = {
        "complex_no": complex_no,
        "items": [
            {
                "trade_type": r["trade_type"],
                "trade_type_label": _TT_LABELS.get(r["trade_type"], r["trade_type"]),
                "price_upper": r["price_upper"],
                "price_lower": r["price_lower"],
                "price_avg": int(r["price_avg"]) if r["price_avg"] is not None else None,
                "base_month": r["month"][:6],
            }
            for r in rows
        ],
    }
    _price_history_cache.set(cache_key, result)
    # 브라우저 HTTP 캐시가 오래된 빈 응답을 재사용하는 문제 방지 (실거래가 수집 직후 특히)
    return JSONResponse(content=result, headers={"Cache-Control": "no-store"})


@router.get("/{complex_no}/trade-points")
def get_trade_points(
    complex_no: str,
    trade_type: Optional[Literal["A1", "B1", "B2", "B3"]] = Query(None),
    area2_m2: Optional[float] = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_approved_user),  # B2 게이트: price-history 답습
):
    """단지 개별 실거래 점 (거래 1건 = 점 1건) — 승인 중개사 전용"""
    points = queries.get_complex_trade_points(db, complex_no, trade_type, area2_m2=area2_m2)
    return JSONResponse(
        content={
            "complex_no": complex_no,
            "points": [
                {
                    "year_month": p["year_month"],
                    "deal_day": p["deal_day"],
                    "price": p["price"],
                    "area2_m2": p["area2_m2"],
                    "floor_number": p["floor_number"],
                }
                for p in points
            ],
        },
        headers={"Cache-Control": "no-store"},
    )


# 공시가격 캐시 — 월 1회 갱신이라 오래 캐시 가능 (12시간 고정 TTL, price-history 답습)
_official_price_cache = TTLCache(ttl=43200, max_size=1000)


@router.get("/{complex_no}/official-prices")
def get_official_prices(
    complex_no: str,
    db: Session = Depends(get_db),
):
    """단지 공동주택 공시가격 (국토교통부) — 무료 공개 (게이트 없음, 플랜 §0-2)"""
    cache_key = f"official_prices:{complex_no}"
    cached = _official_price_cache.get(cache_key)
    if cached is not None:
        return cached

    rows = queries.get_complex_official_prices(db, complex_no)
    years = {r.stdr_year for r in rows}
    latest_year = max(years) if years else None
    result = {
        "complex_no": complex_no,
        "year": latest_year,
        "items": sorted(
            (
                {
                    "prvuse_ar": float(r.prvuse_ar),
                    "price_median": r.price_median,
                    "ho_count": r.ho_count,
                }
                for r in rows
                if r.stdr_year == latest_year
            ),
            key=lambda item: item["prvuse_ar"],
        ),
    }
    _official_price_cache.set(cache_key, result)
    return result


# 가까운 지하철 캐시 — 역사 데이터는 연 1회 갱신이라 오래 캐시 가능
# (12시간 고정 TTL, official-prices 답습)
_subway_cache = TTLCache(ttl=43200, max_size=1000)

_SUBWAY_RADIUS_KM = 3.0
_SUBWAY_MAX_STATIONS = 3


def _normalize_station_name(name: str) -> str:
    """역명 끝의 "역" 접미사를 떼어낸 그룹핑 정규형.

    원본이 같은 물리 역을 노선에 따라 "선릉"(2호선)/"선릉역"(분당선) 처럼 다르게 실어서,
    접미사를 안 떼면 한 역이 결과 슬롯을 두 칸 차지한다(라이브 실측: 역삼IPARK).
    전국 50개 역이 이 표기 불일치에 걸린다.

    떼어낸 결과가 한 글자 이하면 원본을 유지한다 — "역" 단독 역명 방어(현 데이터엔
    없지만 갱신본에서 생길 수 있다).

    ⚠ 이름만으로 묶으므로 원리상 동명이역(부산 "송정" vs 부산진구 "송정역", 340km)도
    같은 키가 된다. 다만 호출부가 3km 반경으로 먼저 거른 뒤 묶어서 실제 충돌은 없다
    (실측: 한 반경에 동시 등장 가능한 동명 쌍 51건은 전부 4~376m 의 진짜 환승역).
    """
    if name.endswith("역"):
        stripped = name[:-1]
        if len(stripped) > 1:
            return stripped
    return name


@router.get("/{complex_no}/subway")
def get_nearby_subway(
    complex_no: str,
    db: Session = Depends(get_db),
):
    """단지 반경 3km 내 가까운 지하철역 최대 3곳 — 무료 공개 (게이트 없음, 공시가격 답습)

    같은 역이 노선별로 여러 행인 원본 구조라 역명으로 묶는다 — 거리는 최단 행 기준,
    노선명은 반경 안에 든 그 역의 모든 노선을 모아 보여준다. 원본이 "선릉"/"선릉역"
    처럼 접미사를 섞어 쓰므로 정규형(_normalize_station_name)을 그룹핑 키로 쓴다.

    응답 station_name 도 접미사 없는 정규형이다 — FE formatStationName 이 "역"을
    붙여 표시하므로 화면에는 "선릉역"으로 나온다.
    """
    cache_key = f"subway:{complex_no}"
    cached = _subway_cache.get(cache_key)
    if cached is not None:
        return cached

    cpx = queries.get_complex_by_no(db, complex_no)
    if not cpx:
        raise HTTPException(status_code=404, detail="단지를 찾을 수 없습니다")

    # 좌표 없는 단지는 계산이 불가능 — 에러가 아니라 빈 목록 (FE 계약)
    if cpx.latitude is None or cpx.longitude is None:
        result = {"stations": []}
        _subway_cache.set(cache_key, result)
        return result

    # 정규화 역명 → {최단거리, 노선명 집합}. 반경 밖 행은 노선 수집에서도 제외한다.
    grouped: dict[str, dict] = {}
    for station in queries.get_all_subway_stations(db):
        distance_km = haversine_km(
            cpx.latitude, cpx.longitude, station.latitude, station.longitude
        )
        if distance_km > _SUBWAY_RADIUS_KM:
            continue
        key = _normalize_station_name(station.station_name)
        entry = grouped.get(key)
        if entry is None:
            grouped[key] = {
                "distance_km": distance_km,
                "lines": {station.line_name},
            }
        else:
            entry["distance_km"] = min(entry["distance_km"], distance_km)
            entry["lines"].add(station.line_name)

    nearest = sorted(grouped.items(), key=lambda item: item[1]["distance_km"])[
        :_SUBWAY_MAX_STATIONS
    ]
    result = {
        "stations": [
            {
                "station_name": name,
                "lines": sorted(entry["lines"]),
                "distance_m": round(entry["distance_km"] * 1000),
            }
            for name, entry in nearest
        ]
    }
    _subway_cache.set(cache_key, result)
    return result


# K-apt 관리비 캐시 — 월 1회 갱신이라 오래 캐시 가능 (12시간, official-prices 답습)
_kapt_cost_cache = TTLCache(ttl=43200, max_size=1000)


@router.get("/{complex_no}/kapt")
def get_kapt_management_cost(
    complex_no: str,
    db: Session = Depends(get_db),
):
    """단지 월 관리비 (K-apt 공동주택관리정보시스템) — 최신 수집월 1건.

    **매칭이 없을 때만 404** 다(K-apt 미등록·게이트 탈락). 매칭은 있는데 관리비가
    아직 없으면(수집 대기·미공개) 200 + 금액 필드 전부 null 로 내린다 — 복도유형은
    매칭 시점에 이미 확보되므로 관리비를 못 모았다는 이유로 그것까지 숨길 이유가
    없다(매칭 1,212건 중 관리비 보유 19건, 2026-08-28 실측).

    금액이 null 인 것과 "관리비 0원"은 여전히 구분된다 — 0 은 숫자로 내려간다.
    """
    cache_key = f"kapt:{complex_no}"
    cached = _kapt_cost_cache.get(cache_key)
    if cached is not None:
        return cached

    row = queries.get_latest_kapt_cost(db, complex_no)
    if row is None:
        raise HTTPException(status_code=404, detail="관리비 정보가 없습니다")

    cost, mapping = row
    result = kapt_cost_to_dict(cost, mapping)
    _kapt_cost_cache.set(cache_key, result)
    return result
