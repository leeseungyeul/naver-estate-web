"""크롤링 서비스 — 단지 가치지표 수집

complex_price_history 에서 단지별 가치지표 3필드를 집계해 complexes 테이블에
채운다. 네이버 API 호출 없이 DB 집계만 — IP 차단 위험 없음.

채우는 필드:
- nearby_median_price: 최근 6개월 매매(A1) 시세 중앙값
- jeonse_rate: 전세(B1) 중앙값 / 매매(A1) 중앙값 × 100
- recent_trades_6m: 최근 6개월 A1 시세 이력 레코드 수
"""

import logging
from collections import defaultdict

from sqlalchemy import exists, func

from crawler.metrics_helpers import _cutoff_month
from crawler.service_common import _checkpoint, fail_job_safely
from crawler.stats import compute_jeonse_rate, compute_median_price
from db.database import SessionLocal
from db.models import Complex, ComplexPriceHistory, CrawlJob
from utils import utcnow

logger = logging.getLogger(__name__)

# 매매 중앙값 계산 기간(개월) — 후보 조건과 계산이 같은 값을 써야 헛바퀴가 안 생긴다(세션 428)
_MEDIAN_MONTHS = 6

# commit 간격(확인한 단지 수). 운영 DB 왕복 약 9.5ms(10-03 실측) × 묶음 안 UPDATE 약 30건 ≈ 0.3초만 잠그게(세션 428).
_METRIC_COMMIT_EVERY = 50

# 체크포인트 저장·진행 로그 간격(확인한 단지 수). 전량(약 2.4만 단지)을 돌므로 공용 체크포인트 간격(5)을
# 그대로 쓰면 체크포인트 기록·로그가 수천 번 생긴다 — 이 잡만 넓게 잡는다(세션 428).
_METRIC_SAVE_EVERY = 500

# 최근 6개월 시세 줄을 하나도 못 읽어 멈춘 날의 잡 사유 — 알림에도 원문 그대로 나가게
# `plain_words._ERROR_RULES` 에 같은 머리말 규칙이 있다(세션 428 재검사관).
_NO_RECENT_ROWS_WORDS = "최근 6개월 시세 기록을 하나도 못 읽어서 가치 점수를 건드리지 않았어요 — 시세 기록을 확인해 주세요"


def _load_recent_prices(db, cutoff: str):
    """기준 달(cutoff, YYYYMM) 이후 A1·B1 줄을 한 번에 읽어 단지별로 묶는다.

    반환 (a1_prices, a1_counts, b1_prices):
    - a1_prices[단지] = price_avg 가 있는 A1 평균가 목록 (중앙값용 — calc_median_price 와 같은 조건)
    - a1_counts[단지] = A1 줄 수, price_avg 빈 줄 포함 (count_recent_price_records 와 같은 조건)
    - b1_prices[단지] = price_avg 가 있는 B1 평균가 목록
    """
    rows = (
        db.query(ComplexPriceHistory.complex_no, ComplexPriceHistory.trade_type, ComplexPriceHistory.price_avg)
        .filter(
            ComplexPriceHistory.trade_type.in_(("A1", "B1")),
            func.substr(ComplexPriceHistory.base_month, 1, 6) >= cutoff,
        )
        .all()
    )
    a1_prices: dict[str, list[int]] = defaultdict(list)
    a1_counts: dict[str, int] = defaultdict(int)
    b1_prices: dict[str, list[int]] = defaultdict(list)
    for complex_no, trade_type, price_avg in rows:
        if trade_type == "A1":
            a1_counts[complex_no] += 1
            if price_avg is not None:
                a1_prices[complex_no].append(price_avg)
        elif price_avg is not None:
            b1_prices[complex_no].append(price_avg)
    return a1_prices, a1_counts, b1_prices


def _compute_metrics(a1: list[int], b1: list[int], recent_count: int):
    """세 값 (중앙값, 전세가율, 최근 거래 수) — 계산 규칙은 옛 단지별 쿼리 경로와 같다."""
    median = compute_median_price(a1)
    jeonse_median = compute_median_price(b1) if b1 else None
    # 전세가율은 정의상 전세 < 매매 (100% 미만) 여야 한다.
    # complex_price_history 의 B1 데이터 84% 가 A1 과 동일값인 결함이
    # 있어, 전세중앙값 >= 매매중앙값이면 신뢰 불가로 보고 NULL 유지.
    if jeonse_median is not None and median is not None and jeonse_median >= median:
        jeonse_median = None
    return median, compute_jeonse_rate(median, jeonse_median), recent_count


