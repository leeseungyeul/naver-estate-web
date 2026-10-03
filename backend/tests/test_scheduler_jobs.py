"""스케줄러 job 등록 검증
실행: python -m pytest tests/test_scheduler_jobs.py -v

create_scheduler() 가 환경 토글에 따라 올바른 job 을 등록하는지 확인.
create_scheduler() 는 scheduler 를 만들고 add_job 만 하며 start() 는 하지
않으므로(main.py lifespan 이 start), job 목록은 start 없이 조회 가능.
"""

from unittest.mock import patch

import jwt
import pytest

from crawler import scheduler as sched_mod
from db.models import UserProfile

# test_admin_jobs.py 와 동일한 관례 (conftest 가 SUPABASE_JWT_SECRET 를 이 값으로 세팅).
_JWT_SECRET = "test-secret-key-for-testing-only"


def _admin_token(uid: str) -> str:
    return jwt.encode(
        {"sub": uid, "aud": "authenticated", "email": f"{uid}@test.com"},
        _JWT_SECRET,
        algorithm="HS256",
    )


def _make_admin(db, uid: str) -> None:
    db.add(UserProfile(user_id=uid, email=f"{uid}@test.com", role="admin", status="approved"))
    db.commit()


def _job_ids(scheduler):
    """등록된 job id 집합"""
    return {job.id for job in scheduler.get_jobs()}


def test_backfill_price_job_registered_when_public_data_enabled():
    """PUBLIC_DATA_ENABLED=true 면 시세 소급 수집 job 이 등록된다"""
    with patch.object(sched_mod, "PUBLIC_DATA_ENABLED", True):
        scheduler = sched_mod.create_scheduler()
    assert "backfill_price" in _job_ids(scheduler)


def test_backfill_price_job_absent_when_public_data_disabled():
    """PUBLIC_DATA_ENABLED=false 면 시세 소급 수집 job 이 등록되지 않는다"""
    with patch.object(sched_mod, "PUBLIC_DATA_ENABLED", False):
        scheduler = sched_mod.create_scheduler()
    assert "backfill_price" not in _job_ids(scheduler)


def test_crawl_jobs_have_max_instances():
    """매물 수집·상세 보강 job 에 max_instances=1 이 설정돼 있다.

    동시 중복 실행 방지 — 이전 배치가 안 끝났는데 다음 주기가 시작되면 안 됨.
    (crawl_articles 는 세션 402 부터 cron, crawl_details 는 여전히 interval —
    trigger 종류와 무관하게 둘 다 중복 실행을 막아야 한다.)
    """
    scheduler = sched_mod.create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    for job_id in ("crawl_articles", "crawl_details"):
        assert job_id in jobs, f"{job_id} job 미등록"
        assert jobs[job_id].max_instances == 1, (
            f"{job_id} 의 max_instances 가 1 이 아님"
        )


def test_crawl_articles_runs_on_cron_twice_daily():
    """매물 수집 배치가 cron(매일 01:00/13:00)으로 등록된다.

    세션 402: interval(12h) 은 APScheduler 가 start_date 를 `now + interval` 로
    잡아 재시작할 때마다 다음 실행이 밀렸다(14일 중 9일이 하루 1회만 실행).
    벽시계 기준 cron 이라야 재시작 횟수와 무관하게 하루 2회가 보장된다.
    누군가 interval 로 되돌리면 이 테스트가 잡는다.
    """
    from apscheduler.triggers.cron import CronTrigger

    scheduler = sched_mod.create_scheduler()
    job = {j.id: j for j in scheduler.get_jobs()}["crawl_articles"]
    assert isinstance(job.trigger, CronTrigger), (
        "crawl_articles 가 cron 이 아님 — interval 은 재시작마다 실행이 밀린다"
    )
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "1,13", f"hour 가 1,13 이 아님: {fields['hour']}"
    assert fields["minute"] == "0", f"minute 이 0 이 아님: {fields['minute']}"
    # jitter(±45분) 유지 — 같은 IP 네이버 요청 분산
    assert job.trigger.jitter == 2700, "crawl_articles jitter 가 2700 이 아님"


