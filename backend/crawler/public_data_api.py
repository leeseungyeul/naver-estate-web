"""공공데이터포털 아파트 매매 실거래가 API 클라이언트

국토교통부 아파트매매 실거래자료 API를 호출하여 실거래가 데이터를 수집한다.
IP 차단 우려 없이 안정적으로 시세 데이터를 보완할 수 있다.

API 문서: https://www.data.go.kr/data/15057511/openapi.do
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

# 공공데이터 API 기본 설정
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]
REQUEST_TIMEOUT = 15
MIN_REQUEST_INTERVAL = 0.3  # 초당 ~3건 (공공데이터 API TPS 제한 대응)


def _normalize_apt_name(name: str) -> str:
    """아파트명 정규화 — 공백/괄호/특수문자 제거 후 비교용 문자열 반환"""
    if not name:
        return ""
    import re
    # 괄호와 내용 제거: "현대아파트(1차)" → "현대아파트1차"
    normalized = re.sub(r"[(\[（]", "", name)
    normalized = re.sub(r"[)\]）]", "", normalized)
    # 공백, 하이픈, 점 제거
    normalized = re.sub(r"[\s\-·.]", "", normalized)
    # 소문자 통일 (영문 포함 단지명)
    normalized = normalized.lower()
    return normalized


_QUOTA_REASON_CODE = "22"  # data.go.kr "일일 요청 한도 초과" (kapt_api.QUOTA_REASON_CODE 와 같은 값)


def _error_envelope_code(data) -> str | None:
    """data.go.kr 오류 봉투(`cmmMsgHeader`)면 사유 코드(빈 문자열 가능), 아니면 None.

    HTTP 200 인데 정상 모양(`{"response": ...}`)이 아니라 게이트웨이 오류 봉투로 오는
    엔드포인트가 있다 — `{"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"returnReasonCode":
    "22", ...}}}` (kapt_api._error_envelope 실측 원문, 2026-09-25). 이걸 정상으로 받으면
    body 가 없어 totalCount 0 = "거래 없는 빈 달"로 캐시된다(세션 420).
    최상위에 `cmmMsgHeader` 만 오는 변형도 받는다.
    """
    if not isinstance(data, dict):
        return None
    wrapper = data.get("OpenAPI_ServiceResponse")
    header = wrapper.get("cmmMsgHeader") if isinstance(wrapper, dict) else None
    if header is None:
        header = data.get("cmmMsgHeader")
    if not isinstance(header, dict):
        return None
    return str(header.get("returnReasonCode") or "").strip()


class PublicDataAPI:
    """국토교통부 아파트매매 실거래자료 API

    - curl_cffi 사용 (impersonate 없이, 일반 HTTP 클라이언트로)
    - _type=json으로 JSON 응답 (XXE 방지)
    - 재시도 + 쓰로틀링 내장
    """

    _lock = threading.Lock()
    _last_request_time = 0.0
    _session: cffi_requests.Session | None = None
    _daily_call_count = 0
    _daily_call_date = ""
    # 세션 420: 마지막 get_apt_trades 실패의 종류 — "quota"(429 재시도 소진·자체 일일
    # 한도 게이트) / "other"(그 밖의 실패) / None(직전 호출 성공). 수집기가 "한도 초과로
    # 멈췄다"와 "다른 이유로 실패했다"를 구분해 쉬운 말로 기록하기 위함.
    _last_failure_kind: str | None = None
    # 세션 421: 창구가 응답 헤더로 알려주는 "오늘 남은 횟수"(x-ratelimit-remaining)와 하루 한도
    # (x-ratelimit-limit) — 200 에도 429 에도 온다(실측). 이 열쇠는 KOSPI·mibunyang 과 같이 쓰므로
    # 우리 쪽 일일 게이트(_check_daily_limit)만으로는 남의 사용분이 안 보인다. 헤더를 읽기만 한다(추가 호출 0).
    _rate_limit: dict | None = None

    @staticmethod
    def _header_int(headers, name: str) -> int | None:
        """응답 헤더 값을 정수로 — 없거나 숫자가 아니면 None (curl_cffi Headers 는 대소문자 무시)."""
        try:
            value = headers.get(name)
        except Exception:
            return None
        if isinstance(value, bytes):
            value = value.decode("ascii", "ignore")
        if not isinstance(value, str):
            return None
        try:
            # 같은 헤더가 두 번 오면 curl_cffi 가 "9755, 9754" 로 합쳐 준다(0.16.3 실측) — 첫 값만 받는다
            return int(value.split(",", 1)[0].strip())
        except ValueError:
            return None

    @classmethod
    def _remember_rate_limit(cls, response) -> None:
        """응답(상태 무관)의 남은 횟수 헤더를 보관 — 헤더가 없으면 이전 값을 그대로 둔다."""
        headers = getattr(response, "headers", None)
        if headers is None:
            return
        remaining = cls._header_int(headers, "x-ratelimit-remaining")
        if remaining is None:
            return
        limit = cls._header_int(headers, "x-ratelimit-limit")
        with cls._lock:
            cls._rate_limit = {
                "remaining": remaining, "limit": limit, "at": datetime.now(timezone.utc),
            }

    @classmethod
    def last_rate_limit(cls) -> dict | None:
        """마지막으로 본 창구 남은 횟수 — {"remaining", "limit", "at"} 또는 None(아직 못 봄)."""
        with cls._lock:
            return dict(cls._rate_limit) if cls._rate_limit else None

    @classmethod
    def _set_failure_kind(cls, kind: str | None) -> None:
        with cls._lock:
            cls._last_failure_kind = kind

    @classmethod
    def last_failure_kind(cls) -> str | None:
        """마지막 get_apt_trades 호출의 실패 종류 ("quota" | "other" | None=성공)."""
        with cls._lock:
            return cls._last_failure_kind

    @classmethod
    def _get_session(cls) -> cffi_requests.Session:
        with cls._lock:
            if cls._session is None:
                cls._session = cffi_requests.Session()
            return cls._session

    @classmethod
    def _throttle(cls):
        """요청 간 최소 간격 보장"""
        with cls._lock:
            now = time.monotonic()
            elapsed = now - cls._last_request_time
            sleep_time = max(0, MIN_REQUEST_INTERVAL - elapsed)
            cls._last_request_time = now + sleep_time
        if sleep_time > 0:
            time.sleep(sleep_time)

    @classmethod
    def _check_daily_limit(cls, max_calls: int = 9000) -> bool:
        """일일 호출 한도 체크 — DB 기반 (일일 10,000회, 안전 마진 10% 포함)"""
        from datetime import date

        from crawler.quota_db import increment_api_quota

        try:
            from db.database import SessionLocal
            result = increment_api_quota(SessionLocal, max_calls=max_calls)
            # in-memory 카운터도 동기화
            today = date.today().isoformat()
            with cls._lock:
                if cls._daily_call_date != today:
                    cls._daily_call_date = today
                    cls._daily_call_count = 0
                cls._daily_call_count += 1
            return result
        except Exception:
            # DB 실패 시 기존 in-memory 폴백
            today = date.today().isoformat()
            with cls._lock:
                if cls._daily_call_date != today:
                    cls._daily_call_date = today
                    cls._daily_call_count = 0
                if cls._daily_call_count >= max_calls:
                    return False
                cls._daily_call_count += 1
                return True

    @classmethod
    def _get_service_key(cls) -> str | None:
        return os.getenv("PUBLIC_DATA_API_KEY")

    @classmethod
    def get_apt_trades(
        cls,
        lawd_cd: str,
        deal_ymd: str,
        num_of_rows: int = 1000,
        page_no: int = 1,
    ) -> dict | None:
        """아파트 매매 실거래가 단일 페이지 조회

        Args:
            lawd_cd: 법정동코드 앞 5자리 (시군구코드)
            deal_ymd: 거래년월 (YYYYMM)
            num_of_rows: 페이지당 건수 (최대 1000)
            page_no: 페이지 번호

        Returns:
            JSON 응답 dict 또는 None (실패 시)
        """
        service_key = cls._get_service_key()
        if not service_key:
            logger.warning("PUBLIC_DATA_API_KEY 미설정 — 공공데이터 수집 건너뜀")
            cls._set_failure_kind("other")
            return None

        if not cls._check_daily_limit():
            logger.warning("공공데이터 API 일일 호출 한도 도달 — 수집 중단")
            cls._set_failure_kind("quota")
            return None

        params = {
            "serviceKey": service_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": str(num_of_rows),
            "pageNo": str(page_no),
            "_type": "json",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 NaverEstateWeb/1.0",
        }

        session = cls._get_session()
        last_was_429 = False  # 마지막 시도가 429 였으면 재시도 소진 = 한도 초과("quota")

        for attempt in range(MAX_RETRIES):
            cls._throttle()
            last_was_429 = False
            try:
                response = session.get(
                    BASE_URL,
                    params=params,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                cls._remember_rate_limit(response)

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception:
                        # 본문이 JSON 이 아님 — data.go.kr 은 `_type=json` 을 줘도 오류를 XML 로
                        # 주는 경우가 있다(kapt_api._body_or_raise 주석). 그 XML 이 한도 초과면
                        # 재시도 없이 "quota" 로 끝낸다(기다려도 안 바뀐다). 그 외는 기존처럼
                        # 아래 공통 예외 경로(재시도 후 "other")로 보낸다.
                        text = response.text or ""
                        if ("LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR" in text
                                or f"<returnReasonCode>{_QUOTA_REASON_CODE}<" in text):
                            logger.warning(
                                "공공데이터 API 한도 초과(XML 오류 응답) — LAWD=%s, YMD=%s",
                                lawd_cd, deal_ymd,
                            )
                            cls._set_failure_kind("quota")
                            return None
                        raise
                    # 오류 봉투(200 + cmmMsgHeader) — 재시도하지 않는다(한도는 기다려도 안 바뀐다).
                    envelope_code = _error_envelope_code(data)
                    if envelope_code is not None:
                        is_quota = envelope_code.lstrip("0") == _QUOTA_REASON_CODE
                        logger.warning(
                            "공공데이터 API 오류 봉투: 코드 %s — LAWD=%s, YMD=%s",
                            envelope_code or "없음", lawd_cd, deal_ymd,
                        )
                        cls._set_failure_kind("quota" if is_quota else "other")
                        return None
                    # 공공데이터 API 에러 응답 체크
                    header = (data.get("response") or {}).get("header") or {}
                    result_code = str(header.get("resultCode", "")).lstrip("0") or "0"
                    if result_code != "0":
                        result_msg = header.get("resultMsg", "알 수 없는 오류")
                        logger.warning(
                            "공공데이터 API 오류: %s (%s) — LAWD=%s, YMD=%s",
                            result_code, result_msg, lawd_cd, deal_ymd,
                        )
                        # 정상 모양인데 resultCode 22 = 일일 한도 초과(세션 420 검사관 M1)
                        cls._set_failure_kind(
                            "quota" if result_code == _QUOTA_REASON_CODE else "other")
                        return None
                    cls._set_failure_kind(None)
                    return data

                if response.status_code == 429:
                    last_was_429 = True
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.info("공공데이터 API 429 — %d초 대기 후 재시도", delay)
                    time.sleep(delay)
                    continue

                logger.warning(
                    "공공데이터 API HTTP %d — LAWD=%s, YMD=%s (시도 %d/%d)",
                    response.status_code, lawd_cd, deal_ymd, attempt + 1, MAX_RETRIES,
                )

            except Exception as e:
                logger.warning(
                    "공공데이터 API 요청 실패: %s — LAWD=%s, YMD=%s (시도 %d/%d)",
                    type(e).__name__, lawd_cd, deal_ymd, attempt + 1, MAX_RETRIES,
                )

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])

        cls._set_failure_kind("quota" if last_was_429 else "other")
        return None

    # 세션 359: 같은 (시군구, 월) 조합을 여러 단지가 반복 호출하는 낭비 발견
    # (backfill_price_batch 가 세대수 상위 단지 순회 시, 같은 구의 단지 N개가
    # 정확히 같은 API 응답을 매번 새로 받아옴 — data.go.kr 하루 10,000회 쿼터
    # 중 실제로는 4.8%만 쓰면서도 이 낭비 때문에 배치를 못 키우고 있었다).
    # 프로세스 내 메모리 캐시 — TTL 없음(과거 월 실거래는 사후 변경 없음, 당월만
    # 예외적으로 갱신될 수 있다). 한 수집 회차 안에서만 쓴다 — 두 수집기
    # (collect_public_trade_data·backfill_price_batch)가 시작·끝에 clear_trade_cache() 로
    # 비운다(세션 422 — 옛 주석은 재시작으로 초기화된다고 했으나 백엔드는 며칠씩 떠 있어
    # 다음 회차가 지난 회차의 달 목록을 그대로 재사용해 새 거래를 못 받았다).
    _trade_cache: dict[tuple[str, str], list[dict]] = {}
    _trade_cache_lock = threading.Lock()

    @classmethod
    def clear_trade_cache(cls) -> None:
        """거래 캐시만 비운다 — 세션·일일 카운터·rate_limit 은 그대로(reset() 과 다름).

        비우기 전 크기를 로그 한 줄로 남긴다(비어 있어도 0·0) — 재시작 뒤 첫 소급 로그에
        이 줄이 보이면 새 코드가 돈다는 증거다(세션 422).
        """
        with cls._trade_cache_lock:
            months = len(cls._trade_cache)
            trades = sum(len(v) for v in cls._trade_cache.values())
            cls._trade_cache.clear()
        logger.info("[정부 실거래가] 실거래가 캐시 비움: 달 %d개·거래 %d건", months, trades)

    @classmethod
    def get_all_apt_trades(cls, lawd_cd: str, deal_ymd: str) -> list[dict] | None:
        """아파트 매매 실거래가 전체 페이지 조회 (페이징 자동 처리, 캐싱).

        같은 (lawd_cd, deal_ymd) 조합은 한 수집 회차 안에서 1회만 API 호출 —
        같은 시군구의 여러 단지가 소급 수집될 때 중복 호출을 없앤다.

        Returns:
            거래 건별 dict 리스트. 정상 응답인데 거래가 없는 달은 [] (캐시함).
            어느 페이지든 호출이 실패하면 None — **캐시하지 않는다**(세션 420: 429 로
            실패한 달을 [] 로 캐시·반환해 "빈 달"로 위장하던 결함. 실패 종류는
            last_failure_kind() 로 확인).
        """
        cache_key = (lawd_cd, deal_ymd)
        with cls._trade_cache_lock:
            cached = cls._trade_cache.get(cache_key)
        if cached is not None:
            return cached

        all_items: list[dict] = []
        page_no = 1

        while True:
            data = cls.get_apt_trades(lawd_cd, deal_ymd, num_of_rows=1000, page_no=page_no)
            if not data:
                return None  # 실패 — 모은 일부를 캐시하지 않는다(반쪽 달 위장 방지)

            body = (data.get("response") or {}).get("body") or {}
            total_count = int(body.get("totalCount", 0))
            items_wrapper = body.get("items") or {}

            # items가 없거나 빈 경우
            item_list = items_wrapper.get("item") or []
            if isinstance(item_list, dict):
                item_list = [item_list]  # 단일 건이면 dict → list

            all_items.extend(item_list)

            # 전체 수집 완료 체크
            if len(all_items) >= total_count or not item_list:
                break
            page_no += 1

        with cls._trade_cache_lock:
            cls._trade_cache[cache_key] = all_items
        return all_items

    @classmethod
    def reset(cls):
        """세션 초기화 (거래 캐시도 함께 초기화 — 테스트 간 오염 방지)"""
        with cls._lock:
            if cls._session:
                try:
                    cls._session.close()
                except (OSError, RuntimeError):
                    pass
            cls._session = None
            cls._daily_call_count = 0
            cls._last_failure_kind = None
            cls._rate_limit = None
        with cls._trade_cache_lock:
            cls._trade_cache.clear()