def collect_complex_metrics(batch_size: int = 0, scheduler_job_id: str | None = None):
    """단지 가치지표 3필드를 매일 다시 계산 → 값이 바뀐 단지만 complexes UPDATE.

    세션 428 (사장님 결정 2026-10-03):
    - 다시 계산: 최근 6개월 A1(price_avg 있는 줄)이 있는 **모든 단지**의 세 값을 매 회차 다시 계산한다.
      옛 코드는 nearby_median_price 가 NULL 인 단지만 채워, 한 번 채운 값이 몇 달씩 낡았다
      (10-03 실측: 다시 계산하면 5% 이상 달라지는 단지 2,581곳·거래 수가 달라진 곳 14,570곳).
    - 최근 6개월 A1(price_avg 있는 줄)이 없는 단지는 읽지도 쓰지도 않는다 — 마지막 값 유지.
      (10-03 사장님 결정: 3월 일괄 수집분만 있는 단지 약 8천 곳이 기준 달이 넘어가는 날 한꺼번에 비지 않게)
    - 최근 6개월 매매 평균가를 하나도 못 읽었으면 아무것도 쓰지 않고 잡 failed(시세 기록 장애 신호).
    - batch_size <= 0 이면 전량, 양수면 세대수 큰 순으로 그만큼만 다시 계산한다(스케줄러 기본 0).
      양수면 매일 같은 상위 N곳만 계산된다(순환 없음 — 나머지는 옛 값 유지).
    - 쓰기: 세 값이 저장값과 같으면 UPDATE 하지 않는다(updated_at 그대로) — 쓰기량을 줄이려고
      (complexes 는 미분양도 읽는 공용 표).
    - 잡 기록: total = 다시 계산 대상 수, processed = 그중 확인을 마친 수(값이 그대로인 단지 포함).
      처리 수를 "바뀐 수"로 적으면 값이 그대로인 날 신선도 화면이 헛바퀴(처리 0/대상 N)로 빨갛게 된다.

    읽기: 최근 6개월 A1·B1 줄을 한 번에 읽어(10-03 실측 운영 약 20만 줄·0.5초) 파이썬에서 단지별로 묶는다 —
    옛 경로(단지마다 쿼리 3번)와 같은 결과(calc_median_price·count_recent_price_records 와 같은 조건).
    """
    db = SessionLocal()
    job = CrawlJob(
        job_type="complex_metric",
        scheduler_job_id=scheduler_job_id,
        status="running",
        started_at=utcnow(),
    )
    db.add(job)
    db.commit()
    job_id = job.id  # except 에서 깨진 세션의 ORM 속성 접근 피하기 위해 미리 확보

    try:
        if batch_size > 0:
            logger.warning(
                "가치지표 수집 배치 %d — 세대수 상위 %d곳만 다시 계산합니다(나머지는 옛 값 유지). 전량은 0",
                batch_size,
                batch_size,
            )

        cutoff = _cutoff_month(_MEDIAN_MONTHS)  # 읽기·후보 조건이 같은 기준 달을 쓰게 한 번만 계산
        a1_prices, a1_counts, b1_prices = _load_recent_prices(db, cutoff)

        if not a1_prices:
            job.status = "failed"
            job.total_items = 0
            job.processed_items = 0
            job.error_message = _NO_RECENT_ROWS_WORDS
            job.completed_at = utcnow()
            db.commit()
            logger.error("가치지표 수집 중단: 최근 6개월 매매 평균가 0건 — 아무것도 쓰지 않음")
            return

        # 후보 = 최근 A1(평균가 있음) 단지. 계산은 위에서 읽은 묶음(a1_prices)으로만 한다 — 두 번 읽은
        # 결과가 엇갈리면(그 사이 새 줄이 들어온 단지) 묶음에 없는 단지는 이번 회차에서 건너뛴다.
        has_recent_a1 = exists().where(
            ComplexPriceHistory.complex_no == Complex.complex_no,
            ComplexPriceHistory.trade_type == "A1",
            func.substr(ComplexPriceHistory.base_month, 1, 6) >= cutoff,
            ComplexPriceHistory.price_avg.isnot(None),
        )
        candidates = (
            db.query(
                Complex.complex_no,
                Complex.nearby_median_price,
                Complex.jeonse_rate,
                Complex.recent_trades_6m,
            )
            .filter(has_recent_a1)
            .order_by(Complex.total_household_count.desc().nullslast())
            .all()
        )
        recompute = [c for c in candidates if a1_prices.get(c.complex_no)]
        if batch_size > 0:
            recompute = recompute[:batch_size]
        total = len(recompute)

        checked = changed = 0
        for c in recompute:
            new_values = _compute_metrics(
                a1_prices[c.complex_no], b1_prices.get(c.complex_no, []), a1_counts[c.complex_no]
            )
            stored = (c.nearby_median_price, c.jeonse_rate, c.recent_trades_6m)
            if new_values != stored:
                median, jeonse_rate, recent = new_values
                db.query(Complex).filter(Complex.complex_no == c.complex_no).update(
                    {
                        Complex.nearby_median_price: median,
                        Complex.jeonse_rate: jeonse_rate,
                        Complex.recent_trades_6m: recent,
                        Complex.updated_at: utcnow(),
                    },
                    synchronize_session=False,
                )
                changed += 1
            checked += 1

            if checked % _METRIC_COMMIT_EVERY == 0:
                db.commit()
            if checked % _METRIC_SAVE_EVERY == 0:
                _checkpoint.save(db, job_id, {"processed": checked, "total": total})
                logger.info("가치지표 수집 중간 저장: %d/%d", checked, total)

        job.status = "completed"
        job.total_items = total
        job.processed_items = checked
        job.completed_at = utcnow()
        db.commit()
        _checkpoint.delete(db, job_id)
        logger.info(
            "가치지표 수집 완료: 확인 %d · 바뀜 %d · 그대로 %d",
            checked,
            changed,
            checked - changed,
        )

    except Exception as e:
        try:
            db.rollback()
            job.status = "failed"
            job.error_message = str(e)[:500]
            db.commit()
        except Exception:
            # 연결 끊김 등으로 같은 세션 마킹 실패 → 새 세션으로 보장 (세션 266)
            fail_job_safely(job_id, str(e))
        logger.exception("가치지표 수집 실패")
    finally:
        db.close()