def test_metrics_job_runs_daily():
    """가치지표 수집 job 이 매일 실행된다 (특정 요일 제한 없음).

    주1회→매일 전환 — cron trigger 의 day_of_week 필드가 '*'(전체) 여야 함.
    """
    with patch.object(sched_mod, "COMPLEX_METRIC_ENABLED", True):
        scheduler = sched_mod.create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "collect_metrics" in jobs, "collect_metrics job 미등록"
    # cron 필드 중 day_of_week 가 특정 요일로 제한돼 있지 않은지 확인
    dow_field = next(
        f for f in jobs["collect_metrics"].trigger.fields if f.name == "day_of_week"
    )
    assert str(dow_field) == "*", f"day_of_week 가 매일이 아님: {dow_field}"


def test_crawl_details_uses_batch_size_env():
    """crawl_details job kwargs 의 batch_size 가 CRAWL_DETAIL_BATCH_SIZE 를 따른다.

    배치 크기를 하드코딩 대신 env 상수로 빼면서, 다음 사람이 또 하드코딩하지
    않도록 회귀 방지 — kwargs 가 module-level 상수를 참조하는지 검증.
    """
    with patch.object(sched_mod, "CRAWL_DETAIL_BATCH_SIZE", 777):
        scheduler = sched_mod.create_scheduler()
    job = {j.id: j for j in scheduler.get_jobs()}["crawl_details"]
    assert job.kwargs["batch_size"] == 777


def test_complex_metric_uses_batch_size_env():
    """collect_metrics job kwargs 의 batch_size 가 COMPLEX_METRIC_BATCH_SIZE 를 따른다.

    가치지표 가속 PR — 기본값 200 → 1000 으로 격상 (env 미설정 시 1000).
    가치 3필드 25,262 단지 잔여 / 200/day = 126일 → 1000/day = 25일.
    회귀 방지 — kwargs 가 module-level 상수를 참조하는지 검증.
    """
    with patch.multiple(
        sched_mod,
        COMPLEX_METRIC_ENABLED=True,
        COMPLEX_METRIC_BATCH_SIZE=555,
    ):
        scheduler = sched_mod.create_scheduler()
    job = {j.id: j for j in scheduler.get_jobs()}["collect_metrics"]
    assert job.kwargs["batch_size"] == 555


def test_complex_metric_runs_offpeak():
    """collect_metrics 가 새벽 04:30 에 돈다 (09~12시 등록 피크 회피).

    세션 255 — 배치 1000 집계가 사용자 요청과 같은 micro 인스턴스 RAM 을
    경합하지 않도록 08:30 → 04:30 으로 이동. 다음 사람이 다시 피크 시간대로
    되돌리지 않도록 cron hour/minute 회귀 방지.
    """
    with patch.object(sched_mod, "COMPLEX_METRIC_ENABLED", True):
        scheduler = sched_mod.create_scheduler()
    job = {j.id: j for j in scheduler.get_jobs()}["collect_metrics"]
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "4", f"collect_metrics 가 04시가 아님: {fields['hour']}시"
    assert fields["minute"] == "30", f"collect_metrics 가 30분이 아님: {fields['minute']}분"


def test_complex_detail_apt_uses_interval_env():
    """COMPLEX_DETAIL_APT_INTERVAL_HOURS env 가 APT backfill 잡 interval 에 반영된다.

    PR #19 답습 — cron(매일 5시) → interval(env 시간) 전환 회귀 방지.
    """
    with patch.object(sched_mod, "COMPLEX_DETAIL_APT_INTERVAL_HOURS", 9):
        scheduler = sched_mod.create_scheduler()
    job = {j.id: j for j in scheduler.get_jobs()}.get("complex_detail_APT")
    assert job is not None, "complex_detail_APT 잡 미등록"
    assert job.trigger.interval.total_seconds() == 9 * 3600


def test_complex_detail_opst_uses_interval_env():
    """COMPLEX_DETAIL_OPST_INTERVAL_HOURS env 가 OPST backfill 잡 interval 에 반영된다."""
    with patch.object(sched_mod, "COMPLEX_DETAIL_OPST_INTERVAL_HOURS", 11):
        scheduler = sched_mod.create_scheduler()
    job = {j.id: j for j in scheduler.get_jobs()}.get("complex_detail_OPST")
    assert job is not None, "complex_detail_OPST 잡 미등록"
    assert job.trigger.interval.total_seconds() == 11 * 3600


