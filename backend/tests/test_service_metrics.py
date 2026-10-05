"""crawler/service_metrics.py 통합 테스트

collect_complex_metrics 검증 — 정상 단지 / 전세 데이터 결함 단지 / 빈 단지.
SessionLocal 은 conftest 가 TestSession 으로 교체하므로 별도 mock 불필요.
"""

from datetime import date

from db.models import Complex, ComplexPriceHistory
from services.upsert import upsert_complex_from_search


def _recent_month() -> str:
    return date.today().strftime("%Y%m")


def _make_complex(complex_no: str) -> dict:
    return {
        "complexNo": complex_no,
        "complexName": f"지표테스트{complex_no}",
        "cortarNo": "1168010100",
        "realEstateTypeCode": "APT",
    }


def _add_price(db, complex_no, trade_type, price_avg):
    db.add(
        ComplexPriceHistory(
            complex_no=complex_no,
            trade_type=trade_type,
            area_no=None,
            price_upper=price_avg + 10000,
            price_lower=price_avg - 10000,
            price_avg=price_avg,
            base_month=_recent_month(),
        )
    )


class TestCollectComplexMetrics:
    def test_normal_complex_filled(self, db):
        """정상: 전세 < 매매 단지 → 3필드 모두 채워짐."""
        upsert_complex_from_search(db, _make_complex("70001"))
        for p in (300000, 310000, 320000):
            _add_price(db, "70001", "A1", p)
        for p in (200000, 210000, 220000):  # 전세 < 매매
            _add_price(db, "70001", "B1", p)
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        c = db.query(Complex).filter(Complex.complex_no == "70001").first()
        assert c.nearby_median_price == 310000
        assert c.jeonse_rate == 67.7  # 210000/310000*100
        assert c.recent_trades_6m == 3

    def test_jeonse_defect_guard(self, db):
        """결함: 전세 median == 매매 median → jeonse_rate 는 NULL 유지."""
        upsert_complex_from_search(db, _make_complex("70002"))
        for p in (31000, 31000, 31000):
            _add_price(db, "70002", "A1", p)
        for p in (31000, 31000, 31000):  # 매매와 동일값 = 결함
            _add_price(db, "70002", "B1", p)
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        c = db.query(Complex).filter(Complex.complex_no == "70002").first()
        assert c.nearby_median_price == 31000  # 매매중앙값은 채워짐
        assert c.jeonse_rate is None  # 결함 데이터 → NULL

    def test_no_price_history_skipped(self, db):
        """빈 데이터: 시세 이력 없는 단지 → NULL 유지 (건너뜀)."""
        upsert_complex_from_search(db, _make_complex("70003"))
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        c = db.query(Complex).filter(Complex.complex_no == "70003").first()
        assert c.nearby_median_price is None


def _add_old_price(db, complex_no, price_avg):
    """6개월 계산 창 밖(2년 전) 매매 이력 — 중앙값 계산에는 안 쓰인다."""
    db.add(
        ComplexPriceHistory(
            complex_no=complex_no,
            trade_type="A1",
            area_no=None,
            price_upper=price_avg,
            price_lower=price_avg,
            price_avg=price_avg,
            base_month=f"{date.today().year - 2}01",
        )
    )


def _set_households(db, complex_no, hh):
    db.query(Complex).filter(Complex.complex_no == complex_no).update(
        {Complex.total_household_count: hh}, synchronize_session=False
    )


def _last_metric_job(db):
    from db.models import CrawlJob

    return (
        db.query(CrawlJob)
        .filter(CrawlJob.job_type == "complex_metric")
        .order_by(CrawlJob.id.desc())
        .first()
    )


