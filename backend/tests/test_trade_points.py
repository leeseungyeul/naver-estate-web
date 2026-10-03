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


def test_mixed_type_apt_dong_does_not_break_batch_insert(db):
    """aptDong 혼합 타입(정수+문자) 배치 INSERT — PG 타입 추론 오류 방지.

    국토부 API는 aptDong을 숫자는 int('108'), 문자는 str('C','아파트')로 섞어 준다.
    insertmanyvalues가 첫 행 값으로 컬럼 타입을 추론해 첫 행이 정수면 이후
    문자열 행에서 DataError 가 난다(2026-10-03 파크리오 소급 실측). 모든
    apt_dong 이 문자열로 바인딩되어야 한다.
    """
    add(db, "t1", "202601", 50000)  # aptDong 없음
    import crawler.service_public as sp

    trades = [
        {"aptNm": "가단지", "dealAmount": "50000", "dealDay": "1", "excluUseAr": "84.0", "floor": "4", "aptDong": 108},
        {"aptNm": "나단지", "dealAmount": "60000", "dealDay": "2", "excluUseAr": "84.0", "floor": "5", "aptDong": "C"},
        {"aptNm": "다단지", "dealAmount": "70000", "dealDay": "3", "excluUseAr": "84.0", "floor": "6"},
    ]
    sp.save_trade_raw_rows(db, trades, "202601", {"가단지": "C-TRADE", "나단지": "C-TRADE", "다단지": "C-TRADE"})
    rows = db.query(ComplexTradeRaw).filter(ComplexTradeRaw.complex_no == "C-TRADE").all()
    dongs = {r.price: r.apt_dong for r in rows}
    assert dongs[50000] == "108"  # int → str 정규화
    assert dongs[60000] == "C"    # str 유지
    assert dongs[70000] is None   # 없음 → None


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