def test_complex_detail_batch_size_env():
    """COMPLEX_DETAIL_BATCH_SIZE 가 5종 backfill 잡 batch_size 에 반영된다.

    한 patch 로 APT/OPST/JGC/ABYG/OBYG 5종 동시 검증.
    """
    with patch.object(sched_mod, "COMPLEX_DETAIL_BATCH_SIZE", 999):
        scheduler = sched_mod.create_scheduler()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    for job_id in ["complex_detail_APT", "complex_detail_OPST",
                   "complex_detail_JGC", "complex_detail_ABYG", "complex_detail_OBYG"]:
        job = jobs.get(job_id)
        assert job is not None, f"{job_id} 잡 미등록"
        assert job.kwargs["batch_size"] == 999, f"{job_id} batch_size 가 env 미반영"


def test_complex_detail_small_types_remain_cron():
    """JGC/ABYG/OBYG 는 cron trigger 유지 (PR #20 의 의도된 분리).

    누군가 실수로 interval 로 바꾸면 호출량 폭증 — 소수 유형은 주1회 cron 고정.
    """
    from apscheduler.triggers.cron import CronTrigger

    scheduler = sched_mod.create_scheduler()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    for job_id in ["complex_detail_JGC", "complex_detail_ABYG", "complex_detail_OBYG"]:
        job = jobs.get(job_id)
        assert job is not None, f"{job_id} 잡 미등록"
        assert isinstance(job.trigger, CronTrigger), (
            f"{job_id} 가 cron 이 아님 — 소수 유형은 cron 유지여야 함"
        )


def test_complex_detail_jobs_have_jitter():
    """5종 backfill 잡 모두 jitter 가 설정돼 있다 (같은 IP 다른 잡과 시간 분산)."""
    scheduler = sched_mod.create_scheduler()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    for job_id in ["complex_detail_APT", "complex_detail_OPST",
                   "complex_detail_JGC", "complex_detail_ABYG", "complex_detail_OBYG"]:
        job = jobs.get(job_id)
        assert job is not None, f"{job_id} 잡 미등록"
        assert job.trigger.jitter is not None and job.trigger.jitter > 0, (
            f"{job_id} 에 jitter 미설정 — IP 차단 방지를 위해 jitter 필요"
        )


def test_add_job_rejects_duplicate_id():
    """create_scheduler() 가 같은 id 두 번 등록을 ValueError 로 거부한다.

    APScheduler 기본 동작은 silent 허용 (2026-05-20 실측: jobs_count=2 통과) —
    동적 id 생성 (예: f"popular_{hour}_{minute}") 충돌 시 발견 지연. 시작 시점에
    명시적 가드. 본 가드 = crawler/scheduler.py 의 _add_job_unique 래퍼.
    """
    scheduler = sched_mod.create_scheduler()
    # 이미 등록된 id 하나를 골라 같은 id 로 한 번 더 add → ValueError
    existing_id = next(iter(j.id for j in scheduler.get_jobs()))
    with pytest.raises(ValueError, match=f"'{existing_id}'"):
        scheduler.add_job(lambda: None, "interval", minutes=1, id=existing_id)


# META fallback 이 가정하는 운영 interval/주기 값 (backend/.env 기준).
# env 가변 잡은 코드 기본값(getenv default)이 CI 와 운영에서 다를 수 있으므로,
# 가드가 이 운영값으로 env 를 명시 patch 해 환경 독립적으로 검증한다.
# 메타 fallback 문자열의 시간수를 바꾸면 여기도 함께 바꿔야 한다.
_OPERATIONAL_INTERVALS = {
    # crawl_articles 는 세션 402 부터 cron 고정(매일 01:00/13:00) — env 가변 아님
    "CRAWL_DETAIL_INTERVAL_MIN": 30,   # crawl_details → "30분마다"
    "COMPLEX_DETAIL_APT_INTERVAL_HOURS": 4,   # → "4시간마다"
    "COMPLEX_DETAIL_OPST_INTERVAL_HOURS": 4,  # → "4시간마다"
    "MONITOR_INTERVAL_MIN": 10,        # crawler_monitor → "10분마다" (.env 운영값)
}