class TestMetricCandidateSelection:
    """세션 428: 옛 매매 이력만 있는 큰 단지가 배치 자리를 차지해 계산 가능한 작은 단지가 굶던 결함."""

    def test_old_only_big_complexes_do_not_starve_small_fillable(self, db):
        # 큰 단지 3곳 = 2년 전 매매만 있음(계산 불가) · 작은 단지 1곳 = 최근 매매 있음(계산 가능)
        for no, hh in (("71001", 3000), ("71002", 2000), ("71003", 1000)):
            upsert_complex_from_search(db, _make_complex(no))
            _set_households(db, no, hh)
            _add_old_price(db, no, 500000)
        upsert_complex_from_search(db, _make_complex("71009"))
        _set_households(db, "71009", 30)
        _add_price(db, "71009", "A1", 200000)
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=2)  # 큰 단지 수(3)보다 작은 배치

        small = db.query(Complex).filter(Complex.complex_no == "71009").first()
        assert small.nearby_median_price == 200000
        job = _last_metric_job(db)
        assert job.status == "completed"
        assert job.total_items == 1  # 옛 이력 단지는 후보에서 빠진다
        assert job.processed_items == 1

    def test_only_old_history_gives_empty_batch_not_spinning(self, db):
        # 계산할 수 있는 단지가 없으면 대상 0 — 처리 0/대상 N 헛바퀴 기록을 남기지 않는다
        upsert_complex_from_search(db, _make_complex("71011"))
        _set_households(db, "71011", 500)
        _add_old_price(db, "71011", 400000)
        _add_filler(db, "71019")  # 세션 428: 최근 줄 0건이면 잡이 failed 로 멈추므로 채움 단지 1곳
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        c = db.query(Complex).filter(Complex.complex_no == "71011").first()
        assert c.nearby_median_price is None
        job = _last_metric_job(db)
        assert job.status == "completed"
        assert job.total_items == 1  # 채움 단지만 — 옛 이력 단지는 대상이 아니다
        assert job.processed_items == 1

    def test_seven_months_old_only_is_not_candidate(self, db):
        # 6개월 창 바로 밖(7개월 전) 줄만 있는 단지 — 기간을 6→12 로 넓히는 변이를 잡는다
        from datetime import timedelta

        upsert_complex_from_search(db, _make_complex("71031"))
        _set_households(db, "71031", 900)
        seven_months_ago = (date.today() - timedelta(days=7 * 31)).strftime("%Y%m")
        db.add(
            ComplexPriceHistory(
                complex_no="71031", trade_type="A1", area_no=None,
                price_upper=300000, price_lower=300000, price_avg=300000, base_month=seven_months_ago,
            )
        )
        _add_filler(db, "71039")  # 세션 428: 최근 줄 0건이면 잡이 failed 로 멈추므로 채움 단지 1곳
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        job = _last_metric_job(db)
        assert job.status == "completed"
        assert job.total_items == 1  # 채움 단지만
        assert job.processed_items == 1

    def test_cutoff_month_row_is_candidate_and_filled(self, db):
        # 경계: 기준 달과 같은 달 줄은 계산에 쓰이므로 후보로도 뽑혀야 한다(>= 를 > 로 바꾸는 변이를 잡는다)
        from crawler.metrics_helpers import _cutoff_month

        upsert_complex_from_search(db, _make_complex("71041"))
        _set_households(db, "71041", 700)
        db.add(
            ComplexPriceHistory(
                complex_no="71041", trade_type="A1", area_no=None,
                price_upper=250000, price_lower=250000, price_avg=250000, base_month=_cutoff_month(6),
            )
        )
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        c = db.query(Complex).filter(Complex.complex_no == "71041").first()
        assert c.nearby_median_price == 250000
        job = _last_metric_job(db)
        assert job.total_items == 1
        assert job.processed_items == 1

    def test_recent_rows_without_price_avg_are_not_candidates(self, db):
        # 최근 매매 줄이 있어도 평균가가 비어 있으면 중앙값을 못 낸다 — 후보에서도 빠져야 헛바퀴가 없다
        upsert_complex_from_search(db, _make_complex("71021"))
        _set_households(db, "71021", 800)
        db.add(
            ComplexPriceHistory(
                complex_no="71021", trade_type="A1", area_no=None,
                price_upper=None, price_lower=None, price_avg=None, base_month=_recent_month(),
            )
        )
        _add_filler(db, "71029")  # 세션 428: 최근 평균가 0건이면 잡이 failed 로 멈추므로 채움 단지 1곳
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        job = _last_metric_job(db)
        assert job.status == "completed"
        assert job.total_items == 1  # 채움 단지만
        assert job.processed_items == 1


