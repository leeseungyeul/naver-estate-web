"""관심 단지 매매호가 추적 — 날짜별 기록 + 두 가지 변동률 분석 (V069).

① 동일 매물 추정 변동률 (analyze_units)
   네이버는 호수(몇 호)를 주지 않고, 같은 집을 중개사마다 따로 올리며, 내렸다 다시
   올리면 매물번호도 바뀐다. 그래서 매물번호가 아니라 (단지·동·층·전용면적)이 같으면
   "같은 집으로 추정"해 한 줄로 묶는다. 같은 날 여러 중개사가 올린 값은 최저가를 쓴다
   (매수자가 실제로 보는 값). 추정 신뢰도: 층이 숫자면 높음, 고/중/저면 보통,
   동·층·면적 중 하나라도 없으면 매물번호 단위로만 추적(낮음).
   ⚠ 같은 동·같은 층·같은 면적의 두 호실(예: 1201호·1202호)은 구분할 수 없다 —
   그날 가격 범위(min~max)와 등록 수를 함께 돌려줘 화면에서 알아볼 수 있게 한다.

② 여러 단지 묶음 평균 변동률 (analyze_basket)
   날짜별로 대상(단지+평형)들의 집(추정 단위) 호가를 모아 평균 호가·전용 3.3㎡당 평균을
   낸다. 매물이 들고 나며 구성이 바뀌면 평균이 출렁이므로, 이웃한 두 날짜에 모두 있는
   같은 집끼리만 비교해 이어 붙인 "동일 매물 지수"(시작=100)를 함께 낸다.
   단지마다 수집일이 달라 생기는 빈칸은 그 단지의 직전 기록(최대 CARRY_FORWARD_DAYS일)으로 메운다.

기록은 매물 수집이 끝까지 성공했을 때만 남긴다(부분 목록으로 기록하면 사라진 집처럼 보인다).
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from db.models import Article, Complex, PriceWatchSnapshot, PriceWatchTarget
from services.upsert import _do_upsert
from shared.constants import M2_TO_PYEONG
from utils import utcnow

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
TRADE_SALE = "매매"
AREA_TOLERANCE_M2 = 0.5
CARRY_FORWARD_DAYS = 14
MAX_TARGETS_PER_USER = 20


def kst_date(dt: datetime | None = None) -> date:
    dt = dt or utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(KST).date()


# ── 기록 ────────────────────────────────────────────────────────────────

def is_watched(db: Session, complex_no: str) -> bool:
    return db.execute(
        select(PriceWatchTarget.id).where(PriceWatchTarget.complex_no == complex_no).limit(1)
    ).first() is not None


def record_snapshot(db: Session, complex_no: str, snapshot_date: date | None = None,
                    commit: bool = True) -> int:
    """그 단지의 지금 활성 매매 매물을 snapshot_date(기본 오늘 KST) 기록으로 덮어쓴다.

    같은 날 이전 기록 중 지금 목록에 없는 매물은 지운다 — 하루의 마지막 완주 수집이
    그날의 정답이다. 반환 = 기록한 매물 수.
    """
    snapshot_date = snapshot_date or kst_date()
    rows = db.execute(
        select(
            Article.article_no, Article.building_name, Article.floor_info,
            Article.area1_m2, Article.area2_m2, Article.numeric_price,
        ).where(
            Article.complex_no == complex_no,
            Article.is_active == True,  # noqa: E712
            Article.trade_type_name == TRADE_SALE,
            Article.numeric_price.isnot(None),
            Article.numeric_price > 0,
        )
    ).all()
    if not rows:
        # 0건은 기록하지 않는다 — 네이버가 일시적으로 빈 목록을 주는 경우(소프트 차단)에
        # 그날 정상 기록까지 지우지 않기 위해서다. 진짜로 다 빠졌다면 다음 기록일에 사라짐으로 보인다.
        return 0
    now = utcnow()
    seen = []
    for no, building, floor_info, area1, area2, price in rows:
        _do_upsert(db, PriceWatchSnapshot, {
            "snapshot_date": snapshot_date, "complex_no": complex_no, "article_no": no,
            "building_name": building, "floor_info": floor_info,
            "area1_m2": area1, "area2_m2": area2, "price": price, "recorded_at": now,
        }, ["snapshot_date", "article_no"])
        seen.append(no)
    db.execute(delete(PriceWatchSnapshot).where(
        PriceWatchSnapshot.snapshot_date == snapshot_date,
        PriceWatchSnapshot.complex_no == complex_no,
        PriceWatchSnapshot.article_no.notin_(seen),
    ))
    if commit:
        db.commit()
    return len(seen)


def record_snapshot_if_watched(db: Session, complex_no: str) -> None:
    """수집 완주 직후 호출 — 관심 단지일 때만 기록. 실패해도 수집 결과는 건드리지 않는다."""
    try:
        if is_watched(db, complex_no):
            n = record_snapshot(db, complex_no)
            logger.info("관심 단지 호가 기록: complex %s → %d건", complex_no, n)
    except Exception as e:
        logger.warning("관심 단지 호가 기록 실패(수집 결과는 유지): complex %s → %s", complex_no, e)
        try:
            db.rollback()
        except Exception:  # 연결이 끊겼어도 이미 끝난 수집을 실패로 덮지 않는다
            logger.warning("관심 단지 호가 기록 rollback 실패: complex %s", complex_no)


def watched_complex_nos_needing_crawl(db: Session, limit: int, stale_hours: int = 20) -> list[str]:
    """관심 단지 중 stale_hours 안에 완주 수집이 없는 단지 (오래된 순)."""
    cutoff = utcnow() - timedelta(hours=stale_hours)
    stmt = (
        select(Complex.complex_no)
        .where(
            Complex.complex_no.in_(select(PriceWatchTarget.complex_no).distinct()),
            (Complex.articles_crawled_at.is_(None)) | (Complex.articles_crawled_at < cutoff),
        )
        .order_by(Complex.articles_crawled_at.asc().nullsfirst())
        .limit(limit)
    )
    return [r[0] for r in db.execute(stmt).all()]


# ── 동일 매물 추정 키 ──────────────────────────────────────────────────

def floor_token(floor_info: str | None) -> str | None:
    tok = (floor_info or "").split("/")[0].strip()
    return tok or None


def unit_identity(article_no: str, building: str | None, floor_info: str | None,
                  area2: float | None) -> tuple[str, str]:
    """(추정 집 키, 신뢰도). 동·층·면적이 다 있어야 묶고, 아니면 매물번호 단위."""
    tok = floor_token(floor_info)
    if building and tok and area2 is not None:
        confidence = "높음" if tok.isdigit() else "보통"
        return f"{building}|{tok}|{round(area2, 1)}", confidence
    return f"article:{article_no}", "낮음"


def _matches_area(target_area: float | None, area2: float | None) -> bool:
    if target_area is None:
        return True
    return area2 is not None and abs(area2 - target_area) <= AREA_TOLERANCE_M2


def change_pct(first: float | None, last: float | None) -> float | None:
    if not first or last is None:
        return None
    return round((last - first) / first * 100, 2)


def pyeong(area_m2: float | None) -> float | None:
    return round(area_m2 / M2_TO_PYEONG, 1) if area_m2 else None


# ── 공통 로딩 ──────────────────────────────────────────────────────────

def _load_unit_prices(db: Session, targets: list[PriceWatchTarget], start: date, end: date):
    """{(complex_no, unit_key): {date: {...}}} + 단지별 기록일 목록 + 집 메타.

    한 집이 같은 날 여러 등록이면 최저가·등록 수·가격 범위를 모은다.
    """
    complex_nos = sorted({t.complex_no for t in targets})
    if not complex_nos:
        return {}, {}, {}
    areas_by_complex: dict[str, list[float | None]] = defaultdict(list)
    for t in targets:
        areas_by_complex[t.complex_no].append(t.area_m2)

    rows = db.execute(
        select(PriceWatchSnapshot).where(
            PriceWatchSnapshot.complex_no.in_(complex_nos),
            PriceWatchSnapshot.snapshot_date >= start,
            PriceWatchSnapshot.snapshot_date <= end,
        )
    ).scalars().all()

    prices: dict[tuple, dict[date, dict]] = defaultdict(dict)
    meta: dict[tuple, dict] = {}
    dates_by_complex: dict[str, set[date]] = defaultdict(set)
    for r in rows:
        dates_by_complex[r.complex_no].add(r.snapshot_date)
        if not any(_matches_area(a, r.area2_m2) for a in areas_by_complex[r.complex_no]):
            continue
        key, confidence = unit_identity(r.article_no, r.building_name, r.floor_info, r.area2_m2)
        uid = (r.complex_no, key)
        day = prices[uid].get(r.snapshot_date)
        if day is None:
            prices[uid][r.snapshot_date] = {"price": r.price, "min": r.price, "max": r.price,
                                             "listings": 1, "articles": {r.article_no}}
        else:
            day["price"] = min(day["price"], r.price)
            day["min"] = min(day["min"], r.price)
            day["max"] = max(day["max"], r.price)
            day["listings"] += 1
            day["articles"].add(r.article_no)
        meta.setdefault(uid, {
            "complex_no": r.complex_no, "building": r.building_name,
            "floor": floor_token(r.floor_info), "floor_info": r.floor_info,
            "area_m2": r.area2_m2, "supply_area_m2": r.area1_m2, "confidence": confidence,
        })
    return prices, {c: sorted(d) for c, d in dates_by_complex.items()}, meta


def _complex_names(db: Session, complex_nos) -> dict[str, str]:
    if not complex_nos:
        return {}
    return {no: name for no, name in db.execute(
        select(Complex.complex_no, Complex.complex_name).where(Complex.complex_no.in_(list(complex_nos)))
    ).all()}


# ── ① 동일 매물 추정 변동률 ───────────────────────────────────────────

def analyze_units(db: Session, targets: list[PriceWatchTarget], days: int,
                  today: date | None = None) -> dict:
    today = today or kst_date()
    start = today - timedelta(days=days)
    prices, dates_by_complex, meta = _load_unit_prices(db, targets, start, today)
    names = _complex_names(db, dates_by_complex.keys())

    units = []
    for uid, by_date in prices.items():
        m = meta[uid]
        ds = sorted(by_date)
        first, last = by_date[ds[0]], by_date[ds[-1]]
        latest_complex_date = dates_by_complex[m["complex_no"]][-1]
        series = [{"date": d.isoformat(), "price": by_date[d]["price"],
                   "min": by_date[d]["min"], "max": by_date[d]["max"],
                   "listings": by_date[d]["listings"]} for d in ds]
        moves = sum(1 for a, b in zip(series, series[1:]) if a["price"] != b["price"])
        all_prices = [p["price"] for p in series]
        units.append({
            "unit_key": uid[1], "complex_no": m["complex_no"],
            "complex_name": names.get(m["complex_no"]),
            "building": m["building"], "floor": m["floor"], "floor_info": m["floor_info"],
            "area_m2": m["area_m2"], "pyeong": pyeong(m["area_m2"]),
            "confidence": m["confidence"],
            "first_date": ds[0].isoformat(), "first_price": first["price"],
            "last_date": ds[-1].isoformat(), "last_price": last["price"],
            "change_amount": last["price"] - first["price"],
            "change_pct": change_pct(first["price"], last["price"]),
            "min_price": min(all_prices), "max_price": max(all_prices),
            "observations": len(ds), "price_moves": moves,
            "listings_now": last["listings"],
            # 그 단지의 마지막 기록일에 보였으면 아직 나와 있는 집
            "status": "active" if ds[-1] == latest_complex_date else "gone",
            "series": series,
        })
    units.sort(key=lambda u: (u["complex_name"] or "", u["building"] or "", u["floor"] or "", u["area_m2"] or 0))

    comparable = [u["change_pct"] for u in units if u["observations"] >= 2 and u["change_pct"] is not None]
    return {
        "period": {"start": start.isoformat(), "end": today.isoformat(), "days": days},
        "summary": {
            "unit_count": len(units),
            "tracked_count": len(comparable),
            "up_count": sum(1 for c in comparable if c > 0),
            "down_count": sum(1 for c in comparable if c < 0),
            "flat_count": sum(1 for c in comparable if c == 0),
            "median_change_pct": round(statistics.median(comparable), 2) if comparable else None,
            "avg_change_pct": round(statistics.fmean(comparable), 2) if comparable else None,
            "gone_count": sum(1 for u in units if u["status"] == "gone"),
        },
        "units": units,
    }


# ── ② 여러 단지 묶음 평균 변동률 ───────────────────────────────────────

def _effective_date(dates: list[date], d: date) -> date | None:
    """d 이전(포함) 가장 가까운 기록일. CARRY_FORWARD_DAYS 보다 오래되면 None."""
    eff = None
    for x in dates:
        if x <= d:
            eff = x
        else:
            break
    if eff is None or (d - eff).days > CARRY_FORWARD_DAYS:
        return None
    return eff


def _ppy(price: int, area_m2: float | None) -> float | None:
    return price / (area_m2 / M2_TO_PYEONG) if area_m2 else None


def analyze_basket(db: Session, targets: list[PriceWatchTarget], days: int,
                   today: date | None = None) -> dict:
    today = today or kst_date()
    start = today - timedelta(days=days)
    # 시작일 직전 기록으로 빈칸을 메우기 위해 CARRY_FORWARD_DAYS 앞에서부터 읽는다
    prices, dates_by_complex, meta = _load_unit_prices(
        db, targets, start - timedelta(days=CARRY_FORWARD_DAYS), today)
    names = _complex_names(db, dates_by_complex.keys())
    all_dates = sorted({d for ds in dates_by_complex.values() for d in ds if start <= d <= today})

    units_by_target: dict[int, list[tuple]] = {
        t.id: [uid for uid in prices if uid[0] == t.complex_no and _matches_area(t.area_m2, meta[uid]["area_m2"])]
        for t in targets
    }
    all_units = list(prices)
    complex_count = len({t.complex_no for t in targets})

    def value_at(uid, d):
        eff = _effective_date(dates_by_complex.get(uid[0], []), d)
        if eff is None:
            return None
        day = prices[uid].get(eff)
        return day["price"] if day else None

    def stats(uids, d):
        vals = [(value_at(u, d), meta[u]["area_m2"]) for u in uids]
        vals = [(p, a) for p, a in vals if p is not None]
        if not vals:
            return None
        ppys = [x for x in (_ppy(p, a) for p, a in vals) if x is not None]
        return {"avg_price": round(statistics.fmean(p for p, _ in vals)),
                "avg_ppy": round(statistics.fmean(ppys)) if ppys else None,
                "unit_count": len(vals)}

    series = []
    index = 100.0
    prev_d = None
    for d in all_dates:
        s = stats(all_units, d)
        if s is None:
            continue
        if prev_d is not None:
            ratios = []
            for u in all_units:
                a, b = value_at(u, prev_d), value_at(u, d)
                if a and b:
                    ratios.append(b / a)
            if ratios:
                index *= statistics.fmean(ratios)
        covered = {u[0] for u in all_units if value_at(u, d) is not None}
        series.append({"date": d.isoformat(), **s, "index": round(index, 2),
                       "complex_coverage": len(covered), "complex_count": complex_count})
        prev_d = d

    per_target = []
    for t in targets:
        t_series = []
        for d in all_dates:
            s = stats(units_by_target[t.id], d)
            if s:
                t_series.append({"date": d.isoformat(), **s})
        first, last = (t_series[0], t_series[-1]) if t_series else (None, None)
        per_target.append({
            "target_id": t.id, "complex_no": t.complex_no, "complex_name": names.get(t.complex_no),
            "area_m2": t.area_m2, "pyeong": pyeong(t.area_m2), "label": t.label,
            "first_avg_price": first and first["avg_price"], "last_avg_price": last and last["avg_price"],
            "change_pct": change_pct(first and first["avg_price"], last and last["avg_price"]),
            "ppy_change_pct": change_pct(first and first["avg_ppy"], last and last["avg_ppy"]),
            "series": t_series,
        })

    first, last = (series[0], series[-1]) if series else (None, None)
    return {
        "period": {"start": start.isoformat(), "end": today.isoformat(), "days": days},
        "summary": {
            "first_date": first and first["date"], "last_date": last and last["date"],
            "first_avg_price": first and first["avg_price"], "last_avg_price": last and last["avg_price"],
            "avg_price_change_pct": change_pct(first and first["avg_price"], last and last["avg_price"]),
            "avg_ppy_change_pct": change_pct(first and first["avg_ppy"], last and last["avg_ppy"]),
            "same_unit_index_change_pct": round(last["index"] - 100, 2) if last else None,
            "observation_days": len(series),
        },
        "series": series,
        "targets": per_target,
    }


# ── 보조: 단지 평형 목록 ───────────────────────────────────────────────

def list_complex_sale_areas(db: Session, complex_no: str) -> list[dict]:
    """단지의 활성 매매 매물 전용면적별 개수·호가 범위 (대상 등록 시 평형 고르기)."""
    area = func.round(Article.area2_m2, 1)
    rows = db.execute(
        select(area, func.avg(Article.area1_m2), func.count(), func.min(Article.numeric_price),
               func.max(Article.numeric_price))
        .where(and_(Article.complex_no == complex_no, Article.is_active == True,  # noqa: E712
                    Article.trade_type_name == TRADE_SALE, Article.area2_m2.isnot(None),
                    Article.numeric_price > 0))
        .group_by(area).order_by(area)
    ).all()
    return [{"area_m2": float(a), "pyeong": pyeong(float(a)),
             "supply_area_m2": round(float(s), 1) if s else None,
             "supply_pyeong": pyeong(float(s)) if s else None,
             "count": c, "min_price": lo, "max_price": hi} for a, s, c, lo, hi in rows]
