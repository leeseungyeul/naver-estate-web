"""관심 단지 매매호가 추적 (V069) — 기록·동일 매물 추정 변동률·묶음 평균 변동률·API·수집 연동."""

from datetime import date, timedelta

from db.models import Article, Complex, PriceWatchSnapshot, PriceWatchTarget
from services import price_watch as pw
from tests.conftest import make_auth_headers
from utils import utcnow

D1, D2, D3 = date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 15)
TODAY = date(2026, 9, 20)


# ── 팩토리 ──
def make_complex(db, no="1001", name="테스트단지", crawled_hours_ago=None):
    c = Complex(complex_no=no, complex_name=name)
    if crawled_hours_ago is not None:
        c.articles_crawled_at = utcnow() - timedelta(hours=crawled_hours_ago)
    db.add(c)
    db.commit()
    return c


def make_article(db, no, complex_no="1001", price=100000, trade="매매", building="101동",
                 floor="12/25", area2=84.9, area1=112.0, active=True):
    db.add(Article(article_no=no, complex_no=complex_no, trade_type_name=trade,
                   building_name=building, floor_info=floor, area2_m2=area2, area1_m2=area1,
                   numeric_price=price, is_active=active))
    db.commit()


def snap(db, d, article_no, price, complex_no="1001", building="101동", floor="12/25", area2=84.9):
    db.add(PriceWatchSnapshot(snapshot_date=d, complex_no=complex_no, article_no=article_no,
                              building_name=building, floor_info=floor, area2_m2=area2,
                              area1_m2=112.0, price=price))
    db.commit()


def target(db, complex_no="1001", area=84.9, user_id="approved-user"):
    t = PriceWatchTarget(user_id=user_id, complex_no=complex_no, area_m2=area)
    db.add(t)
    db.commit()
    return t


# ── 추정 키 ──
def test_unit_identity_confidence_levels():
    """층이 숫자면 높음, 고/중/저면 보통, 동·층·면적 중 결측이면 매물번호 단위(낮음)."""
    assert pw.unit_identity("a", "101동", "12/25", 84.94)[1] == "높음"
    assert pw.unit_identity("a", "101동", "12/25", 84.94)[0] == "101동|12|84.9"
    assert pw.unit_identity("a", "101동", "고/25", 84.9)[1] == "보통"
    assert pw.unit_identity("a", None, "12/25", 84.9) == ("article:a", "낮음")


def test_change_pct_rejects_zero_or_missing_base():
    """첫 값이 0·결측이면 변동률을 지어내지 않는다."""
    assert pw.change_pct(100, 95) == -5.0
    assert pw.change_pct(0, 95) is None
    assert pw.change_pct(None, 95) is None


# ── 기록 ──
def test_record_snapshot_keeps_only_active_sale_and_drops_same_day_stale(db):
    """활성 매매만 기록하고, 같은 날 이전 기록 중 지금 목록에 없는 매물은 지운다."""
    make_complex(db)
    make_article(db, "a1", price=100000)
    make_article(db, "a2", trade="전세", price=50000)
    make_article(db, "a3", active=False)
    snap(db, D1, "old", 90000)  # 같은 날 앞선 수집에만 있던 매물

    n = pw.record_snapshot(db, "1001", D1)

    rows = db.query(PriceWatchSnapshot).filter_by(snapshot_date=D1).all()
    assert n == 1
    assert [r.article_no for r in rows] == ["a1"]


def test_record_snapshot_if_watched_noop_when_not_watched(db):
    make_complex(db)
    make_article(db, "a1")
    pw.record_snapshot_if_watched(db, "1001")
    assert db.query(PriceWatchSnapshot).count() == 0
    target(db)
    pw.record_snapshot_if_watched(db, "1001")
    assert db.query(PriceWatchSnapshot).count() == 1


# ── ① 동일 매물 추정 변동률 ──
def test_units_merge_relisted_article_and_take_lowest_ask(db):
    """매물번호가 바뀐 재등록·여러 중개사 동시 등록을 한 집으로 묶고, 그날 최저가를 쓴다."""
    make_complex(db)
    t = target(db)
    snap(db, D1, "a1", 100000)
    snap(db, D1, "a2", 102000)          # 같은 집, 다른 중개사
    snap(db, D2, "a3", 97000)           # 같은 집, 내렸다 다시 올림(새 매물번호)
    snap(db, D3, "a3", 95000)

    r = pw.analyze_units(db, [t], days=60, today=TODAY)

    assert r["summary"]["unit_count"] == 1
    u = r["units"][0]
    assert u["first_price"] == 100000 and u["last_price"] == 95000
    assert u["change_pct"] == -5.0
    assert u["series"][0]["listings"] == 2 and u["series"][0]["max"] == 102000
    assert u["price_moves"] == 2
    assert r["summary"]["down_count"] == 1