# ── 세션 428: 매일 전부 다시 계산 (최근 6개월 매매 없는 단지는 마지막 값 유지) ──────────────


def _add_row(db, complex_no, trade_type, price_avg, base_month=None):
    """시세 이력 한 줄. price_avg=None 이면 평균가 빈 줄, base_month 생략 시 이번 달."""
    db.add(
        ComplexPriceHistory(
            complex_no=complex_no,
            trade_type=trade_type,
            area_no=None,
            price_upper=price_avg,
            price_lower=price_avg,
            price_avg=price_avg,
            base_month=base_month or _recent_month(),
        )
    )


def _add_filler(db, complex_no, hh=1):
    """최근 매매 평균가가 있는 채움 단지 — '최근 줄 0건이면 아무것도 안 쓴다' 안전장치를 비켜
    다른 단지의 판정만 보려는 시험용. 세대수를 작게 둬 배치 순서에서 뒤로 간다."""
    upsert_complex_from_search(db, _make_complex(complex_no))
    _set_households(db, complex_no, hh)
    _add_row(db, complex_no, "A1", 123000)


def _set_metrics(db, complex_no, median, rate, recent, updated_at=None):
    values = {
        Complex.nearby_median_price: median,
        Complex.jeonse_rate: rate,
        Complex.recent_trades_6m: recent,
    }
    if updated_at is not None:
        values[Complex.updated_at] = updated_at
    db.query(Complex).filter(Complex.complex_no == complex_no).update(values, synchronize_session=False)


def _metrics(db, complex_no):
    db.expire_all()
    c = db.query(Complex).filter(Complex.complex_no == complex_no).first()
    return (c.nearby_median_price, c.jeonse_rate, c.recent_trades_6m)


def _old_month() -> str:
    return f"{date.today().year - 2}01"


def _months_ago(n: int) -> str:
    """n×31일 전의 YYYYMM — _cutoff_month(n) 과 같은 계산(그 달 줄은 n개월 창 안, n-1개월 창 밖)."""
    from datetime import timedelta

    return (date.today() - timedelta(days=n * 31)).strftime("%Y%m")


