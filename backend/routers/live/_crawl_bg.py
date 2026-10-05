"""백그라운드 크롤 워커 — 매물 목록 수집 + 상세 크롤링 위임"""

import logging
import time

from crawler.utils import get_shared_throttle
from db.database import SessionLocal
from db.models import Article as ArticleModel
from db.models import Complex as ComplexModel
from services.cache import get_cache
from services.enricher import enrich_complex_detail
from services.naver_call_counter import record_call
from services.upsert import deactivate_complex_articles, delete_missing_articles, upsert_article
from shared.constants import NAVER_COMPLEX_ARTICLES_API, NAVER_LAND_BASE
from shared.domain.article import RealEstateArticle
from shared.naver_api import NaverEstateAPI
from utils import utcnow

from ._detail_worker import _crawl_details_for_complex
from ._shared import (
    INTER_PAGE_DELAY,
    PAGE_COMMIT_INTERVAL,
    _cache,
    _crawl_lock,
    _crawl_status,
    _update_crawl_status,
    release_complex,
    try_acquire_complex,
)

logger = logging.getLogger(__name__)


def _fetch_articles_all_trade_types(complex_no: str, page: int = 1):
    """Fetch articles with all trade types (A1=매매, B1=전세, B2=월세, B3=단기임대)."""
    token = NaverEstateAPI._ensure_jwt(complex_no)
    headers = {
        'Referer': f'{NAVER_LAND_BASE}/complexes/{complex_no}',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'

    url = (
        f"{NAVER_COMPLEX_ARTICLES_API}/{complex_no}"
        f"?realEstateType=APT%3AABYG%3AJGC%3APRE%3AOPST%3AOBYG%3ARDV"
        f"&tradeType=A1%3AB1%3AB2%3AB3"
        f"&tag=%3A%3A%3A%3A%3A%3A%3A%3A"
        f"&rentPriceMin=0&rentPriceMax=900000000"
        f"&priceMin=0&priceMax=900000000"
        f"&areaMin=0&areaMax=900000000"
        f"&oldBuildYears&recentlyBuildYears"
        f"&minHouseHoldCount&maxHouseHoldCount"
        f"&showArticle=false&sameAddressGroup=false"
        f"&minMaintenanceCost&maxMaintenanceCost"
        f"&priceType=RETAIL&directions="
        f"&page={page}&complexNo={complex_no}"
        f"&buildingNos=&areaNos=&type=list&order=rank"
    )
    record_call("crawl_articles_live")
    return NaverEstateAPI._request_with_retry(url, extra_headers=headers)


def _background_crawl(complex_no: str):
    """Run article crawl in background thread with per-page commits."""
    # 스케줄러 배치와 단지 소유권 공유 — 이미 진행 중이면 즉시 종료
    if not try_acquire_complex(complex_no):
        logger.info("live _background_crawl skip: %s 이미 크롤 진행 중", complex_no)
        _update_crawl_status(complex_no, status="already_running")
        return

    # acquire 성공 직후부터 outer finally 까지 반드시 실행되어야 release 누수 방지
    db = None
    try:
        # 스케줄러 배치와 동일한 글로벌 2초 브레이크 통과 — 네이버 IP 기준 폭주 방지
        get_shared_throttle("articles").wait()
        db = SessionLocal()
        try:
            with _crawl_lock:
                _crawl_status[complex_no] = {
                    "status": "running",
                    "phase": "articles",
                    "current_page": 0,
                    "article_count": 0,
                    "has_more": True,
                    "error": None,
                }
            all_article_nos = set()
            page = 1
            # V058 완주 판정 (세션 402) — 1페이지 오류는 아래에서 이미 return 하므로
            # 여기 도달했다는 것 자체가 1페이지 정상. 페이지≥2 오류로 break 하면 False.
            completed_all_pages = True

            # 기존 가격 일괄 조회 (N+1 방지)
            existing_prices = {
                row[0]: (row[1], row[2])
                for row in db.query(
                    ArticleModel.article_no, ArticleModel.numeric_price, ArticleModel.numeric_rent_price
                ).filter(
                    ArticleModel.complex_no == complex_no, ArticleModel.is_active == True
                ).all()
            }

            while True:
                result = _fetch_articles_all_trade_types(complex_no, page=page)
                if not result or "error" in result:
                    if page == 1:
                        _update_crawl_status(complex_no,
                            status="error",
                            error=str(result.get("error", "네이버 API 요청 실패") if result else "네이버 API 응답 없음"),
                        )
                        return
                    completed_all_pages = False
                    break

                article_list = result.get("articleList") or []
                if not article_list:
                    break

                for a_data in article_list:
                    article = RealEstateArticle.from_dict(a_data)
                    article.complex_no = complex_no
                    upsert_article(db, article, commit=False, track_price=True, existing_prices=existing_prices)
                    all_article_nos.add(article.article_no)

                if page % PAGE_COMMIT_INTERVAL == 0:
                    db.commit()
                    # FE 페이지별 refetch 반영 위해 articles 캐시 즉시 delete
                    get_cache("complexes", dynamic=True).delete(f"articles_default:{complex_no}")

                _update_crawl_status(complex_no, current_page=page, article_count=len(all_article_nos))

                if not result.get("isMoreData", False):
                    break
                page += 1
                time.sleep(INTER_PAGE_DELAY)

            _update_crawl_status(complex_no, has_more=False)

            # 진짜 0건(1페이지 정상 + 마지막 페이지까지 정상인데 매물 자체가 0건)이면
            # 유령 매물이 화면에 안 보이도록 소프트 비활성화. 페이지≥2 오류로 끊긴
            # 부분 목록(completed_all_pages=False)은 뒷 페이지 매물이 부당 삭제/비활성화
            # 되지 않도록 아래 두 처리 모두 생략한다(세션 402 ⑥-b).
            if completed_all_pages:
                if not all_article_nos:
                    deactivate_complex_articles(db, complex_no)
                else:
                    # 물리 삭제: 이번 크롤링에서 안 보인 매물 (네이버에 없는 매물)
                    delete_missing_articles(db, complex_no, all_article_nos)

            # Update last_crawled_at (+ 완주했으면 V058 articles_crawled_at 도 같이)
            complex_update = {"last_crawled_at": utcnow()}
            if completed_all_pages:
                complex_update["articles_crawled_at"] = utcnow()
            db.query(ComplexModel).filter(ComplexModel.complex_no == complex_no).update(
                complex_update
            )
            db.commit()

            # V069 관심 단지 호가 기록 (완주한 목록만, best-effort — services/price_watch.py)
            if completed_all_pages:
                from services.price_watch import record_snapshot_if_watched
                record_snapshot_if_watched(db, complex_no)

            # 단지정보 보강
            _update_crawl_status(complex_no, phase="enriching")
            cpx = db.query(ComplexModel).filter(ComplexModel.complex_no == complex_no).first()
            if cpx:
                enrich_complex_detail(db, complex_no)

            # Phase 2: 상세 정보 자동 크롤링
            _update_crawl_status(complex_no, phase="details", detail_phase="running")
            try:
                _crawl_details_for_complex(db, complex_no)
            except Exception as e:
                logger.warning("Detail crawl phase failed: %s → %s", complex_no, e)
            # done_partial이 설정되었으면 유지, 아니면 done으로 설정
            with _crawl_lock:
                current_status = _crawl_status.get(complex_no, {}).get("status")
            final_status = current_status if current_status == "done_partial" else "done"
            _update_crawl_status(complex_no, detail_phase="done", status=final_status)
            logger.info("Background crawl done: %s -> %d articles", complex_no, len(all_article_nos))

        except Exception as e:
            logger.exception("Background crawl error: %s", complex_no)
            _update_crawl_status(complex_no, status="error", error=str(e))
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
    except Exception as e:
        # outer 예외 (throttle/SessionLocal 실패 등) — 로그만 남기고 삼킨 뒤 finally guard 로 넘김
        logger.exception("Background crawl bootstrap error: %s", complex_no)
        _update_crawl_status(complex_no, status="error", error=str(e))
    finally:
        # ── Terminal 가드: 어떤 경로(throttle/SessionLocal/except 재예외/BaseException)로
        #    종료되든 status 가 반드시 terminal 이 되도록 강제. FE 폴링 무한 대기 차단.
        #    TERMINAL 에 "started"/"running" 의도적 제외 — 이들 잔존 = 스레드가 본체 진입
        #    실패 또는 비정상 종료를 의미하므로 error 전환이 정당.
        TERMINAL = {"done", "done_partial", "error", "already_running"}
        with _crawl_lock:
            st = _crawl_status.get(complex_no)
            if st is None:
                _crawl_status[complex_no] = {
                    "status": "error",
                    "error": "크롤 스레드가 상태 세팅 전 종료됨",
                }
                need_log = True
                from_status = None
            elif st.get("status") not in TERMINAL:
                _crawl_status[complex_no]["status"] = "error"
                _crawl_status[complex_no].setdefault("error", "크롤 스레드가 비정상 종료됨")
                need_log = True
                from_status = st.get("status")
            else:
                need_log = False
                from_status = None
        # logger 는 락 밖 I/O
        if need_log:
            logger.warning("crawl terminal guard: %s status=%s → error", complex_no, from_status)

        # 기존 정리 로직 — db/release/캐시
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
        release_complex(complex_no)
        # 크롤링 완료 마커 설정 (start-crawl 중복 방지, 동적 TTL 적용)
        _cache.set(f"crawl_done:{complex_no}", True)
        # complexes.py의 필터/통계/상세 캐시도 무효화 (레지스트리 기반, 순환 import 없음)
        complexes_cache = get_cache("complexes", dynamic=True)
        complexes_cache.delete(f"filter_options:{complex_no}")
        complexes_cache.delete(f"price_stats:{complex_no}")
        complexes_cache.delete(f"complex_detail:{complex_no}")
        complexes_cache.delete(f"articles_default:{complex_no}")
        complexes_cache.delete(f"pyeong_details:{complex_no}")
        # /api/stats 캐시 무효화 — 크롤 완료로 article_count 변동 가능
        get_cache("stats", dynamic=True).delete("db_stats")