def test_units_mark_gone_and_filter_by_area(db):
    """그 단지 마지막 기록일에 안 보이면 gone. 다른 평형은 대상에서 빠진다."""
    make_complex(db)
    t = target(db, area=84.9)
    snap(db, D1, "a1", 100000, floor="3/25")
    snap(db, D1, "b1", 70000, area2=59.9)         # 다른 평형
    snap(db, D2, "a2", 110000, floor="7/25")      # D2 에 a1 집은 사라짐

    r = pw.analyze_units(db, [t], days=60, today=TODAY)

    status = {u["floor"]: u["status"] for u in r["units"]}
    assert status == {"3": "gone", "7": "active"}
    assert r["summary"]["gone_count"] == 1
    assert r["summary"]["tracked_count"] == 0  # 두 번 이상 관측된 집 없음


# ── ② 묶음 평균 변동률 ──
def test_basket_index_ignores_composition_change(db):
    """비싼 집이 새로 나오면 평균은 오르지만, 같은 집끼리 비교한 지수는 그대로다."""
    make_complex(db)
    t = target(db)
    snap(db, D1, "a1", 100000, floor="3/25")
    snap(db, D2, "a1", 100000, floor="3/25")
    snap(db, D2, "a2", 200000, floor="20/25")     # 새로 등장

    r = pw.analyze_basket(db, [t], days=60, today=TODAY)

    s = r["summary"]
    assert s["avg_price_change_pct"] == 50.0
    assert s["same_unit_index_change_pct"] == 0.0


def test_basket_index_tracks_same_unit_cut(db):
    make_complex(db)
    t = target(db)
    snap(db, D1, "a1", 100000, floor="3/25")
    snap(db, D1, "a2", 200000, floor="5/25")
    snap(db, D2, "a1", 90000, floor="3/25")       # -10%
    snap(db, D2, "a2", 200000, floor="5/25")      # 0%

    r = pw.analyze_basket(db, [t], days=60, today=TODAY)

    assert r["summary"]["same_unit_index_change_pct"] == -5.0
    assert r["summary"]["avg_price_change_pct"] == round((145000 - 150000) / 150000 * 100, 2)


def test_basket_carries_forward_complex_without_same_day_record(db):
    """단지 B 가 D2 에 수집되지 않았으면 D1 기록을 이어 써서 평균에 구멍이 나지 않는다."""
    make_complex(db, "1001", "A")
    make_complex(db, "2002", "B")
    ta, tb = target(db, "1001"), target(db, "2002")
    snap(db, D1, "a1", 100000, complex_no="1001")
    snap(db, D1, "b1", 300000, complex_no="2002")
    snap(db, D2, "a1", 110000, complex_no="1001")

    r = pw.analyze_basket(db, [ta, tb], days=60, today=TODAY)

    last = r["series"][-1]
    assert last["date"] == D2.isoformat()
    assert last["unit_count"] == 2 and last["complex_coverage"] == 2
    assert last["avg_price"] == 205000
    by_cpx = {x["complex_name"]: x["change_pct"] for x in r["targets"]}
    assert by_cpx == {"A": 10.0, "B": 0.0}


def test_basket_empty_when_no_records(db):
    make_complex(db)
    r = pw.analyze_basket(db, [target(db)], days=30, today=TODAY)
    assert r["series"] == [] and r["summary"]["avg_price_change_pct"] is None


# ── 인기 단지 선정 연동 ──
def test_popular_selection_puts_stale_watched_complex_first(db):
    from db.complex_queries import get_complexes_for_popular_crawl

    viewed = make_complex(db, "1001", "최근조회", crawled_hours_ago=1)
    viewed.last_viewed_at = utcnow()
    make_complex(db, "2002", "관심(오래됨)", crawled_hours_ago=30)
    make_complex(db, "3003", "관심(신선)", crawled_hours_ago=2)
    db.commit()
    target(db, "2002")
    target(db, "3003")

    picked = [c.complex_no for c in get_complexes_for_popular_crawl(db, limit=2)]

    assert picked == ["2002", "1001"]


