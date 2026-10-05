"""APScheduler 기반 크롤러 스케줄러"""

import logging
import os
import re

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from crawler.billing_charge import charge_due_billing_keys
from crawler.service import (
    backfill_article_details,
    backfill_price_batch,
    collect_price_history,
    crawl_article_details,
    crawl_articles_batch,
    crawl_complex_details_batch,
    crawl_popular_complexes,
    discover_all_regions,
)
from crawler.service_metrics import collect_complex_metrics
from crawler.vacuum_maintenance import run_vacuum_maintenance

load_dotenv()

# ⚠ load_dotenv() **뒤에** import 해야 한다 — config.payment_flags 는 import 시점에
# os.getenv("PAYMENT_ENABLED") 를 읽으므로, 먼저 import 되면 .env 값을 못 보고 기본값
# (꺼짐)으로 굳는다. main.py 도 같은 이유로 load_dotenv() 를 앱 import 앞에 둔다.
from config import payment_flags  # noqa: E402

logger = logging.getLogger(__name__)

CRAWL_DETAIL_INTERVAL_MIN = int(os.getenv("CRAWL_DETAIL_INTERVAL_MIN", "30"))
CRAWL_DETAIL_BATCH_SIZE = int(os.getenv("CRAWL_DETAIL_BATCH_SIZE", "500"))
# 상세 백필(세션 402) — 네이버 상세 API 키 드리프트(세션 401)로 detail_crawled=True 인데
# heating_type 등 3컬럼이 NULL 인 기존 매물을 재크롤한다. 기본 꺼짐(이 레포 관례 —
# KAPT_ENABLED·OFFICIAL_PRICE_ENABLED 와 동일하게 배포 후 관리자 수동 확인 뒤 켠다).
BACKFILL_DETAIL_ENABLED = os.getenv("BACKFILL_DETAIL_ENABLED", "false").lower() == "true"
# 백필 배치 — 회차별로 크기가 다르다(사장님 결정 2026-09-13: 하루 5,500건, 완주 약 19일).
#
# 왜 새벽과 낮이 다른가 = **소요 시간이 다음 크론과 겹치면 안 되기 때문**.
# 한 건당 _throttle_details(1.5초)가 붙으므로 소요 = 배치 × 1.5초.
#   * 00:20 회차: 다음이 01:00 crawl_articles(cron, jitter ±45분이라 00:15부터 시작 가능).
#     안전 여유를 두고 1,500건(약 38분) — 01:00 정시 시작 기준으로 끝난다.
#   * 12:20 회차: 다음 네이버 호출 잡이 14:45 popular_crawl 로 145분 여유.
#     4,000건(약 100분, 14:00 종료)이라 45분 여유를 남긴다.
# 총량 근거: 네이버 상세 호출 실적 실측(9/7 12,141건 · 9/10 9,993건을 문제없이 소화)에
# 비해 +5,500 은 여력 안. 호출 간격은 불변이라 순간 부하도 안 오른다.
# env 로 덮으면 두 회차 모두 그 값이 된다(개별 조정이 필요하면 env 를 분리할 것).
BACKFILL_DETAIL_BATCH_SIZE = int(os.getenv("BACKFILL_DETAIL_BATCH_SIZE", "0")) or None
_BACKFILL_DAWN_SIZE = BACKFILL_DETAIL_BATCH_SIZE or 1500
_BACKFILL_NOON_SIZE = BACKFILL_DETAIL_BATCH_SIZE or 4000
# 세션 402: 50 → 150. 목록 크롤 네이버 호출은 하루 280~430 으로 상세(565~12,141)의
# 소수라 3배로 올려도 총량 영향이 미미하고, 호출 속도 자체는 _throttle_articles 가
# 그대로 제한한다(간격 불변 = IP 차단 위험 불변). 목표 = 활성 매물 보유 단지 10,567
# 한 바퀴 ≈ 30일(150 × 2회/일 × 30일 ≈ 9,000 단지, PR-2 선정 키 교체와 함께).
# ⚠ .env 에 같은 키가 있으면 그 값이 우선한다 — 적용 후 crawl_jobs 의 자식 잡 수·
# 회차로 실효값을 판정할 것(코드 기본값만 보고 "150 이 돈다"고 단정 금지).
CRAWL_BATCH_SIZE = int(os.getenv("CRAWL_BATCH_SIZE", "150"))
POPULAR_CRAWL_ENABLED = os.getenv("POPULAR_CRAWL_ENABLED", "true").lower() == "true"
POPULAR_CRAWL_BATCH_SIZE = int(os.getenv("POPULAR_CRAWL_BATCH_SIZE", "50"))
PUBLIC_DATA_ENABLED = os.getenv("PUBLIC_DATA_ENABLED", "false").lower() == "true"
PUBLIC_DATA_BATCH_SIZE = int(os.getenv("PUBLIC_DATA_BATCH_SIZE", "300"))
OFFICIAL_PRICE_ENABLED = os.getenv("OFFICIAL_PRICE_ENABLED", "false").lower() == "true"
# K-apt 관리비 연동 (V051) — 기본 false. 첫 배포는 꺼서 나가고, 관리자 수동 트리거로
# 매칭·수집을 실측 검증한 뒤 켠다. ⚠ 단지 하나에 22콜(공용 17 + 개별 5)이 나가
# 배치 크기가 곧 쿼터 소모량이다. 관리비 두 서비스도 운영계정(10만/일) 전환이 끝나
# 500 으로 운영 중(2026-08-31 실측: 하루 kapt 32,035콜, 실패 0·쿼터 에러 0).
KAPT_ENABLED = os.getenv("KAPT_ENABLED", "false").lower() == "true"
KAPT_COST_BATCH_SIZE = int(os.getenv("KAPT_COST_BATCH_SIZE", "500"))
# 시세 이력 부족 단지 소급 수집 (국토교통부 실거래가). PUBLIC_DATA_ENABLED 와 같은
# data.go.kr 키 사용 — 일일 쿼터(10,000회, mibunyang 공유) 보호 위해 배치 작게.
PUBLIC_PRICE_BACKFILL_BATCH_SIZE = int(os.getenv("PUBLIC_PRICE_BACKFILL_BATCH_SIZE", "30"))
AIR_QUALITY_ENABLED = os.getenv("AIR_QUALITY_ENABLED", "false").lower() == "true"
AIR_QUALITY_BATCH_SIZE = int(os.getenv("AIR_QUALITY_BATCH_SIZE", "100"))
EMERGENCY_ENABLED = os.getenv("EMERGENCY_ENABLED", "false").lower() == "true"
# 0 = 전량(위경도 보유 2,938단지). 전국 기관목록을 1회만 받고 단지별 처리는 로컬
# 거리계산뿐이라 배치 크기가 외부 API 호출 수와 무관 — 전량이어도 비용 증가 0 (세션 394).
EMERGENCY_BATCH_SIZE = int(os.getenv("EMERGENCY_BATCH_SIZE", "0"))
CHILDCARE_ENABLED = os.getenv("CHILDCARE_ENABLED", "false").lower() == "true"
# 0 = 전량(위경도 보유 2,938단지). 시군구당 1콜 + 런 내 캐시 재사용 구조라 전량이어도
# 호출 상한 = 단지가 걸친 (region,gu) 조합 수 ≈ 248 (2026-09-05 prod 실측).
CHILDCARE_BATCH_SIZE = int(os.getenv("CHILDCARE_BATCH_SIZE", "0"))
CRIME_STATS_ENABLED = os.getenv("CRIME_STATS_ENABLED", "false").lower() == "true"
COMPLEX_DETAIL_ENABLED = os.getenv("COMPLEX_DETAIL_ENABLED", "true").lower() == "true"
COMPLEX_DETAIL_BATCH_SIZE = int(os.getenv("COMPLEX_DETAIL_BATCH_SIZE", "1000"))
COMPLEX_DETAIL_APT_INTERVAL_HOURS = int(os.getenv("COMPLEX_DETAIL_APT_INTERVAL_HOURS", "4"))
COMPLEX_DETAIL_OPST_INTERVAL_HOURS = int(os.getenv("COMPLEX_DETAIL_OPST_INTERVAL_HOURS", "4"))
COMPLEX_METRIC_ENABLED = os.getenv("COMPLEX_METRIC_ENABLED", "true").lower() == "true"
# 0 = 전량(최근 6개월 매매가 있는 모든 단지를 매일 다시 계산 — 세션 428). DB 집계만이라 외부 호출 0.
# 옛 이름 COMPLEX_METRIC_BATCH_SIZE 는 "빈 단지 N곳 채우기" 뜻이라 새 이름으로 바꿨다 — 운영 .env 에 옛 줄이
# 남아 있어도 전량이 덮이지 않게(그 파일은 우리가 못 읽는다). 옛 줄이 있으면 기동 때 안내 로그만 남긴다.
COMPLEX_METRIC_RECOMPUTE_LIMIT = int(os.getenv("COMPLEX_METRIC_RECOMPUTE_LIMIT", "0"))
# 빌링키 자동결제(정기결제 PR3) — 매일 04:50 next_charge_at 도래분 결제. 기본 활성.
BILLING_AUTO_CHARGE_ENABLED = os.getenv("BILLING_AUTO_CHARGE_ENABLED", "true").lower() == "true"
# 결제 기능 전역 스위치(세션 400 무료 전환, 기본 꺼짐) — 결제 API 게이트와 같은 값을 본다.
# 이 모듈 상수로 한 번 더 받는 이유: create_scheduler() 가 조건에서 읽을 때 테스트가
# patch.object(sched_mod, "PAYMENT_ENABLED", ...) 로 켜고 끌 수 있게 하려는 것
# (다른 토글들과 같은 패턴 — tests/test_scheduler_jobs.py 답습).
PAYMENT_ENABLED = payment_flags.PAYMENT_ENABLED
MONITOR_ENABLED = os.getenv("MONITOR_ENABLED", "false").lower() == "true"
MONITOR_INTERVAL_MIN = int(os.getenv("MONITOR_INTERVAL_MIN", "30"))
# 정기 VACUUM (ANALYZE) — articles/trades visibility map 재악화 차단 (세션 260)
VACUUM_MAINTENANCE_ENABLED = os.getenv("VACUUM_MAINTENANCE_ENABLED", "true").lower() == "true"
# data.go.kr API 버전 격변 감시 — 폐기된 엔드포인트 조기 경보 (2026-08-19 사고 재발방지).
# 기본 활성: 감시 자체가 비용 0 에 가깝고(주 1회 8회 호출), 꺼두면 사고가 그대로 재현된다.
API_VERSION_MONITOR_ENABLED = os.getenv("API_VERSION_MONITOR_ENABLED", "true").lower() == "true"
# 상세 필드 채움률 드리프트 감시 — 네이버 상세 API 응답 키가 조용히 바뀌어(2026-09-13
# heating_type 등 4필드 0% 사고) 에러 없이 데이터만 안 쌓이는 장애를 조기 경보한다.
# DB 집계만(네이버 API 호출 0) 이라 부하 없음 — 기본 false 로 나가고, 검증 후 켠다.
FIELD_DRIFT_MONITOR_ENABLED = os.getenv("FIELD_DRIFT_MONITOR_ENABLED", "false").lower() == "true"