class TestMetricRecomputeAll:
    def test_filled_value_is_recomputed(self, db):
        # 항목 1: 이미 채워진 낡은 값도 매일 다시 계산된다(옛 코드는 NULL 단지만 봤다)
        upsert_complex_from_search(db, _make_complex("72101"))
        _set_metrics(db, "72101", 100000, 50.0, 1)
        for p in (190000, 200000, 210000):
            _add_row(db, "72101", "A1", p)
        _add_row(db, "72101", "B1", 120000)
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        assert _metrics(db, "72101") == (200000, 60.0, 3)

    def test_no_recent_sale_keeps_last_values(self, db):
        # 10-03 사장님 결정: 최근 6개월 매매(평균가 있는 줄)가 없는 단지는 읽지도 쓰지도 않는다 —
        # 저장값·updated_at 그대로(3월 일괄 수집분만 있는 단지 약 8천 곳이 기준 달이 넘어가는 날 비지 않게)
        from datetime import datetime, timezone

        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        for no in ("72201", "72202"):
            upsert_complex_from_search(db, _make_complex(no))
        _set_metrics(db, "72201", 300000, 70.0, 4, updated_at=old)
        _add_row(db, "72201", "A1", 300000, _old_month())  # 2년 전 매매만
        _add_row(db, "72201", "B1", 200000)  # 최근 전세만 있음
        _set_metrics(db, "72202", 150000, None, 2, updated_at=old)
        _add_row(db, "72202", "A1", None)  # 최근 매매가 평균가 빈 줄뿐
        _add_filler(db, "72209")
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=0)

        assert _metrics(db, "72201") == (300000, 70.0, 4)
        assert _metrics(db, "72202") == (150000, None, 2)
        for no in ("72201", "72202"):
            assert db.query(Complex).filter(Complex.complex_no == no).first().updated_at.year == 2020
        job = _last_metric_job(db)
        assert job.status == "completed"
        assert (job.total_items, job.processed_items) == (1, 1)  # 채움 단지만 대상

    def test_same_result_as_per_complex_helpers(self, db):
        # 항목 3: 한 번에 읽는 새 경로 == 옛 단지별 헬퍼(중앙값·전세 가드·전세가율·거래 수)
        from crawler.metrics_helpers import calc_median_price, count_recent_price_records
        from crawler.stats import compute_jeonse_rate

        nos = ("72301", "72302", "72303")
        for no in nos:
            upsert_complex_from_search(db, _make_complex(no))
        for p in (300000, 330000, 310000, 320000):  # 짝수 개 → 가운데 둘 평균
            _add_row(db, "72301", "A1", p)
        _add_row(db, "72301", "A1", None)  # 평균가 빈 줄: 거래 수엔 들어가고 중앙값엔 안 들어감
        _add_row(db, "72301", "A1", 900000, _old_month())  # 기간 밖
        _add_row(db, "72301", "A1", 999000, _months_ago(7))  # 기간 바로 밖(7개월 전) — 읽기 기간을 넓히는 변이를 잡는다
        for p in (200000, 220000):
            _add_row(db, "72301", "B1", p)
        _add_row(db, "72301", "B1", None)
        for p in (100001, 100002):  # 가운데 둘 합이 홀수 → //2
            _add_row(db, "72302", "A1", p)
        _add_row(db, "72302", "B1", 150000)  # 전세 >= 매매 → 전세가율 NULL
        _add_row(db, "72303", "A1", 50000)
        _add_row(db, "72303", "A1", None)
        _add_row(db, "72303", "A1", None)
        db.commit()

        expected = {}
        for no in nos:
            median = calc_median_price(db, no, "A1", months=6)
            jeonse = calc_median_price(db, no, "B1", months=6)
            if jeonse is not None and jeonse >= median:
                jeonse = None
            expected[no] = (median, compute_jeonse_rate(median, jeonse), count_recent_price_records(db, no, months=6))

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=100)

        for no in nos:
            assert _metrics(db, no) == expected[no]
        assert expected["72301"] == (315000, 66.7, 5)
        assert expected["72302"] == (100001, None, 2)
        assert expected["72303"] == (50000, None, 3)

    def test_batch_zero_is_all_and_positive_limits(self, db):
        # 항목 4: 0(과 함수 기본값) = 전량 · 양수 = 세대수 큰 순 그만큼
        for no, hh in (("72401", 900), ("72402", 500), ("72403", 100)):
            upsert_complex_from_search(db, _make_complex(no))
            _set_households(db, no, hh)
            _add_row(db, no, "A1", 400000)
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=1)

        assert _metrics(db, "72401") == (400000, None, 1)
        assert _metrics(db, "72402") == (None, None, None)  # 배치 밖 → 아직 안 채움
        job = _last_metric_job(db)
        assert (job.total_items, job.processed_items) == (1, 1)

        collect_complex_metrics(batch_size=0)
        assert _metrics(db, "72402") == (400000, None, 1)
        assert _metrics(db, "72403") == (400000, None, 1)
        assert _last_metric_job(db).total_items == 3

        _set_metrics(db, "72403", None, None, None)
        db.commit()
        collect_complex_metrics()  # 관리자 버튼(인자 없음) = 전량
        assert _metrics(db, "72403") == (400000, None, 1)

    def test_unchanged_day_counts_every_checked_complex(self, db):
        # 항목 5: 값이 하나도 안 바뀌는 날도 processed == total (헛바퀴 경보 없음)
        for no in ("72501", "72502"):
            upsert_complex_from_search(db, _make_complex(no))
            for p in (250000, 260000, 270000):
                _add_row(db, no, "A1", p)
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=0)
        collect_complex_metrics(batch_size=0)  # 두 번째 날: 바뀐 단지 0

        job = _last_metric_job(db)
        assert job.status == "completed"
        assert job.total_items == 2
        assert job.processed_items == 2

    def test_only_changed_complexes_are_written(self, db):
        # 항목 6: 저장값과 같으면 UPDATE 안 함(updated_at 그대로) · 다르면 세 값 + updated_at
        from datetime import datetime, timezone

        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        for no in ("72601", "72602"):
            upsert_complex_from_search(db, _make_complex(no))
            for p in (180000, 200000):
                _add_row(db, no, "A1", p)
        _set_metrics(db, "72601", 190000, None, 2, updated_at=old)  # 이미 맞는 값
        _set_metrics(db, "72602", 100000, None, 2, updated_at=old)  # 낡은 값
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=0)

        db.expire_all()
        same = db.query(Complex).filter(Complex.complex_no == "72601").first()
        diff = db.query(Complex).filter(Complex.complex_no == "72602").first()
        assert same.updated_at.year == 2020
        assert diff.updated_at.year != 2020
        assert (diff.nearby_median_price, diff.recent_trades_6m) == (190000, 2)