def test_meta_fallback_matches_describe_trigger_for_active_jobs():
    """모든 env on 시: META schedule fallback == describe_trigger(실제 trigger).

    세션 256 — schedule SSOT 도입. META schedule 은 비활성 잡 전용 fallback 으로
    격하됐다(활성 잡은 scheduler-status 가 trigger 에서 런타임 생성). 그래도 손글씨라
    drift 위험이 남으므로, 9개 env 강제 on 한 scheduler 의 각 trigger 와 정확 매칭해
    고정한다. 옛 휴리스틱 가드(키워드 포함 여부)를 정확 매칭으로 대체 —
    PR #99(08:30↔04:30)·PR 6a(6h↔4h)·monitor(20분↔10분) 류 drift 를 구조적으로 차단.

    env 가변 interval 잡은 _OPERATIONAL_INTERVALS 로 운영값을 명시 patch 한다 —
    CI 엔 .env 가 없어 코드 기본값(예: MONITOR_INTERVAL_MIN=30)을 쓰므로, patch
    없이는 메타 fallback(운영 10분)과 환경 불일치로 false fail (CI #823 사고 답습).
    """
    from crawler.schedule_describe import describe_trigger
    from routers.admin.scheduler import SCHEDULER_JOB_META

    with (
        patch.object(sched_mod, "PUBLIC_DATA_ENABLED", True),
        patch.object(sched_mod, "OFFICIAL_PRICE_ENABLED", True),
        patch.object(sched_mod, "POPULAR_CRAWL_ENABLED", True),
        patch.object(sched_mod, "AIR_QUALITY_ENABLED", True),
        patch.object(sched_mod, "EMERGENCY_ENABLED", True),
        patch.object(sched_mod, "CHILDCARE_ENABLED", True),
        patch.object(sched_mod, "CRIME_STATS_ENABLED", True),
        patch.object(sched_mod, "COMPLEX_DETAIL_ENABLED", True),
        patch.object(sched_mod, "COMPLEX_METRIC_ENABLED", True),
        patch.object(sched_mod, "MONITOR_ENABLED", True),
        # V051: KAPT_ENABLED 는 기본 false(첫 배포는 꺼서 나감) — 여기서 켜주지 않으면
        # 잡이 등록되지 않아 "META 만 있고 잡 없음" drift 로 잡힌다.
        patch.object(sched_mod, "KAPT_ENABLED", True),
        # 세션 400: PAYMENT_ENABLED 도 코드 기본값 false(무료 전환) — 명시하지 않으면 이
        # 가드가 conftest 의 env 봉쇄 한 줄에 조용히 의존한다(그 줄이 바뀌면 무관한 이
        # 테스트가 엉뚱한 이유로 깨진다). KAPT_ENABLED 와 같은 이유로 여기서 켠다.
        patch.object(sched_mod, "PAYMENT_ENABLED", True),
        # field_drift_monitor 도 기본 false — 켜지 않으면 "META 만 있고 잡 없음" drift.
        patch.object(sched_mod, "FIELD_DRIFT_MONITOR_ENABLED", True),
        # 세션 402: BACKFILL_DETAIL_ENABLED 도 기본 false — 같은 이유로 여기서 켠다.
        patch.object(sched_mod, "BACKFILL_DETAIL_ENABLED", True),
        patch.multiple(sched_mod, **_OPERATIONAL_INTERVALS),
    ):
        scheduler = sched_mod.create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}

    errors: list[str] = []
    for job_id, meta in SCHEDULER_JOB_META.items():
        job = jobs.get(job_id)
        if job is None:
            errors.append(f"{job_id}: 모든 env on 인데 미등록 (META 만 있고 잡 없음)")
            continue
        generated = describe_trigger(job.trigger)
        if generated != meta["schedule"]:
            errors.append(
                f"{job_id}: meta fallback='{meta['schedule']}' != describe_trigger='{generated}'"
            )
    assert not errors, "META fallback 과 trigger SSOT drift:\n  " + "\n  ".join(errors)


