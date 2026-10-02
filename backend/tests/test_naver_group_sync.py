"""naver_group_sync 단위 테스트 — 네이버 그룹 모드 sameAddrCnt를 원본에 기록.

네트워크 호출은 NaverEstateAPI를 monkeypatch로 차단한다(실호출 0).
실행: .venv/bin/python -m pytest tests/test_naver_group_sync.py -q
"""
from types import SimpleNamespace

import pytest

from db.models import Article
from services import naver_group_sync


@pytest.fixture(autouse=True)
def isolate(db):
    db.query(Article).filter(Article.complex_no == "C-SYNC").delete()
    db.commit()


def add(db, no, *, building="101동", prc="12억 3,000", trade="매매", same=None,
        floor_info="4/18", area2=84.0):
    a = Article(
        article_no=no, complex_no="C-SYNC", trade_type_name=trade,
        article_real_estate_type_name="아파트", building_name=building,
        deal_or_warrant_prc=prc, is_active=True, same_addr_cnt=same,
        floor_info=floor_info, area2_m2=area2,
    )
    db.add(a)
    db.commit()
    return a


def patch_api(monkeypatch, pages):
    """pages: 페이지별 articleList. 호출된 same_address_group 플래그를 기록."""
    calls = []

    class FakeAPI:
        @classmethod
        def get_complex_articles(cls, complex_id, page=1, same_address_group=False):
            calls.append({"complex": complex_id, "page": page, "grouped": same_address_group})
            if page <= len(pages):
                return {"articleList": pages[page - 1], "isMoreData": page < len(pages)}
            return {"articleList": [], "isMoreData": False}

    monkeypatch.setattr(naver_group_sync, "NaverEstateAPI", FakeAPI)
    return calls


def test_group_flag_used_and_counts_saved(db, monkeypatch):
    add(db, "A1", same=1)
    calls = patch_api(monkeypatch, [[
        {"buildingName": "101동", "dealOrWarrantPrc": "12억 3,000",
         "tradeTypeName": "매매", "sameAddrCnt": 26,
         "floorInfo": "4/18", "area2": 84.0},
    ]])
    r = naver_group_sync.update_same_addr_counts_from_naver(db, "C-SYNC")
    assert calls[0]["grouped"] is True
    assert (r["groups"], r["matched"], r["unmatched"]) == (1, 1, 0)
    assert db.query(Article).filter_by(article_no="A1").one().same_addr_cnt == 26


def test_same_key_rows_all_get_count(db, monkeypatch):
    add(db, "A1", same=1)
    add(db, "A2", same=1)
    patch_api(monkeypatch, [[
        {"buildingName": "101동", "dealOrWarrantPrc": "12억 3,000",
         "tradeTypeName": "매매", "sameAddrCnt": 24,
         "floorInfo": "4/18", "area2": 84.0},
    ]])
    r = naver_group_sync.update_same_addr_counts_from_naver(db, "C-SYNC")
    assert r["matched"] == 2
    assert [a.same_addr_cnt for a in db.query(Article).order_by(Article.article_no).all()] == [24, 24]


def test_later_smaller_count_does_not_overwrite(db, monkeypatch):
    """같은 키 대표 여러 건(cnt 26 뒤 cnt 1) — 최댓값 유지, 뒤 행이 덮지 않음(실측 회귀 가드)."""
    add(db, "A1", same=None)
    patch_api(monkeypatch, [[
        {"buildingName": "101동", "dealOrWarrantPrc": "12억 3,000",
         "tradeTypeName": "매매", "sameAddrCnt": 26,
         "floorInfo": "4/18", "area2": 84.0},
        {"buildingName": "101동", "dealOrWarrantPrc": "12억 3,000",
         "tradeTypeName": "매매", "sameAddrCnt": 1,
         "floorInfo": "4/18", "area2": 84.0},
    ]])
    naver_group_sync.update_same_addr_counts_from_naver(db, "C-SYNC")
    assert db.query(Article).filter_by(article_no="A1").one().same_addr_cnt == 26


def test_different_area_or_floor_not_overwritten(db, monkeypatch):
    """같은 동·가격이라도 면적·층이 다르면 별도 묶음 — 실측(26 vs 1 공존) 회귀 가드."""
    add(db, "A1", same=1)                                # 4/18, 84㎡
    add(db, "A2", same=1, floor_info="저/18", area2=84.0)  # 층 미상
    add(db, "A3", same=1, floor_info="4/18", area2=59.0)   # 면적 다름
    patch_api(monkeypatch, [[
        {"buildingName": "101동", "dealOrWarrantPrc": "12억 3,000",
         "tradeTypeName": "매매", "sameAddrCnt": 26,
         "floorInfo": "4/18", "area2": 84.0},
    ]])
    r = naver_group_sync.update_same_addr_counts_from_naver(db, "C-SYNC")
    assert (r["matched"], r["unmatched"]) == (1, 0)
    got = {a.article_no: a.same_addr_cnt for a in db.query(Article).all()}
    assert got == {"A1": 26, "A2": 1, "A3": 1}


def test_unmatched_group_counted_not_crash(db, monkeypatch):
    add(db, "A1")
    patch_api(monkeypatch, [[
        {"buildingName": "999동", "dealOrWarrantPrc": "9억",
         "tradeTypeName": "매매", "sameAddrCnt": 3},
        {"buildingName": "101동", "dealOrWarrantPrc": "12억 3,000",
         "tradeTypeName": "매매", "sameAddrCnt": 0},
    ]])
    r = naver_group_sync.update_same_addr_counts_from_naver(db, "C-SYNC")
    assert r["unmatched"] == 1
    assert db.query(Article).filter_by(article_no="A1").one().same_addr_cnt is None