class TestMetricRecomputeSafeguards:
    """세션 428 보완(검사관 A·C): 거래 수만 바뀐 단지 · 배치 경고 · 최근 줄 0건 안전장치."""

    def test_count_only_change_is_written(self, db):
        # 중앙값은 그대로(190000)인데 거래 수만 1 → 2 로 바뀌면 다시 쓰고 updated_at 도 갱신
        from datetime import datetime, timezone

        upsert_complex_from_search(db, _make_complex("73101"))
        for p in (180000, 200000):
            _add_row(db, "73101", "A1", p)
        _set_metrics(db, "73101", 190000, None, 1, updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=0)

        db.expire_all()
        c = db.query(Complex).filter(Complex.complex_no == "73101").first()
        assert (c.nearby_median_price, c.jeonse_rate, c.recent_trades_6m) == (190000, None, 2)
        assert c.updated_at.year != 2020

    def test_positive_batch_logs_warning(self, db, caplog):
        # 배치를 양수로 두면 매일 같은 상위 N곳만 계산된다는 경고가 회차 시작 때 한 줄 남는다
        import logging

        _add_filler(db, "73201")
        db.commit()

        from crawler.service_metrics import collect_complex_metrics

        with caplog.at_level(logging.WARNING, logger="crawler.service_metrics"):
            collect_complex_metrics(batch_size=7)
        warns = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("배치 7" in m and "상위 7곳만" in m and "전량은 0" in m for m in warns)

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="crawler.service_metrics"):
            collect_complex_metrics(batch_size=0)
        assert not [r for r in caplog.records if r.levelno == logging.WARNING]

    def test_no_recent_rows_writes_nothing_and_fails(self, db):
        # 최근 6개월 매매 평균가를 하나도 못 읽으면(시세 기록 장애 신호) 아무것도 쓰지 않고 잡 failed
        upsert_complex_from_search(db, _make_complex("73301"))
        _add_row(db, "73301", "A1", 300000, _old_month())
        _add_row(db, "73301", "B1", 200000)  # 최근 전세 줄은 있어도 매매 평균가는 0건
        db.commit()

        from crawler.service_metrics import collect_complex_metrics
        collect_complex_metrics(batch_size=0)

        job = _last_metric_job(db)
        assert job.status == "failed"
        assert "하나도 못 읽어서" in job.error_message
        assert (job.total_items, job.processed_items) == (0, 0)
