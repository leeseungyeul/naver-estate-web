"""NaverEstateAPI — 네이버 부동산 API 호출 클래스

데스크톱 앱의 메인 파일에서 추출한 코드. Qt 의존성 없음.
크롤러에서만 사용하며, 웹앱에서 직접 호출 금지.
"""

import logging
import re
import threading
import time

from curl_cffi import requests as cffi_requests

from shared.constants import (
    NAVER_LAND_BASE, NAVER_SEARCH_API,
    NAVER_COMPLEX_ARTICLES_API, NAVER_ARTICLE_DETAIL_API,
    NAVER_COMPLEX_API, JWT_TOKEN_LIFETIME, JWT_TOKEN_PATTERN,
)

logger = logging.getLogger(__name__)


class NaverEstateAPI:
    """네이버 부동산 API 호출 클래스

    - curl_cffi로 Chrome TLS 핑거프린트를 모방하여 봇 감지 우회
    - 매물 API는 JWT 토큰 + Referer 헤더 필수
    - 단지 페이지 HTML에서 JWT 자동 추출
    """

    PAGE_DELAY = 1.5
    MIN_REQUEST_INTERVAL = 1.0
    MAX_RETRIES = 3
    RETRY_DELAYS = [3, 5, 10]
    CACHE_TTL = 600  # 캐시 유효시간 10분

    _lock = threading.Lock()  # 클래스 레벨 상태 보호용 락
    _last_request_time = 0.0
    _session = None
    _jwt_token = None      # 매물 API 인증용 JWT
    _jwt_token_time = 0.0  # JWT 토큰 발급 시간 (time.monotonic())
    _custom_cookies = {}
    _cache: dict[str, tuple[float, object]] = {}  # {cache_key: (monotonic_ts, data)}

    @classmethod
    def _get_cached(cls, key):
        """캐시에서 데이터 조회 (TTL 초과 시 None, 스레드 안전)"""
        with cls._lock:
            entry = cls._cache.get(key)
            if entry and (time.monotonic() - entry[0]) < cls.CACHE_TTL:
                return entry[1]
            cls._cache.pop(key, None)
            return None

    @classmethod
    def _set_cached(cls, key, data):
        """캐시에 데이터 저장 (스레드 안전)"""
        with cls._lock:
            cls._cache[key] = (time.monotonic(), data)

    @classmethod
    def clear_cache(cls):
        """캐시 전체 초기화 (스레드 안전)"""
        with cls._lock:
            cls._cache.clear()

    @classmethod
    def set_custom_cookies(cls, cookie_string):
        """브라우저 쿠키를 세션에 추가 (스레드 안전)"""
        with cls._lock:
            cls._custom_cookies = {}
            if cookie_string:
                try:
                    for pair in cookie_string.split(';'):
                        pair = pair.strip()
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            cls._custom_cookies[key.strip()] = value.strip()
                except (ValueError, AttributeError):
                    cls._custom_cookies = {}
        cls.reset_session()

    @classmethod
    def _get_session(cls):
        """Chrome TLS 핑거프린트를 모방하는 세션 반환"""
        with cls._lock:
            if cls._session is None:
                cls._session = cffi_requests.Session(impersonate="chrome")
                try:
                    cls._session.get(f"{NAVER_LAND_BASE}/", timeout=10)
                except (OSError, ValueError, RuntimeError):
                    pass
                if cls._custom_cookies:
                    cls._session.cookies.update(cls._custom_cookies)
            return cls._session

    @classmethod
    def _ensure_jwt(cls, complex_id=None):
        """매물 API용 JWT 토큰 확보 (단지 페이지에서 추출, 50분 후 자동 갱신)"""
        with cls._lock:
            if cls._jwt_token and (time.monotonic() - cls._jwt_token_time) < JWT_TOKEN_LIFETIME:
                return cls._jwt_token
            cls._jwt_token = None  # 만료 또는 미발급 → 재발급

        session = cls._get_session()
        # 아무 단지 페이지나 방문하면 JWT가 HTML에 포함됨
        target_id = complex_id or "134062"
        token = None
        try:
            r = session.get(f"{NAVER_LAND_BASE}/complexes/{target_id}", timeout=10)
            if r.status_code == 200:
                token_match = re.search(JWT_TOKEN_PATTERN, r.text)
                if token_match:
                    token = token_match.group(1)
        except (OSError, ValueError, RuntimeError):
            pass

        with cls._lock:
            if token:
                cls._jwt_token = token
                cls._jwt_token_time = time.monotonic()
            return cls._jwt_token

    @classmethod
    def reset_session(cls):
        """세션 및 JWT 초기화 (스레드 안전)"""
        with cls._lock:
            if cls._session:
                try:
                    cls._session.close()
                except (OSError, RuntimeError):
                    pass
            cls._session = None
            cls._jwt_token = None
            cls._jwt_token_time = 0.0

    @staticmethod
    def _throttle():
        """요청 간 최소 간격 보장 (스레드 안전)"""
        with NaverEstateAPI._lock:
            now = time.monotonic()
            elapsed = now - NaverEstateAPI._last_request_time
            sleep_time = max(0, NaverEstateAPI.MIN_REQUEST_INTERVAL - elapsed)
            NaverEstateAPI._last_request_time = now + sleep_time
        if sleep_time > 0:
            time.sleep(sleep_time)

    @classmethod
    def _request_with_retry(cls, url, params=None, extra_headers=None):
        """Chrome TLS 모방 세션으로 GET 요청"""
        session = cls._get_session()

        for attempt in range(cls.MAX_RETRIES):
            cls._throttle()
            try:
                response = session.get(url, params=params, headers=extra_headers, timeout=10)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (401, 403):
                    # JWT 만료 또는 Referer 문제 → 토큰 재발급 후 재시도
                    with cls._lock:
                        cls._jwt_token = None
                    if attempt < cls.MAX_RETRIES - 1:
                        new_token = cls._ensure_jwt()  # 토큰 재발급 시도
                        # 재발급된 토큰으로 헤더 갱신
                        if new_token and extra_headers and 'Authorization' in extra_headers:
                            extra_headers = dict(extra_headers)
                            extra_headers['Authorization'] = f'Bearer {new_token}'
                        time.sleep(1)
                        continue
                    return {"error": f"API 인증 실패 (HTTP {response.status_code})"}
                elif response.status_code == 429:
                    delay = cls.RETRY_DELAYS[min(attempt, len(cls.RETRY_DELAYS) - 1)]
                    logger.warning("429 Rate Limit. %d초 대기 후 재시도 (%d/%d)", delay, attempt + 1, cls.MAX_RETRIES)
                    time.sleep(delay)
                    cls.reset_session()
                    session = cls._get_session()
                    continue
                else:
                    return {"error": f"API 요청 실패: 상태 코드 {response.status_code}"}
            except Exception as e:
                if attempt < cls.MAX_RETRIES - 1:
                    time.sleep(2)
                    cls.reset_session()
                    session = cls._get_session()
                    continue
                return {"error": f"데이터 조회 중 오류 발생: {str(e)}"}

        return {"error": "API 요청이 반복적으로 실패했습니다. 네트워크 연결을 확인해주세요."}

    @staticmethod
    def search_by_keyword(keyword, page=1, real_estate_type=None):
        """키워드로 단지 검색 (인증 불필요)"""
        cache_key = f"search:{keyword}:{page}:{real_estate_type or ''}"
        cached = NaverEstateAPI._get_cached(cache_key)
        if cached is not None:
            return cached
        params = {
            'keyword': keyword,
            'page': str(page),
        }
        if real_estate_type:
            params['realEstateType'] = real_estate_type
        result = NaverEstateAPI._request_with_retry(NAVER_SEARCH_API, params=params)
        if result and "error" not in result:
            NaverEstateAPI._set_cached(cache_key, result)
        return result

    @classmethod
    def get_complex_articles(cls, complex_id, page=1, same_address_group=False):
        """단지 ID로 매물 목록 조회 (JWT + Referer 필요)

        same_address_group=True 면 네이버가 묶은 대표 매물만 내려온다
        (sameAddrCnt = 묶인 등록 수). 실측(2026-10-02, 개봉아이파크 17538):
        개별 false=143건 / 그룹 true=33그룹.
        """
        # JWT 토큰 확보
        token = cls._ensure_jwt(complex_id)
        headers = {
            'Referer': f'{NAVER_LAND_BASE}/complexes/{complex_id}',
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'

        group_flag = 'true' if same_address_group else 'false'
        url = (
            f"{NAVER_COMPLEX_ARTICLES_API}/{complex_id}"
            f"?realEstateType=APT%3AABYG%3AJGC%3APRE%3AOPST%3AOBYG%3ARDV&tradeType="
            f"&tag=%3A%3A%3A%3A%3A%3A%3A%3A"
            f"&rentPriceMin=0&rentPriceMax=900000000"
            f"&priceMin=0&priceMax=900000000"
            f"&areaMin=0&areaMax=900000000"
            f"&oldBuildYears&recentlyBuildYears"
            f"&minHouseHoldCount&maxHouseHoldCount"
            f"&showArticle=false&sameAddressGroup={group_flag}"
            f"&minMaintenanceCost&maxMaintenanceCost"
            f"&priceType=RETAIL&directions="
            f"&page={page}&complexNo={complex_id}"
            f"&buildingNos=&areaNos=&type=list&order=rank"
        )
        return cls._request_with_retry(url, extra_headers=headers)

    @classmethod
    def get_article_detail(cls, article_no):
        """매물 상세 정보 조회 (캐시 적용)"""
        cache_key = f"detail:{article_no}"
        cached = cls._get_cached(cache_key)
        if cached is not None:
            return cached
        token = cls._ensure_jwt()
        headers = {
            'Referer': f'{NAVER_LAND_BASE}/articles/{article_no}',
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'
        url = f"{NAVER_ARTICLE_DETAIL_API}/{article_no}"
        result = cls._request_with_retry(url, extra_headers=headers)
        if result and "error" not in result:
            cls._set_cached(cache_key, result)
        return result

    @classmethod
    def get_complex_detail(cls, complex_id):
        """단지 상세 정보 조회 (면적 목록 포함, 캐시 적용)"""
        cache_key = f"complex:{complex_id}"
        cached = cls._get_cached(cache_key)
        if cached is not None:
            return cached
        token = cls._ensure_jwt(complex_id)
        headers = {'Referer': f'{NAVER_LAND_BASE}/complexes/{complex_id}'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        url = f"{NAVER_COMPLEX_API}/{complex_id}"
        result = cls._request_with_retry(url, extra_headers=headers)
        if result and "error" not in result:
            cls._set_cached(cache_key, result)
        return result

    @classmethod
    def get_complex_prices(cls, complex_id, trade_type="A1", area_no=None):
        """단지 시세 조회 (A1=매매, B1=전세, B2=월세)"""
        token = cls._ensure_jwt(complex_id)
        headers = {'Referer': f'{NAVER_LAND_BASE}/complexes/{complex_id}'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        params = {
            'complexNo': complex_id,
            'tradeType': trade_type,
            'year': '5',
            'priceChartChange': 'true',
            'type': 'table',
        }
        if area_no is not None:
            params['areaNo'] = str(area_no)
            params['areaChange'] = 'true'
        url = f"{NAVER_COMPLEX_API}/{complex_id}/prices"
        return cls._request_with_retry(url, params=params, extra_headers=headers)

    @classmethod
    def get_complex_real_prices(cls, complex_id, trade_type="A1", area_no=None):
        """단지 실거래가 조회 — /prices/real (국토교통부 데이터, 년 단위 장기 이력)"""
        token = cls._ensure_jwt(complex_id)
        headers = {'Referer': f'{NAVER_LAND_BASE}/complexes/{complex_id}'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        params = {
            'complexNo': complex_id,
            'tradeType': trade_type,
            'year': '5',
            'type': 'table',
        }
        if area_no is not None:
            params['areaNo'] = str(area_no)
        url = f"{NAVER_COMPLEX_API}/{complex_id}/prices/real"
        return cls._request_with_retry(url, params=params, extra_headers=headers)

    @classmethod
    def get_complex_schools(cls, complex_id):
        """단지 학군 정보 조회"""
        token = cls._ensure_jwt(complex_id)
        headers = {'Referer': f'{NAVER_LAND_BASE}/complexes/{complex_id}'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        url = f"{NAVER_COMPLEX_API}/{complex_id}/schools"
        return cls._request_with_retry(url, extra_headers=headers)
