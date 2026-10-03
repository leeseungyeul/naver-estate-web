"""GET /api/complexes/{no}/trade-points — 개별 실거래 점 엔드포인트.

승인 중개사 전용(price-history 게이트 답습), 월별 평균이 아니라 거래 1건 = 점 1건.
"""
import pytest

from db.models import ComplexTradeRaw


@pytest.fixture(autouse=True)
def isolate(db):
    db.query(ComplexTradeRaw).filter(ComplexTradeRaw.complex_no == "C-TP").delete()
    db.commit()


def _add_points(db):
    db.add(ComplexTradeRaw(
        complex_no="C-TP", trade_type="A1", deal_year_month="202601",
        deal_day="15", price=50000, area2_m2=84.0, floor_number=4, source="test",
    ))
    db.add(ComplexTradeRaw(
        complex_no="C-TP", trade_type="A1", deal_year_month="202601",
        deal_day="20", price=62000, area2_m2=84.0, floor_number=10, source="test",
    ))
    db.commit()


def test_trade_points_200_all_individual(client, db, approved_headers):
    """개별 거래가 모두 점으로 반환된다 (월 평균 1점 아님)"""
    _add_points(db)
    res = client.get("/api/complexes/C-TP/trade-points", headers=approved_headers)
    assert res.status_code == 200
    prices = sorted(p["price"] for p in res.json()["points"])
    assert prices == [50000, 62000]


def test_trade_points_requires_approval(client, db):
    """미승인 → 401/403 (price-history B2 게이트 답습)"""
    _add_points(db)
    res = client.get("/api/complexes/C-TP/trade-points")
    assert res.status_code in (401, 403)


def test_trade_points_empty_complex_200_empty(client, db, approved_headers):
    res = client.get("/api/complexes/NO-SUCH/trade-points", headers=approved_headers)
    assert res.status_code == 200
    assert res.json()["points"] == []