# ── API ──
def test_api_requires_approved_user(client, db):
    assert client.get("/api/price-watch/targets").status_code in (401, 403)
    pending = make_auth_headers(db, user_id="pending-user", status="pending")
    assert client.get("/api/price-watch/targets", headers=pending).status_code == 403


def test_api_target_lifecycle(client, db, approved_headers):
    make_complex(db, crawled_hours_ago=3)
    make_article(db, "a1")

    r = client.post("/api/price-watch/targets", json={"complex_no": "1001", "area_m2": 84.94},
                    headers=approved_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["area_m2"] == 84.9 and body["initial_recorded"] == 1

    dup = client.post("/api/price-watch/targets", json={"complex_no": "1001", "area_m2": 84.9},
                      headers=approved_headers)
    assert dup.status_code == 409

    missing = client.post("/api/price-watch/targets", json={"complex_no": "9999"}, headers=approved_headers)
    assert missing.status_code == 404

    lst = client.get("/api/price-watch/targets", headers=approved_headers)
    assert lst.headers["cache-control"] == "no-store"
    assert [x["complex_name"] for x in lst.json()["targets"]] == ["테스트단지"]
    assert lst.json()["targets"][0]["snapshot_days"] == 1

    units = client.get("/api/price-watch/units?days=30", headers=approved_headers)
    assert units.status_code == 200 and units.json()["summary"]["unit_count"] == 1
    basket = client.get(f"/api/price-watch/basket?days=30&target_ids={body['id']}", headers=approved_headers)
    assert basket.status_code == 200 and len(basket.json()["targets"]) == 1

    other = make_auth_headers(db, user_id="other-user")
    assert client.delete(f"/api/price-watch/targets/{body['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/price-watch/targets/{body['id']}", headers=approved_headers).status_code == 200
    assert db.query(PriceWatchTarget).count() == 0


def test_api_rejects_bad_target_ids(client, db, approved_headers):
    r = client.get("/api/price-watch/units?target_ids=abc", headers=approved_headers)
    assert r.status_code == 422


def test_api_complex_areas(client, db, approved_headers):
    make_complex(db)
    make_article(db, "a1", price=100000, area2=84.94)
    make_article(db, "a2", price=120000, area2=84.91, building="102동")
    make_article(db, "a3", price=70000, area2=59.9)
    r = client.get("/api/price-watch/complexes/1001/areas", headers=approved_headers)
    assert r.status_code == 200
    areas = {a["area_m2"]: a for a in r.json()["areas"]}
    assert areas[84.9]["count"] == 2 and areas[84.9]["max_price"] == 120000
    assert areas[59.9]["count"] == 1


def test_popular_selection_survives_missing_watch_table(db, monkeypatch):
    """V069 표가 아직 없는 DB(코드 먼저 배포)여도 인기 갱신 선정은 원래대로 돈다."""
    from db import complex_queries

    viewed = make_complex(db, "1001", "최근조회", crawled_hours_ago=1)
    viewed.last_viewed_at = utcnow()
    db.commit()

    def boom(*_a, **_k):
        raise RuntimeError("relation price_watch_targets does not exist")

    monkeypatch.setattr("services.price_watch.watched_complex_nos_needing_crawl", boom)
    picked = [c.complex_no for c in complex_queries.get_complexes_for_popular_crawl(db, limit=2)]
    assert picked == ["1001"]


def test_record_snapshot_empty_list_keeps_same_day_records(db):
    """빈 목록(네이버 일시 오류 가능)은 그날 앞선 정상 기록을 지우지 않는다."""
    make_complex(db)
    snap(db, D1, "a1", 100000)
    assert pw.record_snapshot(db, "1001", D1) == 0
    assert db.query(PriceWatchSnapshot).count() == 1


def test_popular_selection_caps_watched_share_at_half(db):
    from db.complex_queries import get_complexes_for_popular_crawl

    viewed = make_complex(db, "1001", "최근조회", crawled_hours_ago=1)
    viewed.last_viewed_at = utcnow()
    for no in ("2002", "3003"):
        make_complex(db, no, f"관심{no}", crawled_hours_ago=30)
        target(db, no)
    db.commit()

    picked = [c.complex_no for c in get_complexes_for_popular_crawl(db, limit=2)]
    assert picked == ["2002", "1001"]
