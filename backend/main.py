"""FastAPI 백엔드 진입점

실행: cd backend && uvicorn main:app --reload
"""

import logging
import os
import re
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response

from auth.rate_limiter import RateLimitMiddleware
from config.payment_flags import require_payment_enabled
from routers import admin, articles, billing, complexes, health, live, mb, payment, regions, stats, users, verify
from services.cache import get_dynamic_ttl

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

IS_DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true")


def _sweep_stale_running_jobs() -> int:
    """서버 재시작 시 5분 이상 running 상태로 방치된 crawl_jobs 행을 cancelled 로 정리.

    uvicorn 강제 종료로 중단된 job 은 status=running·completed_at=NULL 채로 남음.
    sweep 임계가 모니터 알림 임계(1h) 와 같았던 v1 은 race 로 매 재시작마다 모니터
    false alarm 발생 (세션 208 텔레그램 2건 적발). 임계 5분으로 낮춰 새 backend
    startup 직후 모든 stale 즉시 정리. 가장 짧은 정상 interval = crawl_details 30분
    이라 5분 임계는 안전.

    상태는 'failed' 대신 'cancelled' — 모니터 실패율 통계에 잡히면 안 됨
    (강제종료는 실패 아니라 운영자 의도된 중단).

    cutoff 는 Python 측에서 계산해 paramize — PostgreSQL/SQLite 양쪽 호환
    (테스트 CI 가 SQLite, 운영이 PG 라서 NOW() - INTERVAL syntax 못 씀).

    error_message 는 기존 값을 보존하되 스윕 마커를 **항상 append** 한다 — 진행
    상황을 error_message 에 남기는 잡(official_price)이 COALESCE 로는 마커를 못 받아
    monitor 의 해소 사유 판정이 '수동 취소' 로 오분류했다 (세션 391).
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text

    from db.database import SessionLocal

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    now_utc = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        res = db.execute(text("""
            UPDATE crawl_jobs
            SET status = 'cancelled',
                completed_at = :now_utc,
                error_message = COALESCE(error_message || ' | ', '')
                                || 'stale running — swept on startup'
            WHERE status = 'running'
              AND completed_at IS NULL
              AND started_at < :cutoff
        """), {"cutoff": cutoff, "now_utc": now_utc})
        db.commit()
        return res.rowcount or 0
    except Exception as e:
        logger.warning("stale crawl_jobs sweep 실패: %s", e)
        db.rollback()
        return 0
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    logger.info("FastAPI 서버 시작")

    # 재시작 시 유령 running job 정리 (운영자 안전도 신호등 재발 방지)
    try:
        swept = _sweep_stale_running_jobs()
        if swept:
            logger.info("시작 시 stale running crawl_jobs %d개 정리", swept)
    except Exception as e:
        logger.warning("stale sweep 예외: %s", e)

    # JWKS 도달 자가진단 — ES256 로컬 검증이 실제로 가능한지 부팅 로그로 남긴다.
    # (모듈 import 시점이 아니라 여기서 부르는 이유는 deps._check_jwks_reachable docstring 참조)
    try:
        from deps import _check_jwks_reachable

        _check_jwks_reachable()
    except Exception as e:  # pragma: no cover - 자가진단이 기동을 막으면 안 됨
        logger.warning("JWKS 자가진단 예외: %s", e)

    # 스케줄러 단일 인스턴스 파일락 — uvicorn 여러 개가 뜨면(수동 재시작 경합 등)
    # 각자 스케줄러를 돌려 같은 잡을 중복 실행하던 것을 프로세스 간 차단(세션 341).
    # 락 못 잡으면(다른 backend 가 이미 보유) 스케줄러만 스킵, health/API 는 정상.
    scheduler = None
    lock = None
    try:
        from crawler.job_error_listener import register_job_listener
        from crawler.scheduler import create_scheduler
        from crawler.scheduler_lock import acquire_scheduler_lock

        lock = acquire_scheduler_lock()
        if lock is None:
            logger.warning("스케줄러 락 미획득 — 스케줄러 시작 스킵. health/API 는 정상 응답")
        else:
            scheduler = create_scheduler()
            register_job_listener(scheduler)  # 잡 예외/misfire 최후 안전망 (텔레그램 알림)
            scheduler.start()
            logger.info("크롤러 스케줄러 시작됨 (락 보유)")
    except Exception as e:
        logger.warning("크롤러 스케줄러 시작 실패 (DB 미연결?): %s", e)

    yield

    # scheduler / lock 각각 독립적으로 안전 정리 (한쪽 None 이어도 안전).
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("크롤러 스케줄러 종료됨")
    if lock is not None:
        try:
            lock.release()  # nullcontext sentinel 도 release() no-op 지원
        except Exception:  # release 예외가 다음 재시작 락 획득을 막지 않게
            pass
    logger.info("FastAPI 서버 종료")


app = FastAPI(
    title="네이버 아파트 매물 조회 API",
    description="네이버 부동산 데이터 기반 아파트 매물 조회/분석 API",
    version="1.0.0",
    lifespan=lifespan,
)

# GZip 압축 (1KB 이상 응답 자동 압축)
# compresslevel=6: 기본값 9 는 CPU 약 2.9배 더 쓰면서 압축률 이득은 0.3%p 뿐(세션 329 실측:
# 210KB JSON 응답 level9=8.6ms/87.1% vs level6=3.0ms/86.8%). 단일 집서버라 대형 응답 동시 다발
# 시 압축 CPU 가 threadpool 점유 → 9 의 추가 CPU 는 순손해. 6 이 CPU/압축률 균형점.
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)

# CORS 설정 (FRONTEND_URL: 콤마 구분 복수 도메인 지원)
_frontend_urls = os.getenv("FRONTEND_URL", "http://localhost:3000" if IS_DEBUG else "")
if not IS_DEBUG and not _frontend_urls:
    logger.critical("FRONTEND_URL 환경변수가 설정되지 않았습니다 (프로덕션 모드)")
allowed_origins = [u.strip() for u in _frontend_urls.split(",") if u.strip()]
if IS_DEBUG:
    for dev_url in ["http://localhost:3000", "http://localhost:3001"]:
        if dev_url not in allowed_origins:
            allowed_origins.append(dev_url)
# Rate Limiting 미들웨어 (CORS보다 먼저 등록 = CORS 이후에 실행)
app.add_middleware(RateLimitMiddleware)

# CORS 설정 (가장 먼저 실행되어야 preflight OPTIONS 처리 가능)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)


# 응답 시간 측정 미들웨어 (200ms 이상만 로깅)
@app.middleware("http")
async def log_response_time(request: Request, call_next):
    start = time.time()
    response: Response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    if elapsed_ms > 200:
        logger.warning("PERF %s %s %.0fms", request.method, request.url.path, elapsed_ms)
    return response


# 단지 상세 1건 정확 매칭 (/api/complexes/{no} — 하위 경로는 제외)
_COMPLEX_DETAIL_PATH = re.compile(r"/api/complexes/[^/]+")


# TTL 캐시 (get_dynamic_ttl 호출 최적화 — 60초 간격으로 갱신)
_cached_ttl: int = 300
_cached_ttl_time: float = 0


def _get_cached_ttl() -> int:
    global _cached_ttl, _cached_ttl_time
    now = time.time()
    if now - _cached_ttl_time > 60:
        _cached_ttl = get_dynamic_ttl()
        _cached_ttl_time = now
    return _cached_ttl


# 보안 헤더 미들웨어
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not IS_DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # GET 응답에 엔드포인트별 캐시 적용
    if (
        request.method == "GET"
        and request.url.path.startswith("/api/")
        and "Cache-Control" not in response.headers
        # 오류 응답(4xx/5xx)은 캐시 대상에서 제외한다 — 인증 게이트 엔드포인트
        # (price-stats·pyeong-details·price-history)가 비승인 사용자에게 401 을 주는데,
        # 그 401 이 private, max-age=3600 으로 캐시돼 **승인 직후에도 최대 1시간 잠긴 화면**이
        # 유지됐다(세션 396 라이브 실측). 404(kapt 미매칭)도 같은 기전으로 굳는다.
        # 성공 응답만 엔드포인트별 정책을 받고, 오류는 매번 서버 판정을 다시 받게 한다.
        and response.status_code < 400
    ):
        path = request.url.path
        if path.startswith("/api/regions"):
            response.headers["Cache-Control"] = "public, max-age=86400"  # 24시간 (정적 데이터)
        elif path.startswith("/api/admin/"):
            # 관리자 API 는 전부 no-store (세션 396). 카드 8종이 30~60초 간격으로 폴링하는데
            # 끝말 매칭(/progress 등)에 안 걸리는 것들이 기본 분기의 private, max-age=30 을 받아
            # 최대 30초 옛값을 보여줬다 (#466 과 같은 기전 — recrawl/status·scheduler-status·quota-status).
            # 관리자 전용·소량·폴링이라 브라우저 캐시 이득이 0 이므로 접두어 단위로 일반화한다.
            response.headers["Cache-Control"] = "no-store"
        elif _COMPLEX_DETAIL_PATH.fullmatch(path) or (
            path.startswith("/api/complexes/") and "/articles" in path
        ) or "price-history" in path:
            # 단지 상세 1건 + 매물 목록은 no-cache (세션 396 §5-N).
            # 크롤 완료 직후 FE 가 재조회해도 브라우저 HTTP 캐시(3600s/30s)가 답해 배지·건수가
            # 옛값이었다(9/9 01:53 단지 15111 실측). 클라 캐시는 React Query staleTime 이 이미
            # 담당하므로 HTTP 캐시는 정합성 구멍만 만든다.
            # no-store 가 아니라 no-cache 인 이유: 의미론 구분(저장은 허용, 재검증 없는 재사용만 금지)
            # 뿐이다 — ETag/Last-Modified 가 없어 실제 네트워크 동작은 no-store 와 같다(매번 원본 재전송, 의도된 동작).
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("/api/complexes/"):
            response.headers["Cache-Control"] = "private, max-age=3600"  # 1시간 (단지 하위 정보)
        elif path.endswith(("/crawl-status", "/collect-status", "/progress")):
            # 진행 상태 폴링 응답이 브라우저에 캐시되면 완료를 영영 감지 못 한다
            # (세션 395 라이브 재현: 폴링 44회 중 서버 도착 1회, 크롤이 끝나도 화면은 "크롤 중").
            # 진행률 폴링 계열은 전부 no-store — /api/admin/recrawl/progress(FE BulkRecrawlCard 3초 폴링)도
            # 기본 분기의 private, max-age=30 을 받아 같은 결함이었다 (세션 395 맹점 검증).
            # ⚠ 세션 396 이후 /api/admin/ 은 위 admin 분기가 먼저 잡는다. 이 줄은 /api/live/ 계열
            #   (crawl-status·collect-status)을 아래 동적 TTL 분기보다 앞서 no-store 로 잡기 위해 유지.
            # 아래 /api/live/ 의 max-age 는 실시간 검색·상세 결과 캐시라 의도된 동작이므로 그대로 둔다.
            response.headers["Cache-Control"] = "no-store"
        elif path.startswith("/api/live/"):
            response.headers["Cache-Control"] = f"private, max-age={_get_cached_ttl()}"
        else:
            response.headers["Cache-Control"] = "private, max-age=30"  # 30초 (기본)
    return response


# 라우터 등록
app.include_router(live.router, prefix="/api/live", tags=["실시간 크롤링"])
app.include_router(complexes.router, prefix="/api/complexes", tags=["단지"])
app.include_router(articles.router, prefix="/api/articles", tags=["매물"])
app.include_router(stats.router, prefix="/api", tags=["통계"])
app.include_router(regions.router, prefix="/api", tags=["지역"])
app.include_router(admin.router, prefix="/api/admin", tags=["관리자"])
app.include_router(users.router, prefix="/api/users", tags=["사용자"])
app.include_router(mb.router, prefix="/api/mb", tags=["미분양"])
app.include_router(verify.router, prefix="/api/verify", tags=["중개사 검증"])
# 결제·정기결제 라우터 — PAYMENT_ENABLED 게이트 (세션 400 무료 전환).
#   꺼져 있으면(기본) 아래 7 엔드포인트 전부 403. 라우터 레벨 dependencies 는 엔드포인트
#   인증 의존성보다 먼저 평가되므로 비로그인도 401 이 아니라 403 을 받는다.
#   webhook 도 함께 잠근다: 미완료 결제 0건·활성 빌링키 0건(세션 400 실측)이라 PortOne
#   재시도가 올 대상 자체가 없다. PAYMENT_ENABLED=true 로 켜면 웹훅 수신도 같이 재개된다.
app.include_router(
    payment.router,
    prefix="/api/payment",
    tags=["결제"],
    dependencies=[Depends(require_payment_enabled)],
)
app.include_router(
    billing.router,
    prefix="/api/payment/billing",
    tags=["빌링키 자동결제"],
    dependencies=[Depends(require_payment_enabled)],
)
app.include_router(health.router, tags=["헬스체크"])  # /health/db 심층 헬스체크 (외부 uptime 감시용)


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