def test_scheduler_job_meta_covers_all_registered_jobs():
    """SCHEDULER_JOB_META 가 create_scheduler() 의 모든 등록 job id 를 커버한다.

    META 누락 시 admin UI 의 스케줄러 모니터링 표에 해당 job 이 안 보임.
    PR #20·#14 가 새 job 추가하면서 META 동기화를 빠뜨린 사고 재발 방지.
    """
    from routers.admin.scheduler import SCHEDULER_JOB_META

    # 모든 조건부 job 을 켜야 등록되는 잡까지 다 잡힘
    with (
        patch.object(sched_mod, "PUBLIC_DATA_ENABLED", True),
        patch.object(sched_mod, "OFFICIAL_PRICE_ENABLED", True),
        patch.object(sched_mod, "POPULAR_CRAWL_ENABLED", True),
        patch.object(sched_mod, "AIR_QUALITY_ENABLED", True),
        patch.object(sched_mod, "EMERGENCY_ENABLED", True),
        patch.object(sched_mod, "CHILDCARE_ENABLED", True),
        patch.object(sched_mod, "CRIME_STATS_ENABLED", True),
        patch.object(sched_mod, "COMPLEX_DETAIL_ENABLED", True),
        patch.object(sched_mod, "COMPLEX_METRIC_ENABLED", True),
        patch.object(sched_mod, "MONITOR_ENABLED", True),
        patch.object(sched_mod, "VACUUM_MAINTENANCE_ENABLED", True),
        patch.object(sched_mod, "FIELD_DRIFT_MONITOR_ENABLED", True),
        patch.object(sched_mod, "BACKFILL_DETAIL_ENABLED", True),
    ):
        scheduler = sched_mod.create_scheduler()
    registered_ids = {job.id for job in scheduler.get_jobs()}
    missing = registered_ids - set(SCHEDULER_JOB_META.keys())
    assert not missing, (
        f"SCHEDULER_JOB_META 누락: {sorted(missing)} — "
        "backend/routers/admin/scheduler.py 의 SCHEDULER_JOB_META 에 추가 필요"
    )


def test_vacuum_maintenance_job_registered_by_default():
    """VACUUM_MAINTENANCE_ENABLED=true(기본) 면 정기 VACUUM job 이 새벽 03:50 에 등록 (세션 260)"""
    with patch.object(sched_mod, "VACUUM_MAINTENANCE_ENABLED", True):
        scheduler = sched_mod.create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "vacuum_maintenance" in jobs
    fields = {f.name: str(f) for f in jobs["vacuum_maintenance"].trigger.fields if not f.is_default}
    assert fields.get("hour") == "3" and fields.get("minute") == "50"


def test_vacuum_maintenance_job_absent_when_disabled():
    """VACUUM_MAINTENANCE_ENABLED=false 면 정기 VACUUM job 미등록"""
    with patch.object(sched_mod, "VACUUM_MAINTENANCE_ENABLED", False):
        scheduler = sched_mod.create_scheduler()
    assert "vacuum_maintenance" not in _job_ids(scheduler)


def test_run_vacuum_maintenance_skips_on_sqlite():
    """run_vacuum_maintenance 는 SQLite(테스트)에선 no-op (VACUUM 문법 PostgreSQL 전용)"""
    from crawler.vacuum_maintenance import run_vacuum_maintenance

    result = run_vacuum_maintenance()
    assert result["skipped"] == "sqlite"
    assert result["vacuumed"] == []


def test_run_vacuum_maintenance_records_crawl_job(db):
    """세션 359: 전수조사로 발견된 사각지대 회귀 가드 — 이전엔 CrawlJob 을 아예
    안 남겨 monitor.py 3축(작업실패/작업마비/데이터미축적) 어디도 이 잡의 존재
    자체를 몰랐다. 이제 job_type='vacuum_maintenance' 로 완료 기록이 남아야 하고,
    이걸로 monitor.py 의 범용 job_type 스캔(작업실패/작업마비)에 자연 편입된다."""
    from crawler.vacuum_maintenance import run_vacuum_maintenance
    from db.models import CrawlJob

    run_vacuum_maintenance()

    job = db.query(CrawlJob).filter(CrawlJob.job_type == "vacuum_maintenance").first()
    assert job is not None, "CrawlJob 기록이 생성되지 않음 — 사각지대 재발"
    assert job.status == "completed"
    assert job.completed_at is not None


# ── source(출처) 필드 회귀 가드 (세션 402 — 관리자 화면 출처 표시) ──────────────