# 모듈 레벨 스케줄러 참조 — admin API에서 다음 실행 시각 조회용
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    """실행 중인 스케줄러 인스턴스 반환 (미실행 시 None)"""
    return _scheduler


# add_job( 호출 시작 지점을 찾는 정규식 — 여기서부터 블록 단위로 id 를 찾는다.
# 파일 전체를 무차별로 id=<문자열> 패턴 스캔하면 주석·docstring 안에 우연히
# 같은 모양 문구가 있을 때 오탐한다(구현 중 실측 발견 — 세션 359). add_job(
# 호출 블록 안에서만 id 를 찾으면 이 오탐이 원천 차단된다.
#
# ⚠ 이 헬퍼는 반드시 create_scheduler() 정의보다 "앞"(= 파일의 모든 add_job(
# 호출보다 앞)에 위치해야 한다 — extract_scheduler_job_ids() 는 "각 add_job(
# 호출 지점부터 다음 add_job( 또는 파일 끝까지"를 한 블록으로 보는데, 만약
# 이 함수를 create_scheduler() *뒤*에 두면 마지막 add_job 호출 이후 "파일
# 끝까지"의 마지막 블록 안에 이 함수 자신의 소스 코드(주석 포함)까지
# 포함되어 자기 자신을 오탐하는 사고가 난다(구현 중 실측 발견).
_ADD_JOB_CALL_PATTERN = re.compile(r"\.add_job\(")
_STATIC_ID_PATTERN = re.compile(r'\bid="([a-zA-Z0-9_]+)"')


