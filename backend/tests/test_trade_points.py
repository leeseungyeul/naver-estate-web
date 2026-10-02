"""단지 실거래 개별 점 API — 월별 평균 1점이 아니라 모든 개별 실거래를 반환.

기존 get_complex_price_history는 월별 min/max/avg만 집계해 차트가 월 1점.
분포·거래량을 눈으로 확인하려면 개별 거래 가격이 필요하다(사장님 요청 2026-10-02).

공공데이터 원본에는 개별 거래가 (price)와 면적·층이 있으나 현재 버려진다.
→ ComplexPriceHistory에 개별 행 저장 방식으로 전환하지 않고(집계 행과 충돌),
  신규 테이블 complex_trade_raw (거래 1건 = 행 1건)로 저장한다.
"""
import pytest

from db.models import ComplexTradeRaw
from db.price_queries import get_complex_trade_points


@pytest.fixture(autouse=True)
def isolate(db):
    db.query(ComplexTradeRaw).filter(ComplexTradeRaw.complex_no == "C-TRADE").delete()
    db.commit()


def add(db, no, ym, price, trade="A1", area2=84.0, floor=4):
    db.add(ComplexTradeRaw(
        complex_no="C-TRADE", trade_type=trade, deal_year_month=ym,
        price=price, area2_m2=area2, floor_number=floor, source="test",
    ))
    db.commit()


def test_all_individual_trades_returned_not_averaged(db):
    add(db, "t1", "202601", 50000)
    add(db, "t2", "202601", 60000)
    add(db, "t3", "202601", 55000)
    pts = get_complex_trade_points(db, "C-TRADE")
    jan = [p for p in pts if p["year_month"] == "202601"]
    assert sorted(p["price"] for p in jan) == [50000, 55000, 60000]  # 평균 1점 아님


def test_filter_by_trade_type_and_area(db):
    add(db, "t1", "202601", 50000, trade="A1")
    add(db, "t2", "202601", 45000, trade="B1")
    add(db, "t3", "202602", 52000, trade="A1", area2=59.0)
    pts = get_complex_trade_points(db, "C-TRADE", trade_type="A1", area2_m2=84.0)
    assert [p["price"] for p in pts] == [50000]