def test_scheduler_job_meta_all_jobs_have_source_key():
    """SCHEDULER_JOB_META 의 모든 잡에 "source" 키가 존재한다 (값은 None 가능).

    누락되면 dict.get("source") 는 조용히 None 을 반환해 이 가드 없인 "출처 없음"과
    "그 필드를 아예 안 채웠음"이 구분되지 않는다 — 새 잡 추가 시 source 명시를 강제.
    """
    from routers.admin.scheduler import SCHEDULER_JOB_META

    missing = [job_id for job_id, meta in SCHEDULER_JOB_META.items() if "source" not in meta]
    assert not missing, f"source 키 누락: {missing}"


def test_scheduler_job_meta_probe_refs_match_registry():
    """META 의 {"probe": "..."} 참조가 실제 PROBE_REGISTRY name 과 정확히 일치한다.

    오타로 존재하지 않는 이름을 적으면 _source_text() 가 그 원문 문자열을 그대로
    돌려주는 폴백이 있어(눈에 띄게 하려는 의도적 설계) 화면이 깨지진 않지만, 그러면
    "PROBE_REGISTRY 에서 조회했다"는 설계 취지가 무력화되고 이름이 레지스트리와
    따로 논다 — CI 가 이 drift 를 잡는다.
    """
    from crawler.api_version_monitor import PROBE_REGISTRY
    from routers.admin.scheduler import SCHEDULER_JOB_META

    registry_names = {entry["name"] for entry in PROBE_REGISTRY}
    errors = []
    for job_id, meta in SCHEDULER_JOB_META.items():
        source = meta.get("source")
        if isinstance(source, dict) and "probe" in source:
            if source["probe"] not in registry_names:
                errors.append(f"{job_id}: probe 참조 '{source['probe']}' 가 PROBE_REGISTRY 에 없음")
    assert not errors, "\n".join(errors)


def test_source_text_resolves_probe_reference():
    """_source_text() 가 {"probe": name} 을 PROBE_REGISTRY 의 실제 (name, url) 로 조회한다."""
    from routers.admin.scheduler import _source_text

    name, url = _source_text({"probe": "국토교통부 아파트 매매 실거래가"})
    assert name == "국토교통부 아파트 매매 실거래가"
    assert url == "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"


def test_source_text_handles_string_and_none():
    """_source_text() 가 문자열은 그대로, None 은 (None, None) 을 반환한다."""
    from routers.admin.scheduler import _source_text

    assert _source_text("네이버 부동산 (https://new.land.naver.com)") == (
        "네이버 부동산 (https://new.land.naver.com)",
        None,
    )
    assert _source_text(None) == (None, None)


def test_source_text_unknown_probe_falls_back_to_raw_key():
    """존재하지 않는 probe 참조는 원문 키를 그대로 노출한다 (drift 를 숨기지 않음).

    뮤테이션 검증용 — 이 동작 자체가 "오타를 조용히 삼키지 않는다"는 설계 의도.
    """
    from routers.admin.scheduler import _source_text

    name, url = _source_text({"probe": "존재하지-않는-이름"})
    assert name == "존재하지-않는-이름"
    assert url is None