def extract_scheduler_job_ids(source: str) -> list[str]:
    """스케줄러 소스 텍스트에서 add_job 호출의 정적 id 리터럴 전부 추출.

    "새 스케줄러 잡을 추가하면서 감시 등록을 깜빡하는" 실수를 CI 가 구조적으로
    막기 위한 test_scheduler_monitoring_coverage.py 전용 헬퍼 (mibunyang
    RECORD_ALLOWLIST 패턴 답습). 순수 함수 — 부작용 없음(파일을 열지 않고
    이미 읽은 소스 텍스트 문자열을 인자로 받는다).

    구현 방식: 각 add_job 호출 지점부터 다음 add_job 호출(또는 파일 끝)까지를
    한 블록으로 보고, 그 블록 안에서만 id 큰따옴표 문자열 리터럴을 찾는다.
    파일 전체를 무차별 스캔하지 않으므로 add_job 호출 밖의 주석·docstring 에
    있는 우연한 문구에 오염되지 않는다.

    ⚠ 커버리지 범위 = "정적 id 문자열"만. create_scheduler() 안에는 for 루프로
    id 를 동적 생성하는 add_job 호출이 2곳 있다 (popular_1030/1430/1900,
    complex_detail_JGC/ABYG/OBYG) — 이 6개는 문자열 소스 파싱만으로는 안전하게
    전개할 수 없어(루프 변수 실행이 필요) 이 함수는 그 블록을 만나면 id 를
    아예 추가하지 않고 건너뛴다(동적 블록도 오탐 없이 무시). 이 6개는
    routers/admin/scheduler.py 의 SCHEDULER_JOB_META 표시 메타에는 이미 개별
    등록돼 있으나, freshness_meta.py(FRESHNESS_ITEMS/MONITORING_EXEMPT) 쪽은
    세션 359 조사에서 다루지 않은 별도 사각지대로 남아 있다(다음 세션 후보).
    """
    call_starts = [m.start() for m in _ADD_JOB_CALL_PATTERN.finditer(source)]
    call_starts.append(len(source))

    ids: list[str] = []
    for i in range(len(call_starts) - 1):
        block = source[call_starts[i] : call_starts[i + 1]]
        static_match = _STATIC_ID_PATTERN.search(block)
        if static_match:
            ids.append(static_match.group(1))
        # 동적 id(f"..." 또는 job_id 변수)는 의도적으로 건너뜀 — docstring 답습.
    return ids


