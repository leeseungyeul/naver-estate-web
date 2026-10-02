"""Group estimates must affect total/pagination, never delete source listings."""
import pytest
from db.models import Article


@pytest.fixture(autouse=True)
def isolate_group_complex(db):
    # conftest uses a disposable SQLite DB per pytest run, shared within that run.
    db.query(Article).filter(Article.complex_no == "C-GROUP").delete()
    db.commit()


def add(db, no, *, complex_no="C-GROUP", trade="매매", area=84.0,
        building="101동", floor: int | None=4, floor_info="4/18", price=123000,
        rent=0, direction="남향", same: int | None=3, active=True, confirmed="20261002"):
    db.add(Article(
        article_no=no, complex_no=complex_no, trade_type_name=trade,
        article_real_estate_type_name="아파트", area2_m2=area,
        building_name=building, floor_number=floor, floor_info=floor_info,
        numeric_price=price, numeric_rent_price=rent, direction=direction,
        same_addr_cnt=same, is_active=active, article_confirm_ymd=confirmed,
    ))
    db.commit()


def get(client, headers, suffix=""):
    return client.get(f"/api/complexes/C-GROUP/articles?group_duplicates=true{suffix}", headers=headers)


def test_grouped_count_and_members_across_pages(client, db, approved_headers):
    add(db, "A1", same=3)
    add(db, "A2", same=3)
    add(db, "A3", same=3)
    add(db, "B1", floor=9, floor_info="9/18", same=1)
    page1 = get(client, approved_headers, "&page_size=1&page=1")
    assert page1.status_code == 200
    d = page1.json()
    assert (d["total"], d["raw_total"], len(d["articles"])) == (2, 4, 1)
    first = d["articles"][0]
    assert first["group_count"] == 3
    assert {a["article_no"] for a in first["group_members"]} == {"A1", "A2", "A3"}
    page2 = get(client, approved_headers, "&page_size=1&page=2").json()
    assert page2["total"] == 2
    assert page2["articles"][0]["article_no"] == "B1"


def test_ambiguous_or_different_units_never_merge(client, db, approved_headers):
    """속성 완전한 등록은 시그니처별 1행(네이버식), 속성 누락분만 각각 분리.

    네이버는 같은 (동·층·면적·가격) 등록 여러 건도 대표 행 1개로 보여주므로
    A1~A5·A8은 각 시그니처 1그룹, 층 누락 A6·A7만 각각 분리된다.
    """
    add(db, "A1", same=None)
    add(db, "A2", same=None, direction="남서향")   # 방향 달라도 같은 시그니처
    add(db, "A3", same=None, area=85)
    add(db, "A4", same=None, price=124000)
    add(db, "A5", same=None, trade="전세")
    add(db, "A6", same=None, floor=None, floor_info="저/18")
    add(db, "A7", same=None, floor=None, floor_info="저/18")
    add(db, "A8", same=1)
    add(db, "A9", same=None, active=False)
    d = get(client, approved_headers).json()
    # A1+A2+A8(동일 시그니처·A8은 cnt=1이지만 속성 완전) 1 + A3 1 + A4 1 + A5 1 + A6 1 + A7 1 = 6
    assert (d["total"], d["raw_total"]) == (6, 8)
    counts = sorted(a["group_count"] for a in d["articles"])
    assert counts == [1, 1, 1, 1, 1, 3]  # A1+A2+A8 묶음 1개(3건), A3~A7 각각 분리


def test_naver_synced_signature_groups_like_naver(client, db, approved_headers):
    """sameAddrCnt>1 저장분은 네이버 시그니처(동·면적·가격)로 묶인다 — 13개 재현 경로."""
    # 같은 동·면적·가격(=같은 호실 추정)에 naver cnt=13 저장분 3행
    add(db, "N1", same=13)
    add(db, "N2", same=13)
    add(db, "N3", same=13)
    # 다른 호실(가격 다름) naver cnt=1
    add(db, "N4", same=None, price=130000)
    d = get(client, approved_headers).json()
    assert (d["total"], d["raw_total"]) == (2, 4)
    first = d["articles"][0]
    assert first["group_count"] == 3


def test_filter_before_grouping_and_sort_representative(client, db, approved_headers):
    add(db, "A1", same=2, confirmed="20261001")
    add(db, "A2", same=2, confirmed="20261002")
    add(db, "B1", floor=9, floor_info="9/18", price=120000)
    d = get(client, approved_headers, "&trade_types=매매&min_area_m2=84&max_area_m2=84&sort_by=price_asc").json()
    assert (d["total"], d["raw_total"]) == (2, 3)
    assert d["articles"][0]["article_no"] == "B1"
    assert d["articles"][1]["group_count"] == 2
    filtered = get(client, approved_headers, "&max_price=120000").json()
    assert (filtered["total"], filtered["raw_total"]) == (1, 1)


def test_different_same_addr_counts_do_not_split_same_exact_signature(client, db, approved_headers):
    add(db, "A1", same=2)
    add(db, "A2", same=3)
    d = get(client, approved_headers).json()
    assert (d["total"], d["raw_total"]) == (1, 2)
    assert d["articles"][0]["group_count"] == 2


def test_sort_by_building_groups_same_dong(client, db, approved_headers):
    add(db, "B1", building="105동", price=100000)
    add(db, "A1", building="101동", price=130000)
    add(db, "A2", building="101동", price=110000)
    d = get(client, approved_headers, "&sort_by=building_asc").json()
    assert [a["building_name"] for a in d["articles"]] == ["101동", "101동", "105동"]


def test_raw_endpoint_unchanged(client, db, approved_headers):
    add(db, "A1", same=2)
    add(db, "A2", same=2)
    d = client.get("/api/complexes/C-GROUP/articles?page_size=2", headers=approved_headers).json()
    assert d["total"] == 2
    assert len(d["articles"]) == 2