def test_scheduler_status_response_includes_source(client, db):
    """GET /api/admin/scheduler-status 응답의 각 job 에 source/source_url 이 포함된다.

    기존 필드(scheduler_job_id/name/schedule/enabled/last_run/next_run_at/stats_24h)
    구조는 절대 안 바뀌었는지도 같이 확인 (FE 타입 하위호환).
    """
    _make_admin(db, "sched-src-1")
    resp = client.get(
        "/api/admin/scheduler-status",
        headers={"Authorization": f"Bearer {_admin_token('sched-src-1')}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"], "jobs 배열이 비어있음"
    for job in body["jobs"]:
        assert "source" in job
        assert "source_url" in job
        # 기존 필드 존재 확인 (하위호환 회귀 가드)
        for key in (
            "scheduler_job_id", "name", "schedule", "enabled",
            "last_run", "next_run_at", "stats_24h",
        ):
            assert key in job, f"기존 필드 '{key}' 누락 — FE 타입 호환 깨짐"

    # 네이버 출처 잡 하나를 골라 실제 내용 확인
    crawl_articles = next(j for j in body["jobs"] if j["scheduler_job_id"] == "crawl_articles")
    assert "네이버" in crawl_articles["source"]

    # 내부 DB 전용 잡은 source 가 None (화면에 "-" 로 표시)
    vacuum = next(j for j in body["jobs"] if j["scheduler_job_id"] == "vacuum_maintenance")
    assert vacuum["source"] is None
    assert vacuum["source_url"] is None


# ── 잡 이름 한 벌 가드 (세션 418 — 화면·달력·알림 이름 통일) ─────────────────
#
# 정본 = crawler/scheduler.py 의 add_job(name=...). 관리자 화면(SCHEDULER_JOB_META)과
# 텔레그램 폴백표(_JOB_LABEL_FALLBACK)는 그 글자를 그대로 옮긴다. 세션 418 전에는
# META 이름 31개 중 30개가 add_job 과 달라, 사장님이 화면과 알림에서 같은 잡을
# 다른 이름으로 봤다("매물 수집 배치" vs "단지 매물 가져오기").


def _scheduler_with_every_job():
    """조건부 토글을 전부 켠 스케줄러 — 등록될 수 있는 잡을 빠짐없이 만든다."""
    with (
        patch.object(sched_mod, "PUBLIC_DATA_ENABLED", True),
        patch.object(sched_mod, "OFFICIAL_PRICE_ENABLED", True),
        patch.object(sched_mod, "POPULAR_CRAWL_ENABLED", True),
        patch.object(sched_mod, "AIR_QUALITY_ENABLED", True),
        patch.object(sched_mod, "EMERGENCY_ENABLED", True),
        patch.object(sched_mod, "CHILDCARE_ENABLED", True),
        patch.object(sched_mod, "CRIME_STATS_ENABLED", True),
        patch.object(sched_mod, "COMPLEX_DETAIL_ENABLED", True),
        patch.object(sched_mod, "COMPLEX_METRIC_ENABLED", True),
        patch.object(sched_mod, "MONITOR_ENABLED", True),
        patch.object(sched_mod, "KAPT_ENABLED", True),
        patch.object(sched_mod, "PAYMENT_ENABLED", True),
        patch.object(sched_mod, "BILLING_AUTO_CHARGE_ENABLED", True),
        patch.object(sched_mod, "VACUUM_MAINTENANCE_ENABLED", True),
        patch.object(sched_mod, "API_VERSION_MONITOR_ENABLED", True),
        patch.object(sched_mod, "FIELD_DRIFT_MONITOR_ENABLED", True),
        patch.object(sched_mod, "BACKFILL_DETAIL_ENABLED", True),
    ):
        return sched_mod.create_scheduler()


def test_meta_names_match_add_job_names():
    """SCHEDULER_JOB_META 의 name == add_job(name=...) — 31개 전부 글자 단위로.

    뮤테이션: META 이름 하나를 옛 이름(예: "매물 수집 배치")으로 되돌리면 FAIL.
    """
    from routers.admin.scheduler import SCHEDULER_JOB_META

    jobs = {job.id: job for job in _scheduler_with_every_job().get_jobs()}
    errors = []
    for job_id, meta in SCHEDULER_JOB_META.items():
        job = jobs.get(job_id)
        if job is None:
            errors.append(f"{job_id}: 토글을 다 켜도 등록되지 않음 (META 만 있고 잡 없음)")
        elif meta["name"] != job.name:
            errors.append(f"{job_id}: META '{meta['name']}' != add_job '{job.name}'")
    assert not errors, "관리자 화면 이름이 스케줄러 이름과 다르다:\n  " + "\n  ".join(errors)


def test_job_label_fallback_matches_add_job_names():
    """_JOB_LABEL_FALLBACK[id] == add_job(name=...) — 등록되는 잡 전부(동적 id 포함).

    폴백표는 스케줄러 조회가 실패할 때 텔레그램에 찍히는 이름이다. 달라지면 같은
    잡이 평소와 다른 이름으로 알림이 온다. 뮤테이션: 폴백 값 하나를 바꾸면 FAIL.
    """
    from crawler.job_error_listener import _JOB_LABEL_FALLBACK

    errors = []
    for job in _scheduler_with_every_job().get_jobs():
        label = _JOB_LABEL_FALLBACK.get(job.id)
        if label != job.name:
            errors.append(f"{job.id}: 폴백 '{label}' != add_job '{job.name}'")
    assert not errors, "알림 폴백 이름이 스케줄러 이름과 다르다:\n  " + "\n  ".join(errors)


def _cron_field(job, name: str) -> str:
    """cron 트리거의 필드 하나를 문자열로 (예: hour → '12')."""
    return str(next(f for f in job.trigger.fields if f.name == name))


def test_kapt_costs_runs_twice_daily_morning_and_noon():
    """관리비 받기가 06:20·12:40 두 회차로 등록된다 (세션 422).

    아침 시각대에만 K-apt 창구가 간헐 오류(04)를 내 06:20 회차가 사흘 연속 실패했다 →
    같은 함수·같은 배치로 12:40 에 한 번 더 돈다. 두 회차는 scheduler_job_id 만 다르다
    (crawl_jobs 행에서 어느 회차인지 구분하고, 신선도 카드는 둘을 함께 센다).
    뮤테이션: scheduler.py 의 kapt_costs_noon add_job 을 지우면 FAIL.
    """
    with patch.object(sched_mod, "KAPT_ENABLED", True):
        scheduler = sched_mod.create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "kapt_costs" in jobs, "kapt_costs(06:20) 미등록"
    assert "kapt_costs_noon" in jobs, "kapt_costs_noon(12:40) 미등록"

    morning, noon = jobs["kapt_costs"], jobs["kapt_costs_noon"]
    assert (_cron_field(morning, "hour"), _cron_field(morning, "minute")) == ("6", "20")
    assert (_cron_field(noon, "hour"), _cron_field(noon, "minute")) == ("12", "40")
    assert _cron_field(noon, "day_of_week") == "*", "낮 회차가 매일이 아님"

    # 같은 함수·같은 배치 — 다른 것은 scheduler_job_id 하나뿐
    assert noon.func is morning.func
    assert noon.kwargs["batch_size"] == morning.kwargs["batch_size"] == sched_mod.KAPT_COST_BATCH_SIZE
    assert morning.kwargs["scheduler_job_id"] == "kapt_costs"
    assert noon.kwargs["scheduler_job_id"] == "kapt_costs_noon"
    assert noon.max_instances == 1


def test_kapt_costs_evening_run_at_2100():
    """관리비 받기 저녁 회차가 매일 21:00 에 등록된다 (세션 426).

    호출 간격 1.5초에선 두 회차로 한 달 수요를 못 따라가 세 번째 회차를 더했다.
    같은 함수·같은 배치, 다른 것은 scheduler_job_id 하나뿐.
    뮤테이션: scheduler.py 의 kapt_costs_evening add_job 을 지우면 FAIL.
    """
    with patch.object(sched_mod, "KAPT_ENABLED", True):
        scheduler = sched_mod.create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "kapt_costs_evening" in jobs, "kapt_costs_evening(21:00) 미등록"

    morning, evening = jobs["kapt_costs"], jobs["kapt_costs_evening"]
    assert (_cron_field(evening, "hour"), _cron_field(evening, "minute")) == ("21", "0")
    assert _cron_field(evening, "day_of_week") == "*", "저녁 회차가 매일이 아님"
    assert _cron_field(evening, "day") == "*", "저녁 회차가 매일이 아님"
    assert evening.name == "단지 관리비 받기 21:00"
    assert evening.func is morning.func
    assert evening.kwargs["batch_size"] == sched_mod.KAPT_COST_BATCH_SIZE
    assert evening.kwargs["scheduler_job_id"] == "kapt_costs_evening"
    assert evening.max_instances == 1
    assert evening.misfire_grace_time == 3600


def test_kapt_costs_both_runs_absent_when_disabled():
    """KAPT_ENABLED 꺼짐이면 세 회차 모두 등록되지 않는다."""
    with patch.object(sched_mod, "KAPT_ENABLED", False):
        scheduler = sched_mod.create_scheduler()
    ids = _job_ids(scheduler)
    assert "kapt_costs" not in ids
    assert "kapt_costs_noon" not in ids
    assert "kapt_costs_evening" not in ids