def create_scheduler() -> BackgroundScheduler:
    """크롤러 스케줄러 생성 (BackgroundScheduler — 메인 스레드 차단 없음).

    add_job 호출을 래핑해 같은 id 두 번 등록 시 즉시 ValueError. APScheduler
    기본 동작은 silent 허용이라 동적 id (예: f"popular_{hour}") 충돌 시 발견
    지연 — 시작 시점에 즉시 적발.
    """
    scheduler = BackgroundScheduler()
    _seen_ids: set[str] = set()
    _orig_add_job = scheduler.add_job

    def _add_job_unique(*args, **kwargs):
        job_id = kwargs.get("id")
        if job_id is None and len(args) >= 4:
            # add_job(func, trigger, args, kwargs, id, ...) 위치 인자 호환
            job_id = args[4] if len(args) > 4 else None
        if job_id is not None:
            if job_id in _seen_ids:
                raise ValueError(
                    f"create_scheduler: 같은 id '{job_id}' 가 두 번 등록됨 — "
                    "동적 id 생성 시 충돌 의심"
                )
            _seen_ids.add(job_id)
        return _orig_add_job(*args, **kwargs)

    scheduler.add_job = _add_job_unique  # type: ignore[method-assign]

    # A. 단지 발견 — 주 1회 일요일 새벽 3시
    scheduler.add_job(
        discover_all_regions,
        "cron",
        day_of_week="sun",
        hour=3,
        kwargs={"scheduler_job_id": "discover_regions"},
        id="discover_regions",
        name="새 단지 찾기",
        misfire_grace_time=3600,
    )

    # B. 매물 수집 — 매일 01:00 / 13:00 (jitter: mibunyang 08:00 월/목 크롤링과 충돌 회피)
    #    max_instances=1: 이전 배치가 안 끝났는데 다음 주기가 시작되는 중복 실행 차단
    #    (cron job 들과 일관성 — 동시 크롤은 같은 IP 부하·DB 경합 유발).
    #    ⚠ 세션 402: interval(12h) → cron 전환. APScheduler 3.11.3 IntervalTrigger 는
    #    start_date 를 `now + interval` 로 잡으므로(소스 실측) 재시작할 때마다 다음
    #    실행이 12시간 뒤로 밀린다 — 최근 14일 중 9일이 하루 1회만 돌았다(crawl_jobs
    #    실측). cron 은 벽시계 기준이라 재시작 횟수와 무관하게 하루 2회가 보장된다.
    #    01:00/13:00 ± 45분(jitter)은 release.md 시각표에서 네이버 호출 잡과 겹치지
    #    않는다 (01:00 childcare 는 data.go.kr 호출이라 네이버 IP 부하 무관, 13:00 공백).
    scheduler.add_job(
        crawl_articles_batch,
        "cron",
        hour="1,13",
        minute=0,
        jitter=2700,
        kwargs={"batch_size": CRAWL_BATCH_SIZE, "scheduler_job_id": "crawl_articles"},
        id="crawl_articles",
        name="단지 매물 가져오기",
        max_instances=1,
        misfire_grace_time=1800,
    )

    # C. 상세 보강 — 30분마다 (jitter: 같은 IP 네이버 요청 분산)
    #    max_instances=1: B 와 동일 — 30분 주기가 밀려도 중복 실행 안 함.
    scheduler.add_job(
        crawl_article_details,
        "interval",
        minutes=CRAWL_DETAIL_INTERVAL_MIN,
        jitter=900,
        kwargs={"batch_size": CRAWL_DETAIL_BATCH_SIZE, "scheduler_job_id": "crawl_details"},
        id="crawl_details",
        name="매물 상세 내용 채우기",
        max_instances=1,
        misfire_grace_time=900,
    )

    # C-2. 상세 백필 — 매일 00:20 / 12:20 (세션 402, PR #503 네이버 키 드리프트 대응)
    #    detail_crawled=True 인데 heating_type 등 3컬럼이 NULL 인 기존 매물(최근 30일
    #    활성만) 재크롤. crawl_details(C, 30분마다 상시)와 같은 상세 API 를 쓰므로
    #    "완전히 안 겹치는 시각"은 존재하지 않는다 — 대신 아래 두 시각을 고른 근거는
    #    ①대량 상세 API 소비 잡(complex_detail_APT/OPST interval, popular_1030/1430/1900,
    #    crawl_details 자체는 상시)과 겹치지 않는 새벽·정오 한산 시각이라는 점,
    #    ②B(crawl_articles, 01:00/13:00)와 40분 간격을 둬 그 배치 시작과 겹치지 않는다는
    #    점이다. 00:20 은 기존 스케줄 표(release.md §3-0) 전체를 통틀어 완전히 빈 슬롯,
    #    12:20 도 마찬가지(가장 가까운 게 10:45 popular 와 1시간35분 차, 13:00 B 와 40분 차).
    #    max_instances=1: 이전 배치가 안 끝났는데 다음 회차가 겹치는 것 방지.
    if BACKFILL_DETAIL_ENABLED:
        # 두 회차를 별도 잡으로 등록한다 — 배치 크기가 다르기 때문(위 상수 주석의 소요 시간 근거).
        # ⚠ jitter 를 두지 않는다: 소요 시간이 다음 크론과 겹치지 않게 계산한 시각이라
        #    앞뒤로 흔들리면 그 계산이 무너진다(특히 00:20 회차는 01:00 순찰과 여유가 적다).
        # ⚠ 루프로 묶지 않고 풀어 쓴다 — id 를 리터럴로 둬야 정적 추출기가 잡을 인식한다.
        #    루프 변수로 쓰면 tests/test_scheduler_monitoring_coverage.py 가 "동적 id 블록이
        #    늘었다"고 잡는다(그 잡이 감시 대상에서 조용히 빠지는 것을 막는 안전장치).
        scheduler.add_job(
            backfill_article_details,
            "cron",
            hour=0,
            minute=20,
            kwargs={"batch_size": _BACKFILL_DAWN_SIZE, "scheduler_job_id": "backfill_detail_dawn"},
            id="backfill_detail_dawn",
            name="빠진 정보 뒤늦게 채우기 00:20",
            max_instances=1,
            misfire_grace_time=1800,
        )
        scheduler.add_job(
            backfill_article_details,
            "cron",
            hour=12,
            minute=20,
            kwargs={"batch_size": _BACKFILL_NOON_SIZE, "scheduler_job_id": "backfill_detail_noon"},
            id="backfill_detail_noon",
            name="빠진 정보 뒤늦게 채우기 12:20",
            max_instances=1,
            misfire_grace_time=1800,
        )
        logger.info(
            "상세 백필 활성화: 00:20(배치 %d) · 12:20(배치 %d) = 하루 %d건",
            _BACKFILL_DAWN_SIZE, _BACKFILL_NOON_SIZE, _BACKFILL_DAWN_SIZE + _BACKFILL_NOON_SIZE,
        )

    # D. 시세 수집 — 주 1회 수요일 새벽 4시 (Phase 1)
    scheduler.add_job(
        collect_price_history,
        "cron",
        day_of_week="wed",
        hour=4,
        kwargs={"batch_size": CRAWL_BATCH_SIZE, "scheduler_job_id": "collect_prices"},
        id="collect_prices",
        name="단지 시세 기록 모으기",
        misfire_grace_time=3600,
    )

    # D-2. 시세 이력 소급 수집 — 매일 새벽 3시 30분
    #   complex_price_history 6행 미만 단지를 세대수 상위순으로 국토교통부
    #   실거래가 backfill. 가치지표(M)의 집계 대상 단지를 늘리는 근본 경로.
    #   공공데이터 API 라 네이버 IP 차단 무관. PUBLIC_DATA_ENABLED 토글 공유
    #   (같은 data.go.kr 키) — 토요일 collect_public_trades 와 시각 분리.
    if PUBLIC_DATA_ENABLED:
        scheduler.add_job(
            backfill_price_batch,
            "cron",
            hour=3,
            minute=30,
            kwargs={"batch_size": PUBLIC_PRICE_BACKFILL_BATCH_SIZE, "scheduler_job_id": "backfill_price"},
            id="backfill_price",
            name="옛 시세 채워 넣기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("시세 이력 소급 수집 활성화: 매일 03:30 (배치 %d)", PUBLIC_PRICE_BACKFILL_BATCH_SIZE)

    # E. 인기 단지 선제적 크롤링 — 하루 3회 (10:45, 14:45, 19:15 KST)
    #    기존 스케줄(B: 매일 01:00/13:00, C: 30분마다)과 충돌 회피
    #    2026-04-16: mibunyang 쿨다운 대응 — 기존 10:30/14:30/19:00에서 15분씩 시프트
    if POPULAR_CRAWL_ENABLED:
        for hour, minute, job_id in [(10, 45, "popular_1030"), (14, 45, "popular_1430"), (19, 15, "popular_1900")]:
            scheduler.add_job(
                crawl_popular_complexes,
                "cron",
                hour=hour,
                minute=minute,
                kwargs={"batch_size": POPULAR_CRAWL_BATCH_SIZE, "scheduler_job_id": job_id},
                id=job_id,
                name=f"자주 보는 단지 미리 갱신 {hour:02d}:{minute:02d}",
                max_instances=1,
                misfire_grace_time=1800,
            )
        logger.info("인기 단지 선제적 크롤링 활성화: 10:45, 14:45, 19:15 (배치 %d)", POPULAR_CRAWL_BATCH_SIZE)

    # K. 단지 상세 유형별 backfill — 매물유형별 독립 job
    #    APT(4.6만)·OPST(1.5만)는 interval 가속 (PR #19 매물상세 패턴 답습),
    #    소수 유형은 주 1회 07:00 cron 유지. jitter 로 같은 IP 다른 잡과 분산.
    if COMPLEX_DETAIL_ENABLED:
        # 대량 유형 — interval (env 시간 조절, 자동 감속 throttle 자율 보호)
        scheduler.add_job(
            crawl_complex_details_batch,
            "interval",
            hours=COMPLEX_DETAIL_APT_INTERVAL_HOURS,
            jitter=600,
            kwargs={"real_estate_type": "APT", "batch_size": COMPLEX_DETAIL_BATCH_SIZE,
                    "scheduler_job_id": "complex_detail_APT"},
            id="complex_detail_APT",
            name="아파트 단지 정보 채우기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        scheduler.add_job(
            crawl_complex_details_batch,
            "interval",
            hours=COMPLEX_DETAIL_OPST_INTERVAL_HOURS,
            jitter=600,
            kwargs={"real_estate_type": "OPST", "batch_size": COMPLEX_DETAIL_BATCH_SIZE,
                    "scheduler_job_id": "complex_detail_OPST"},
            id="complex_detail_OPST",
            name="오피스텔 단지 정보 채우기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        # ⚠ 알림 본문에 그대로 찍히는 이름이라 우리말만 쓴다(infra.md §텔레그램 알림 문구).
        #    plain_words.JOB_WORDS 와 같은 표현으로 맞춘다 — 두 곳이 어긋나면
        #    사장님이 화면과 알림에서 다른 이름을 보게 된다(세션 409 적대검증 HIGH-1).
        _DETAIL_TYPE_WORDS = {"JGC": "재건축", "ABYG": "아파트 분양권", "OBYG": "오피스텔 분양권"}
        # 소수 유형 — 주 1회 07:00 (요일 분산)
        for dow, rtype in [("tue", "JGC"), ("wed", "ABYG"), ("thu", "OBYG")]:
            scheduler.add_job(
                crawl_complex_details_batch,
                "cron",
                day_of_week=dow,
                hour=7,
                jitter=600,
                kwargs={"real_estate_type": rtype, "batch_size": COMPLEX_DETAIL_BATCH_SIZE,
                        "scheduler_job_id": f"complex_detail_{rtype}"},
                id=f"complex_detail_{rtype}",
                name=f"{_DETAIL_TYPE_WORDS[rtype]} 단지 정보 채우기",
                max_instances=1,
                misfire_grace_time=3600,
            )
        logger.info(
            "단지 상세 backfill 활성화: APT %dh interval / OPST %dh interval 매일, "
            "JGC·ABYG·OBYG 주1회 07:00 (배치 %d)",
            COMPLEX_DETAIL_APT_INTERVAL_HOURS, COMPLEX_DETAIL_OPST_INTERVAL_HOURS, COMPLEX_DETAIL_BATCH_SIZE,
        )

    # F. 공공데이터 실거래가 수집 — 주 1회 토요일 새벽 5시
    #    네이버 API 보완용, IP 차단 우려 없음
    if PUBLIC_DATA_ENABLED:
        from crawler.service import collect_public_trade_data

        scheduler.add_job(
            collect_public_trade_data,
            "cron",
            day_of_week="sat",
            hour=5,
            kwargs={"batch_size": PUBLIC_DATA_BATCH_SIZE, "scheduler_job_id": "collect_public_trades"},
            id="collect_public_trades",
            name="정부 실거래가 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("공공데이터 실거래가 수집 활성화: 토요일 05:00 (배치 %d)", PUBLIC_DATA_BATCH_SIZE)

    # F-1. 청약홈 오피스텔·민간임대 수집 — 주 1회 월요일 새벽 5시 (이슈 #323)
    #      공공데이터 실거래가(토요일 5시)와 겹치지 않게 요일 분리.
    if PUBLIC_DATA_ENABLED:
        from crawler.service_applyhome_officetel import collect_officetel_presale
        from crawler.service_applyhome_rental import collect_rental_presale

        scheduler.add_job(
            collect_officetel_presale,
            "cron",
            day_of_week="mon",
            hour=5,
            minute=0,
            kwargs={"scheduler_job_id": "collect_officetel_presale"},
            id="collect_officetel_presale",
            name="오피스텔 청약 공고 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        scheduler.add_job(
            collect_rental_presale,
            "cron",
            day_of_week="mon",
            hour=5,
            minute=30,
            kwargs={"scheduler_job_id": "collect_rental_presale"},
            id="collect_rental_presale",
            name="민간임대 청약 공고 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("청약홈 오피스텔·민간임대 수집 활성화: 월요일 05:00/05:30")

    # F-2. 공동주택 공시가격 수집 — 매월 15일 새벽 6시 30분 (V-WORLD, 네이버 0)
    if OFFICIAL_PRICE_ENABLED:
        from crawler.service_official_price import collect_official_prices

        scheduler.add_job(
            collect_official_prices, "cron",
            day="15", hour=6, minute=30,
            kwargs={"scheduler_job_id": "official_price"},
            id="official_price", name="정부 공시가격 받기",
            max_instances=1, misfire_grace_time=3600,
        )
        logger.info("공동주택 공시가격 수집 활성화: 매월 15일 06:30")

    # F-3. K-apt 관리비 연동 (V051) — 매칭 월 1회 + 관리비 매일.
    #      06:20 = 매월15일 06:30 official_price·일요일 06:40 api_version_probe 와
    #      겹치지 않는 빈 슬롯. 네이버 API 0건이라 IP 차단 무관(data.go.kr 전용).
    #      매칭 21일 14:50 — 1.5초 간격(세션 425)이면 약 6.1시간이라 06:20·12:40 관리비 회차가
    #      끝난 뒤 혼자 돌게 옮겼다(사장님 결정 2026-10-01, 옛 06:10).
    if KAPT_ENABLED:
        from crawler.service_kapt import collect_kapt_costs, match_kapt_complexes

        scheduler.add_job(
            match_kapt_complexes,
            "cron",
            day="21", hour=14, minute=50,
            kwargs={"scheduler_job_id": "kapt_match"},
            id="kapt_match", name="관리비 단지 연결하기",
            max_instances=1, misfire_grace_time=3600,
        )
        scheduler.add_job(
            collect_kapt_costs,
            "cron",
            hour=6, minute=20,
            kwargs={
                "batch_size": KAPT_COST_BATCH_SIZE,
                "scheduler_job_id": "kapt_costs",
            },
            id="kapt_costs", name="단지 관리비 받기 06:20",
            max_instances=1, misfire_grace_time=3600,
        )
        # 낮 회차 12:40 (세션 422) — 같은 함수·같은 배치를 하루 한 번 더 돌린다.
        #   왜: 2026-09-25 부터 K-apt 관리비 창구가 분 단위 간헐 오류(코드 04)를 내 06:20 회차가 사흘
        #   연속 실패했다. 아침 06시대가 가장 심하고 오후(09-25 14:47~17:21·09-26 14:28)에도 실패한 날이
        #   있다 — 낮 회차는 두 번째 기회일 뿐 완치가 아니다.
        #   호출량: 둘 다 되는 날엔 하루 1,000단지 · 호출 ≈25,000/일(아침만일 때 ≈12,000) —
        #   우리 자체 상한 kapt_api._quota_daily_limit 60,000·포털 운영계정 10만/일 안.
        #   겹침: 06:20 회차가 길어져도(최악 ≈152분 → 08:52) 12:40 과 안 겹치고, 겹치더라도
        #   collect_kapt_costs 의 already_running 가드(job_type 기준)가 새 회차를 건너뛴다.
        #   crawl_jobs 행은 scheduler_job_id="kapt_costs_noon" 으로 남는다 — 신선도 카드는 두 id 를 함께 센다.
        scheduler.add_job(
            collect_kapt_costs,
            "cron",
            hour=12, minute=40,
            kwargs={
                "batch_size": KAPT_COST_BATCH_SIZE,
                "scheduler_job_id": "kapt_costs_noon",
            },
            id="kapt_costs_noon", name="단지 관리비 받기 12:40",
            max_instances=1, misfire_grace_time=3600,
        )
        # 저녁 회차 21:00 (세션 426, 사장님 결정 2026-10-01) — 같은 함수·같은 배치를 하루 한 번 더.
        #   왜: 호출 간격이 1.5초(세션 425)라 한 회차 120분 예산이면 약 4,800콜뿐이다. 06:20·12:40
        #   두 회차로는 한 달 수요의 97~107% 라 새 달이 나온 단지를 다 못 따라간다 — 세 번째 회차로
        #   매월 최신 달을 유지한다. 밤에도 같은 속도 제한(33번째 콜부터 04)이 걸린다는 것은
        #   2026-10-01 23:30 실측으로 확인해 시간대로 피할 수는 없다.
        #   겹침: 다른 정기 K-apt 잡은 21:00 에 없고, 기존 행 재수집 스크립트(recollect_kapt_5ops.py)는
        #   20:30 이후 시작을 거부하고 20:45 에 멈춘다(이 스크립트는 crawl_jobs 행이 없어 이 회차가 못 보므로
        #   스크립트가 먼저 비켜 준다). 길면 약 23:30 에 끝나 01:30~ 밤 배치 창과 안 겹친다.
        #   매월 21일 14:50 매칭(약 6.1시간 + 꼬리)이 21:00 넘어 돌면 collect_kapt_costs 의
        #   match_running 가드가 이 회차를 건너뛴다 — 21일 저녁 회차는 대개 건너뛴다.
        scheduler.add_job(
            collect_kapt_costs,
            "cron",
            hour=21, minute=0,
            kwargs={
                "batch_size": KAPT_COST_BATCH_SIZE,
                "scheduler_job_id": "kapt_costs_evening",
            },
            id="kapt_costs_evening", name="단지 관리비 받기 21:00",
            max_instances=1, misfire_grace_time=3600,
        )
        logger.info(
            "K-apt 관리비 연동 활성화: 매칭 매월 21일 14:50 / 관리비 매일 06:20·12:40·21:00 (배치 %d)",
            KAPT_COST_BATCH_SIZE,
        )

    # G. 에어코리아 대기질 수집 — 매일 새벽 2시
    if AIR_QUALITY_ENABLED:
        from crawler.env_service import collect_air_quality

        scheduler.add_job(
            collect_air_quality,
            "cron",
            hour=2,
            kwargs={"batch_size": AIR_QUALITY_BATCH_SIZE},
            id="collect_air_quality",
            name="동네 공기질 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("에어코리아 대기질 수집 활성화: 매일 02:00 (배치 %d)", AIR_QUALITY_BATCH_SIZE)

    # H. 응급의료기관 수집 — 매월 첫째 월요일 새벽 3시
    #    ⚠ 배치 = 전량(0, 세션 394). 전국 기관목록 1콜 + 단지별 로컬 거리계산 구조라
    #    배치 크기가 API 호출 수와 무관 — 전량이어도 외부 호출은 여전히 1회다.
    #    옛 배치 100 은 이득 없이 커버리지만 깎았다(prod 실측 496/2,938만 채워짐).
    if EMERGENCY_ENABLED:
        from crawler.env_emergency import batch_label
        from crawler.env_service import collect_emergency_data

        scheduler.add_job(
            collect_emergency_data,
            "cron",
            day="1-7",
            day_of_week="mon",
            hour=3,
            kwargs={"batch_size": EMERGENCY_BATCH_SIZE},
            id="collect_emergency",
            name="응급실 위치 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info(
            "응급의료기관 수집 활성화: 매월 첫째 월요일 03:00 (배치 %s)",
            batch_label(EMERGENCY_BATCH_SIZE),
        )

    # I. 어린이집 수집 — 매월 첫째 목요일 새벽 1시
    #    ⚠ 01:00 고정 사유: CPMS cpmsapi030 키를 mibunyang 과 공유하는데, mibunyang
    #    childcare-detail 이 매일 04:30 에 일일 쿼터(1000건)를 전량 소진한다. 자정 리셋
    #    직후인 01:00 에 먼저 쓰고 지나가야 INFO-300 즉사를 피한다
    #    (06:00 시절 2026-07·08 두 달 연속 실패 — 세션 366). 04:30 이후로 되돌리지 말 것.
    #    ⚠ 배치 = 전량(0, 세션 393). 전량이어도 시군구당 1콜 + 런 내 캐시 재사용이라
    #    호출 상한 ~248콜(2026-09-05 prod 실측) — 일 쿼터 1,000 안에서 mibunyang 04:30
    #    소진 전에 선사용하는 구도는 그대로다.
    if CHILDCARE_ENABLED:
        from crawler.env_childcare import batch_label
        from crawler.env_service import collect_childcare_data

        scheduler.add_job(
            collect_childcare_data,
            "cron",
            day="1-7",
            day_of_week="thu",
            hour=1,
            kwargs={"batch_size": CHILDCARE_BATCH_SIZE},
            id="collect_childcare",
            name="어린이집 정보 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info(
            "어린이집 수집 활성화: 매월 첫째 목요일 01:00 (배치 %s)",
            batch_label(CHILDCARE_BATCH_SIZE),
        )

    # J. 범죄통계 수집 — 분기 1회 (1/4/7/10월 첫째 일요일 새벽 4시)
    #    경찰청 범죄통계 분기별 공표 주기에 맞춤
    if CRIME_STATS_ENABLED:
        from crawler.env_service import collect_crime_stats

        scheduler.add_job(
            collect_crime_stats,
            "cron",
            month="1,4,7,10",
            day="1-7",
            day_of_week="sun",
            hour=4,
            id="collect_crime_stats",
            name="동네 범죄 통계 받기",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("범죄통계 수집 활성화: 분기별 첫째 일요일 04:00")

    # L. 크롤링 모니터 — N분마다 장애 감지 + 텔레그램 알림
    if MONITOR_ENABLED:
        from crawler.monitor import run_monitor_job

        scheduler.add_job(
            run_monitor_job,
            "interval",
            minutes=MONITOR_INTERVAL_MIN,
            id="crawler_monitor",
            name="서버 일감 점검",
            max_instances=1,
            misfire_grace_time=600,
        )
        logger.info("크롤링 모니터 활성화: %d분 간격", MONITOR_INTERVAL_MIN)

    # M. 단지 가치지표 수집 — 매일 04:30
    #    complex_price_history 집계만 (네이버 API 호출 0) → IP 차단 무관.
    #    04:30 = 새벽 저트래픽 창(0~9시 매물 변동 거의 없음, services/cache.py 동적 TTL).
    #    09~12시 매물 등록 피크를 완전히 비켜감 — 배치 1000 집계가 사용자 요청과
    #    같은 micro 인스턴스 RAM 을 경합하지 않게 함 (세션 254 micro RAM 스파이크 답습).
    #    08:00 mibunyang 로컬 수집과도 더 멀어짐(기존 08:30=30분 분리 → 04:30=3.5h 분리).
    #    03:30 backfill·04:00 Wed 시세와 시작 instant 겹침 없음, 전부 max_instances=1·집계 전용.
    #    주1회→매일 전환: 집계 대상(시세 이력 보유 단지) 완주를 가속.
    #    세션 428: 매일 전 단지 다시 계산(배치 0 = 전량). 최근 6개월 매매 없는 단지는 마지막 값 유지.
    if COMPLEX_METRIC_ENABLED:
        scheduler.add_job(
            collect_complex_metrics,
            "cron",
            hour=4,
            minute=30,
            kwargs={"batch_size": COMPLEX_METRIC_RECOMPUTE_LIMIT, "scheduler_job_id": "collect_metrics"},
            id="collect_metrics",
            name="단지 가치 점수 계산",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info(
            "단지 가치지표 수집 활성화: 매일 04:30 (%s)",
            "전량" if COMPLEX_METRIC_RECOMPUTE_LIMIT <= 0 else f"배치 {COMPLEX_METRIC_RECOMPUTE_LIMIT}",
        )
        if os.getenv("COMPLEX_METRIC_BATCH_SIZE") is not None:
            # 값은 찍지 않는다 — 옛 줄이 남아 있다는 사실만(지울지는 사람 몫)
            logger.info("옛 설정 COMPLEX_METRIC_BATCH_SIZE 는 더는 쓰지 않습니다(세션 428) — 지워도 됩니다")

    # M-2. 빌링키 자동결제 — 매일 새벽 4시 50분 (정기결제 PR3, 세션 330).
    #   next_charge_at 도래분(status='active' AND is_default) 카드를 PortOne 빌링키 결제.
    #   PortOne 결제라 네이버 IP 차단 무관 → 04:50 = 04:30 metrics·03:50 vacuum 과 instant
    #   겹침 없는 빈 슬롯. 결제 대상이 소수(active 빌링키)라 가볍다. 3일 연속 실패 시 중단(알림).
    #   BILLING_AUTO_CHARGE_ENABLED=false 로 끄면 자동결제 미동작(카드 등록·첫결제는 무관).
    #   PAYMENT_ENABLED 가 꺼짐이면(기본, 세션 400 무료 전환) 이 잡을 아예 등록하지 않는다 —
    #   결제 API 7종이 403 인데 새벽 자동결제만 도는 모순을 막는다. 관리자 스케줄러 화면에서
    #   사라지는 것도 다른 토글과 같은 동작. 켤 땐 PAYMENT_ENABLED=true 후 재시작.
    if BILLING_AUTO_CHARGE_ENABLED and PAYMENT_ENABLED:
        scheduler.add_job(
            charge_due_billing_keys,
            "cron",
            hour=4,
            minute=50,
            kwargs={"scheduler_job_id": "billing_charge"},
            id="billing_charge",
            name="구독료 자동 결제",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("빌링키 자동결제 활성화: 매일 04:50")

    # 정기 VACUUM (ANALYZE) articles/trades — visibility map 재악화 차단 (세션 260).
    # 03:50 = 03:30 backfill·04:00 Wed 시세·04:30 metrics 와 instant 겹침 없는 빈 슬롯.
    # DB 전용(네이버 API 0) 이라 IP 차단 무관. VACUUM 은 ACCESS SHARE only = 비차단.
    if VACUUM_MAINTENANCE_ENABLED:
        scheduler.add_job(
            run_vacuum_maintenance,
            "cron",
            hour=3,
            minute=50,
            id="vacuum_maintenance",
            name="자료 보관함 정리",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("정기 VACUUM 유지보수 활성화: 매일 03:50 (articles/trades)")

    # data.go.kr API 버전 격변 감시 — 주 1회 일요일 06:40.
    # 2026-08-19 사고: data.go.kr 이 구버전 엔드포인트를 공지 체감 없이 폐기해
    # 수집기들이 조용히 죽었다. 엔드포인트 8개를 최소 호출로 찔러 폐기(코드 12)를
    # 조기 감지한다. 06:40 = 03:00 일요일 discover_regions·매월15일 06:30
    # official_price 와 겹치지 않는 빈 슬롯. 네이버 API 0건이라 IP 차단 무관이고,
    # 호출 8건이라 data.go.kr 일일 쿼터(mibunyang 공유) 영향도 무시 가능.
    if API_VERSION_MONITOR_ENABLED:
        from crawler.api_version_monitor import probe_api_versions

        scheduler.add_job(
            probe_api_versions,
            "cron",
            day_of_week="sun",
            hour=6,
            minute=40,
            kwargs={"scheduler_job_id": "api_version_probe"},
            id="api_version_probe",
            name="정부 자료 창구 살아있나 확인",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("data.go.kr API 버전 감시 활성화: 주 1회 일요일 06:40")

    # 상세 필드 채움률 드리프트 감시 — 매일 04:40.
    # 2026-09-13 사고: 네이버 상세 API 응답 키가 바뀌어(heating_type 등) 에러 없이
    # 4개 필드가 6개월 넘게 0% 채움으로 방치됐다. DB 집계만(네이버 API 0)이라
    # 04:30 collect_metrics·04:50 billing_charge 사이 빈 슬롯인 04:40 에 배치한다.
    if FIELD_DRIFT_MONITOR_ENABLED:
        from crawler.field_drift_monitor import run_field_drift_monitor

        scheduler.add_job(
            run_field_drift_monitor,
            "cron",
            hour=4,
            minute=40,
            kwargs={"scheduler_job_id": "field_drift_monitor"},
            id="field_drift_monitor",
            name="정보 안 채워지면 알림",
            max_instances=1,
            misfire_grace_time=3600,
        )
        logger.info("상세 필드 채움률 드리프트 감시 활성화: 매일 04:40")

    global _scheduler
    _scheduler = scheduler
    return scheduler
