"""관심 단지 매매호가 추적 API (V069) — 승인 사용자 전용(B2B 게이트).

GET    /api/price-watch/targets                내 관심 대상 목록
POST   /api/price-watch/targets                대상 등록(단지 + 전용면적) → 지금 DB 상태로 첫 기록
DELETE /api/price-watch/targets/{id}           대상 삭제
GET    /api/price-watch/complexes/{no}/areas   단지 매매 평형 목록(등록 시 고르기)
GET    /api/price-watch/units?days=&target_ids=   ① 동일 매물 추정 호가 변동률
GET    /api/price-watch/basket?days=&target_ids=  ② 여러 단지 평균 호가 변동률

네이버 호출 0 — DB 기록만 읽는다. 기록은 매물 수집 완주 시 쌓인다(services/price_watch.py).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import Complex, PriceWatchSnapshot, PriceWatchTarget
from deps import get_approved_user, get_db
from services import price_watch as pw

router = APIRouter()


class TargetCreate(BaseModel):
    complex_no: str = Field(min_length=1, max_length=20, pattern=r"^\d+$")
    area_m2: float | None = Field(default=None, gt=0, lt=1000)
    label: str | None = Field(default=None, max_length=100)


def _no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


def _my_targets(db: Session, user_id: str, target_ids: str | None) -> list[PriceWatchTarget]:
    stmt = select(PriceWatchTarget).where(PriceWatchTarget.user_id == user_id)
    if target_ids:
        try:
            ids = [int(x) for x in target_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="target_ids 는 숫자를 쉼표로 이어 주세요")
        stmt = stmt.where(PriceWatchTarget.id.in_(ids))
    return list(db.execute(stmt.order_by(PriceWatchTarget.id)).scalars().all())


def _target_dict(t: PriceWatchTarget, name: str | None, coverage: tuple | None) -> dict:
    first, last, days = coverage or (None, None, 0)
    return {
        "id": t.id, "complex_no": t.complex_no, "complex_name": name,
        "area_m2": t.area_m2, "pyeong": pw.pyeong(t.area_m2), "label": t.label,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "first_snapshot": first.isoformat() if first else None,
        "last_snapshot": last.isoformat() if last else None,
        "snapshot_days": days or 0,
    }


@router.get("/targets")
def list_targets(response: Response, db: Session = Depends(get_db),
                 user: dict = Depends(get_approved_user)):
    _no_store(response)
    targets = _my_targets(db, user["user_id"], None)
    complex_nos = {t.complex_no for t in targets}
    names = pw._complex_names(db, complex_nos)
    coverage = {}
    if complex_nos:
        coverage = {row[0]: row[1:] for row in db.execute(
            select(PriceWatchSnapshot.complex_no, func.min(PriceWatchSnapshot.snapshot_date),
                   func.max(PriceWatchSnapshot.snapshot_date),
                   func.count(func.distinct(PriceWatchSnapshot.snapshot_date)))
            .where(PriceWatchSnapshot.complex_no.in_(complex_nos))
            .group_by(PriceWatchSnapshot.complex_no)
        ).all()}
    return {"targets": [_target_dict(t, names.get(t.complex_no), coverage.get(t.complex_no))
                        for t in targets],
            "max_targets": pw.MAX_TARGETS_PER_USER}


@router.post("/targets", status_code=201)
def create_target(body: TargetCreate, db: Session = Depends(get_db),
                  user: dict = Depends(get_approved_user)):
    cpx = db.get(Complex, body.complex_no)
    if cpx is None:
        raise HTTPException(status_code=404, detail="단지를 찾을 수 없습니다")
    user_id = user["user_id"]
    count = db.execute(select(func.count()).select_from(PriceWatchTarget)
                       .where(PriceWatchTarget.user_id == user_id)).scalar()
    if count >= pw.MAX_TARGETS_PER_USER:
        raise HTTPException(status_code=409,
                            detail=f"관심 대상은 최대 {pw.MAX_TARGETS_PER_USER}개까지 등록할 수 있습니다")
    area = round(body.area_m2, 1) if body.area_m2 is not None else None
    dup = select(PriceWatchTarget.id).where(PriceWatchTarget.user_id == user_id,
                                            PriceWatchTarget.complex_no == body.complex_no)
    dup = dup.where(PriceWatchTarget.area_m2.is_(None) if area is None else PriceWatchTarget.area_m2 == area)
    if db.execute(dup).first():
        raise HTTPException(status_code=409, detail="이미 등록한 단지·평형입니다")

    target = PriceWatchTarget(user_id=user_id, complex_no=body.complex_no, area_m2=area,
                              label=(body.label or "").strip() or None)
    db.add(target)
    try:
        db.commit()
    except IntegrityError:  # 동시 등록 경합 — 위 확인과 UNIQUE NULLS NOT DISTINCT 사이
        db.rollback()
        raise HTTPException(status_code=409, detail="이미 등록한 단지·평형입니다")
    db.refresh(target)

    # 첫 기록 = 지금 DB 에 있는 매물(마지막 완주 수집 날짜로). 수집 이력이 없으면 다음 수집 때부터.
    crawled_at = cpx.articles_crawled_at
    recorded = 0
    if crawled_at is not None:
        try:
            recorded = pw.record_snapshot(db, body.complex_no, pw.kst_date(crawled_at))
        except Exception:
            db.rollback()
    return {**_target_dict(target, cpx.complex_name, None), "initial_recorded": recorded}


@router.delete("/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db),
                  user: dict = Depends(get_approved_user)):
    target = db.get(PriceWatchTarget, target_id)
    if target is None or target.user_id != user["user_id"]:
        raise HTTPException(status_code=404, detail="관심 대상을 찾을 수 없습니다")
    db.delete(target)
    db.commit()
    return {"deleted": target_id}


@router.get("/complexes/{complex_no}/areas")
def complex_areas(complex_no: str, db: Session = Depends(get_db),
                  user: dict = Depends(get_approved_user)):
    cpx = db.get(Complex, complex_no)
    if cpx is None:
        raise HTTPException(status_code=404, detail="단지를 찾을 수 없습니다")
    return {"complex_no": complex_no, "complex_name": cpx.complex_name,
            "articles_crawled_at": cpx.articles_crawled_at.isoformat() if cpx.articles_crawled_at else None,
            "areas": pw.list_complex_sale_areas(db, complex_no)}


@router.get("/units")
def units(response: Response, days: int = Query(90, ge=7, le=730), target_ids: str | None = None,
          db: Session = Depends(get_db), user: dict = Depends(get_approved_user)):
    _no_store(response)
    return pw.analyze_units(db, _my_targets(db, user["user_id"], target_ids), days)


@router.get("/basket")
def basket(response: Response, days: int = Query(90, ge=7, le=730), target_ids: str | None = None,
           db: Session = Depends(get_db), user: dict = Depends(get_approved_user)):
    _no_store(response)
    return pw.analyze_basket(db, _my_targets(db, user["user_id"], target_ids), days)
