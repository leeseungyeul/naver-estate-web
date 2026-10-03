"""data.go.kr API 버전 격변 자동 감시 — 폐기된 엔드포인트를 주 1회 프로브해 조기 경보.

배경 (2026-08-19 실사고)
------------------------
data.go.kr 이 "인증 예외 처리"를 종료하면서 구버전 엔드포인트(AptListService3,
AptBasisInfoServiceV4 등)가 **체감할 공지 없이** 한꺼번에 죽었다. 응답은
``NO_OPENAPI_SERVICE_ERROR``("해당 오픈API 서비스가 없거나 폐기됨",
returnReasonCode "12"). 이 프로젝트와 자매 프로젝트(mibunyang) 둘 다 수집기 장애를
겪었고, 다음 정기 수집이 돌 때까지 아무도 몰랐다.

감지 원리 (라이브 실측 확정)
----------------------------
- **살아있는 서비스**: 필수 파라미터가 없어도 ``NO_MANDATORY_REQUEST_PARAMETERS_ERROR``
  (코드 11) 또는 정상 응답을 준다 → 서비스 실존 증거.
- **폐기된 서비스**: ``NO_OPENAPI_SERVICE_ERROR`` + returnReasonCode ``"12"``
  (HTTP 400) → 죽음 확정.
- 따라서 **유효한 파라미터 없이 serviceKey 만** 넣고 호출해도 생사 판별이 된다.
  numOfRows=1 수준의 최소 호출이라 일일 쿼터(10,000회 mibunyang 공유) 영향 무시 가능.
- ``SERVICE_KEY_IS_NOT_REGISTERED_ERROR``(코드 30)·``SERVICETIMEOUT_ERROR``(코드 05)
  같은 간헐 오류는 **폐기가 아니다** — ``degraded`` 로 분류해 로그만 남기고 알림하지
  않는다(간헐 오류로 새벽에 알림이 울리는 오탐 방지).

odcloud.kr 은 응답 포맷이 다르다 (2026-08-29 라이브 실측)
--------------------------------------------------------
같은 data.go.kr 이라도 ``api.odcloud.kr`` 계열은 ``returnReasonCode`` 를 아예 쓰지
않고 자체 포맷을 쓴다. 위 apis.data.go.kr 판정기(12=dead / 11=alive / 30·05=degraded)
를 그대로 적용하면 **모든 응답이 판정 근거 없음 → degraded** 로 뭉개져 감시가 무력화된다.
그래서 odcloud 전용 판정기(``classify_odcloud_response``)를 따로 둔다.

라이브 실측 결과(키 값 미출력, 최소 파라미터 1회 호출):

===============================  ======  =========================================
상황                              HTTP    본문
===============================  ======  =========================================
정상(GET 목록형)                  200     ``{"currentCount":1,"data":[...]}``
정상(국세청 POST)                 200     ``{"request_cnt":1,"status_code":"OK",...}``
**폐기/경로 없음**                404     ``{"code":-3,"msg":"등록되지 않은 서비스 입니다."}``
인증키 문제(폐기 아님)            401     ``{"code":-4,"msg":"등록되지 않은 인증키 입니다."}``
바디 형식 오류(폐기 아님)         411     ``{"status_code":"REQUEST_DATA_MALFORMED"}``
===============================  ======  =========================================

→ **dead 는 ``code: -3`` 하나뿐**이다. ``-4``(키)·``411``(바디)은 서비스가 실존하기에
나오는 응답이므로 폐기가 아니다. 여기서도 "alive 는 양성 증거가 있을 때만" 원칙을
유지한다 — 빈 응답·HTML 게이트웨이 페이지는 degraded.

⚠ 국세청 사업자 API(status·validate)는 **POST 전용**이라 GET 으로 찌르면 405 가 떠서
생사를 가릴 수 없다. 레지스트리 항목마다 method/body 를 지정해 실제 코드와 같은 방식으로
프로브한다(``b_no`` 는 존재하지 않는 번호 1개 — 조회만 하고 부수효과 0).

⚠ **오퍼레이션 단위로 등록한다.** 같은 서비스(nts-businessman/v1) 아래여도 status 와
validate 는 별개 오퍼레이션이라 한쪽만 폐기·개편될 수 있다. 서비스가 통째로 죽을 때만
잡히면 되는 청약홈(4 오퍼레이션 → 대표 1개)과 달리, 국세청 두 오퍼레이션은 각각
공인중개사 **휴폐업 차단**(status)과 **가입 진위확인**(validate)의 생명줄이라 둘 다 건다.

네이버 API 는 0건이라 IP 차단 무관(.claude/rules/infra.md §IP 차단 방지 대상 아님).
"""

import logging
import os
import time

import requests

from crawler.env_common import _complete_job, _fail_job, _record_job
from db.database import SessionLocal

logger = logging.getLogger(__name__)

# 응답 포맷 계열 — 판정기를 고르는 스위치. 레지스트리 항목의 "flavor" 로 지정하며,
# 생략하면 apis.data.go.kr 계열로 본다(기존 8종 무변경).
FLAVOR_DATAGOKR = "datagokr"  # apis.data.go.kr — returnReasonCode 계열
FLAVOR_ODCLOUD = "odcloud"    # api.odcloud.kr — {"code": -N, "msg": ...} 계열

# ⚠ 새 data.go.kr API 를 코드에 도입하면 **여기 1줄 추가가 의무**다.
#   그러지 않으면 그 API 만 감시 사각지대로 남아 2026-08-19 사고가 그대로 재현된다.
#   name = 사람이 텔레그램에서 읽을 이름, url = 실제 코드가 호출하는 엔드포인트.
#   (url 은 각 API 모듈의 상수와 동일해야 한다 — 변경 시 양쪽 답습)
#   odcloud 계열은 "flavor": FLAVOR_ODCLOUD 를 반드시 붙인다 — 빠뜨리면 판정기가
#   어긋나 모든 응답이 degraded 로 뭉개져 그 API 만 감시 사각지대가 된다.
PROBE_REGISTRY: list[dict] = [
    # crawler/public_data_api.py BASE_URL — 실제 호출 창구는 Dev(상세) 버전.
    # 일반 버전(RTMSDataSvcAptTrade)을 감시하던 동안 실창구가 사각지대였던 결함 수정 (2026-10-02).
    {
        "name": "국토교통부 아파트 매매 실거래가",
        "url": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    },
    # crawler/emergency_api.py EMERGENCY_LIST_URL
    {
        "name": "응급의료기관 목록",
        "url": "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire",
    },
    # crawler/emergency_api.py EMERGENCY_BEDS_URL (세션 417 — 응급실 병상은 이 op 에서만 받는다)
    {
        "name": "응급실 실시간 가용병상",
        "url": "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire",
    },
    # crawler/air_quality_api.py NEARBY_STATION_URL
    {
        "name": "에어코리아 근접 측정소",
        "url": "https://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getNearbyMsrstnList",
    },
    # crawler/air_quality_api.py REALTIME_AIR_URL
    {
        "name": "에어코리아 실시간 대기질",
        "url": "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty",
    },
    # K-apt 공동주택 연동 4종 — 2026-08-19 격변으로 구버전(3·V4)이 죽어 신버전으로 이동한 것들.
    # 같은 격변이 재발하면(V5 → V6 등) 여기서 가장 먼저 잡힌다.
    {
        "name": "K-apt 시도별 단지 목록 (AptListService4)",
        "url": "https://apis.data.go.kr/1613000/AptListService4/getSidoAptList4",
    },
    {
        "name": "K-apt 단지 기본정보 (AptBasisInfoServiceV5)",
        "url": "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5",
    },
    {
        "name": "K-apt 개별사용료 (AptIndvdlzManageCostServiceV3)",
        "url": "https://apis.data.go.kr/1613000/AptIndvdlzManageCostServiceV3/getHsmpHeatCostInfoV3",
    },
    # ⚠ 공용관리비는 반드시 **첫 op**(COMMON_COST_OPS[0] = getHsmpLaborCostInfoV3)를 찌른다.
    #   수집기가 "첫 op 가 비면 그 서비스·월 전체 미공개" 로 보고 나머지 16콜을 건너뛰고
    #   (kapt_api._collect_ops), 카나리도 그 op 하나로 API 생사를 판정하기 때문이다 —
    #   즉 첫 op 가 죽으면 관리비 수집이 통째로 "전량 미공개" 로 보인다. 감시가 다른 op 를
    #   보고 있으면 정작 그 단일 실패점을 못 본다.
    {
        "name": "K-apt 공용관리비 (AptCmnuseManageCostServiceV3)",
        "url": "https://apis.data.go.kr/1613000/AptCmnuseManageCostServiceV3/getHsmpLaborCostInfoV3",
    },
    # ── odcloud.kr 계열 3종 (응답 포맷이 달라 flavor 지정 필수 — 모듈 docstring 참조) ──
    # crawler/applyhome_officetel_api.py BASE_URL + 오퍼레이션.
    # 4개 오퍼레이션이 같은 서비스(ApplyhomeInfoDetailSvc/v1) 아래 있어, 서비스가
    # 통째로 폐기되면 넷 다 죽는다 → 대표 1개만 찔러도 격변이 잡힌다(쿼터 절약).
    {
        "name": "청약홈 오피스텔·민간임대 분양정보 (ApplyhomeInfoDetailSvc/v1)",
        "url": (
            "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/"
            "getUrbtyOfctlLttotPblancDetail"
        ),
        "flavor": FLAVOR_ODCLOUD,
    },
    # crawler/business_api.py STATUS_URL — 공인중개사 검증(휴폐업 차단)의 생명줄.
    # ⚠ POST 전용이라 GET 으로 찌르면 405 → 생사 판별 불가. 실제 코드와 같은 방식으로 부른다.
    #   body 의 b_no 는 존재하지 않는 번호 1개 — 조회 전용이라 부수효과 0.
    {
        "name": "국세청 사업자 영업상태 (nts-businessman/v1/status)",
        "url": "https://api.odcloud.kr/api/nts-businessman/v1/status",
        "flavor": FLAVOR_ODCLOUD,
        "method": "POST",
        "json": {"b_no": ["0000000000"]},
    },
    # crawler/business_api.py VALIDATE_URL — 공인중개사 **가입 검증**(진위확인)의 생명줄.
    # ⚠ status 와 같은 서비스 이름을 쓰지만 **오퍼레이션이 다르다**. data.go.kr 은
    #   오퍼레이션 단위로도 폐기·개편되므로(2026-08-19 격변이 그랬다), status 하나만
    #   감시하면 validate 만 죽었을 때 가입 검증이 조용히 막혀도 아무도 모른다.
    #   bodies 스키마도 status(b_no 배열)와 달리 businesses 배열이라 따로 지정한다.
    #   b_no 는 존재하지 않는 번호 1개 — 조회 전용이라 부수효과 0.
    {
        "name": "국세청 사업자 진위확인 (nts-businessman/v1/validate)",
        "url": "https://api.odcloud.kr/api/nts-businessman/v1/validate",
        "flavor": FLAVOR_ODCLOUD,
        "method": "POST",
        "json": {"businesses": [{"b_no": "0000000000", "p_nm": "", "start_dt": ""}]},
    },
    # crawler/crime_stats_api.py CRIME_STATS_URL (uddi 포함 전체 URL 이 곧 데이터셋 주소)
    {
        "name": "경찰청 범죄통계 (3074462)",
        "url": (
            "https://api.odcloud.kr/api/3074462/v1/"
            "uddi:ae109087-8690-4cb5-bda9-a7876a92f3b8"
        ),
        "flavor": FLAVOR_ODCLOUD,
    },
]

REQUEST_TIMEOUT = 15
# 호출 간 간격 — data.go.kr TPS 제한 보호 (public_data_api.MIN_REQUEST_INTERVAL 0.3 보다 여유).
PROBE_INTERVAL_SECONDS = 0.5

# 폐기 확정 신호. returnReasonCode "12" 또는 에러 문자열 어느 쪽으로 와도 잡는다
# (data.go.kr 은 같은 상황을 XML/JSON·본문/헤더로 제각각 표현한다).
DEAD_REASON_CODE = "12"
DEAD_ERROR_TOKEN = "NO_OPENAPI_SERVICE_ERROR"

# ── odcloud 판정 신호 (2026-08-29 라이브 실측, 모듈 docstring §odcloud 표) ──
# 폐기/경로 없음: {"code":-3,"msg":"등록되지 않은 서비스 입니다."} (HTTP 404)
ODCLOUD_DEAD_CODE = -3
ODCLOUD_DEAD_TOKEN = "등록되지 않은 서비스"
# 인증키 문제(-4)·바디 형식 오류(411) 등은 **서비스가 실존하기에** 나오는 응답이다.
ODCLOUD_ALIVE_KEYS = ("currentCount", "matchCount", "totalCount", "status_code", "data")

STATUS_ALIVE = "alive"
STATUS_DEAD = "dead"
STATUS_DEGRADED = "degraded"


def _extract_reason_code(body: str) -> str | None:
    """응답 본문에서 returnReasonCode 값 추출 — XML/JSON 양쪽 포맷 대응.

    XML:  ``<returnReasonCode>12</returnReasonCode>``
    JSON: ``"returnReasonCode": "12"`` (공백·따옴표 유무가 응답마다 다르다)

    정규식 없이 토큰 뒤 첫 숫자 뭉치를 읽는다 — 포맷 변덕에 둔감한 최소 구현.
    """
    idx = body.find("returnReasonCode")
    if idx < 0:
        return None
    tail = body[idx + len("returnReasonCode") : idx + len("returnReasonCode") + 40]
    digits = ""
    for ch in tail:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return digits or None


def classify_response(body: str) -> str:
    """응답 본문 → alive / dead / degraded 분류.

    dead 판정은 **폐기 신호가 명시적으로 보일 때만** — 그 외는 전부 alive 또는
    degraded 다. "확신이 없으면 알림하지 않는다"가 이 감시기의 기본 태도(오탐이
    반복되면 진짜 경보까지 무시하게 된다).
    """
    if body is None:
        return STATUS_DEGRADED

    if DEAD_ERROR_TOKEN in body or _extract_reason_code(body) == DEAD_REASON_CODE:
        return STATUS_DEAD

    # 파라미터 부족(코드 11)은 "서비스가 살아서 요청을 검증했다"는 증거다.
    if "NO_MANDATORY_REQUEST_PARAMETERS_ERROR" in body:
        return STATUS_ALIVE

    # 서비스키 미등록(30)·타임아웃(05)·트래픽 초과(22) 등 — 폐기 아님, 로그만.
    for token in (
        "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
        "SERVICETIMEOUT_ERROR",
        "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
        "SERVICE_ACCESS_DENIED_ERROR",
        "UNKNOWN_ERROR",
        "APPLICATION_ERROR",
        "HTTP_ERROR",
    ):
        if token in body:
            return STATUS_DEGRADED

    reason = _extract_reason_code(body)
    if reason is not None:
        # 알 수 없는 에러코드 — 폐기로 단정하지 않는다. 00 계열이면 정상 응답.
        return STATUS_ALIVE if reason.strip("0") == "" else STATUS_DEGRADED

    # ⚠ "죽음 신호가 없다"는 곧 "살아있다"가 아니다. 빈 응답·HTML 502 게이트웨이 페이지
    #   처럼 **생존 근거가 하나도 없는** 본문을 alive 로 세면, 감시기가 오히려 안심을
    #   파는 최악의 경우가 된다(폐기 사고를 못 잡는 건 아니지만, 인프라 장애를 정상으로
    #   보고). 그래서 alive 는 data.go.kr 응답 구조가 실제로 보일 때만 인정한다.
    if "resultCode" in body or "<response" in body or '"response"' in body:
        return STATUS_ALIVE

    return STATUS_DEGRADED


def classify_odcloud_response(body: str) -> str:
    """odcloud.kr 응답 본문 → alive / dead / degraded 분류.

    apis.data.go.kr 판정기와 **신호 체계가 완전히 다르다** — odcloud 는
    ``returnReasonCode`` 를 쓰지 않으므로 그쪽 판정기를 태우면 전부 degraded 로
    뭉개져 감시가 무력화된다(모듈 docstring §odcloud 표).

    - dead     : ``{"code": -3}`` 또는 "등록되지 않은 서비스" — 서비스 경로 자체가 없음
    - degraded : 인증키 오류(-4)·바디 형식 오류(411)·빈 응답·HTML 등 그 외 전부
    - alive    : ``currentCount``/``data``/``status_code`` 등 **양성 증거**가 보일 때만

    dead 를 ``-3`` 하나로 좁힌 이유: ``-4``(등록되지 않은 인증키)는 서비스가 살아
    있으니까 나오는 응답이라 폐기로 세면 키 만료 때마다 오탐이 터진다.
    """
    if not body:
        return STATUS_DEGRADED

    if ODCLOUD_DEAD_TOKEN in body or _extract_odcloud_code(body) == ODCLOUD_DEAD_CODE:
        return STATUS_DEAD

    # ⚠ 여기서도 "죽음 신호가 없다" ≠ "살아있다" (datagokr 판정기와 같은 원칙).
    #   양성 증거가 있을 때만 alive — 빈 응답·HTML 502 는 degraded 로 남겨 로그만 남긴다.
    if any(f'"{k}"' in body for k in ODCLOUD_ALIVE_KEYS):
        return STATUS_ALIVE

    return STATUS_DEGRADED


def _extract_odcloud_code(body: str) -> int | None:
    """odcloud 에러 본문의 ``"code": -3`` 값 추출 (음수 부호 포함).

    ``_extract_reason_code`` 와 달리 부호를 살려야 한다 — ``-3``(폐기)과
    ``-4``(인증키)를 절댓값으로 뭉개면 키 만료가 폐기로 오탐된다.
    정상 응답에도 ``code`` 키가 없으므로 못 찾으면 None.
    """
    idx = body.find('"code"')
    if idx < 0:
        return None
    tail = body[idx + len('"code"') : idx + len('"code"') + 40]
    sign, digits, seen_colon = 1, "", False
    for ch in tail:
        if ch == ":" and not seen_colon:
            seen_colon = True
        elif ch == "-" and seen_colon and not digits:
            sign = -1
        elif ch.isdigit():
            digits += ch
        elif digits:
            break
    return sign * int(digits) if digits else None


def classify_by_flavor(body: str, flavor: str) -> str:
    """레지스트리 항목의 flavor 에 맞는 판정기로 라우팅."""
    if flavor == FLAVOR_ODCLOUD:
        return classify_odcloud_response(body)
    return classify_response(body)


def _probe_one(entry: dict, service_key: str) -> tuple[str, str]:
    """엔드포인트 1건 프로브 → (status, 진단용 요약 문자열).

    파라미터는 serviceKey + 최소 페이지 지정뿐 — 유효 파라미터 없이도 생사가 갈린다
    (모듈 docstring §감지 원리). 네트워크 예외는 degraded (폐기 아님).

    ``method``/``json`` 이 지정된 항목(국세청 status 등)은 실제 코드와 **같은 방식**
    으로 부른다 — POST 전용 엔드포인트를 GET 으로 찌르면 405 만 돌아와 생사를 못 가린다.
    """
    url = entry["url"]
    flavor = entry.get("flavor", FLAVOR_DATAGOKR)
    method = entry.get("method", "GET")
    # odcloud 는 page/perPage, apis.data.go.kr 은 pageNo/numOfRows 를 쓴다.
    # 어느 쪽이든 "생사 판별" 에는 무관하나(유효 파라미터 없이도 갈린다), 정상 응답을
    # 최소 크기로 받아 쿼터·대역폭을 아끼려고 각 계열의 이름을 맞춰 준다.
    if flavor == FLAVOR_ODCLOUD:
        params = {"serviceKey": service_key, "page": "1", "perPage": "1", "returnType": "JSON"}
    else:
        params = {"serviceKey": service_key, "numOfRows": "1", "pageNo": "1"}

    try:
        if method == "POST":
            resp = requests.post(
                url,
                params={"serviceKey": service_key},
                json=entry.get("json") or {},
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
        else:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except Exception as e:  # 타임아웃·DNS·연결 끊김 — 서비스 폐기의 증거가 아니다
        return STATUS_DEGRADED, f"요청 예외 {type(e).__name__}"

    body = resp.text or ""
    status = classify_by_flavor(body, flavor)
    return status, f"HTTP {resp.status_code} / {body[:120].strip()}"


def _build_alert_message(dead: list[dict]) -> str:
    """폐기 감지 텔레그램 본문 — 평문(parse_mode 없음, HTML 이스케이프 불필요).

    ⚠ 문구는 전부 쉬운 우리말이어야 한다(infra.md §텔레그램 알림 문구). 세션 409 에
    `엔드포인트`·`NO_OPENAPI_SERVICE_ERROR`·`버전 개편`·URL 나열을 걷어냈다 —
    사장님이 읽고 **무엇이 멈췄고 무엇을 하면 되는지**만 남긴다. 기술 세부(어느 URL 이
    죽었는지)는 서버 로그와 관리자 화면에 그대로 남아 내가 언제든 본다.
    """
    names = ", ".join(item["name"] for item in dead)
    return "\n".join([
        "[서버 알림] 🔴 정부 자료 창구가 닫혔어요",
        "",
        f"▸ 정부가 자료 주는 곳 {len(dead)}군데가 응답을 멈췄어요: {names}",
        "  정부 쪽에서 주소를 바꿨을 때 이렇게 됩니다.",
        "→ 손님 화면은 그대로 보입니다(예전에 받아둔 자료). 그 자료만 새로 안 들어와요.",
        "   아침에 Claude 에게 알려주시면 새 주소로 바꿉니다.",
    ])


def _alert_api_version(message: str) -> None:
    """운영 텔레그램 알림 — 실패해도 감시를 죽이지 않는다(best-effort, lazy import).

    service_official_price._alert_official_price 패턴 답습. TELEGRAM_ENABLED 토글을
    공유하며, 테스트에서는 conftest 가 그 토글을 false 로 강제해 실발송이 0 이다
    (세션 325 사고 답습).
    """
    try:
        from services.telegram import send_telegram

        send_telegram(message)
    except Exception:
        logger.warning("[api_version] 텔레그램 알림 발송 실패", exc_info=True)


def probe_api_versions(scheduler_job_id: str = "api_version_probe") -> dict:
    """레지스트리 전체를 프로브하고, 폐기(dead)가 있으면 텔레그램 1건으로 묶어 알린다.

    Returns:
        {"alive": [...], "dead": [...], "degraded": [...]} — 각 원소는
        {"name", "url", "detail"} dict. 스케줄러는 반환값을 쓰지 않지만
        수동 실행·테스트에서 결과를 직접 볼 수 있게 돌려준다.

    ⚠ dead 발견은 **잡 실패가 아니다** — 감시기는 제 할 일을 다 한 것이므로
    CrawlJob 은 completed 로 남기고, 알림으로 사람에게 넘긴다.
    """
    service_key = os.getenv("PUBLIC_DATA_API_KEY", "")
    if not service_key:
        logger.warning("[api_version] PUBLIC_DATA_API_KEY 미설정 — 프로브 건너뜀")
        return {"alive": [], "dead": [], "degraded": []}

    result: dict[str, list[dict]] = {STATUS_ALIVE: [], STATUS_DEAD: [], STATUS_DEGRADED: []}

    db = SessionLocal()
    job = None
    try:
        job = _record_job(db, "api_version_probe", scheduler_job_id)

        for i, entry in enumerate(PROBE_REGISTRY):
            if i > 0:
                time.sleep(PROBE_INTERVAL_SECONDS)
            status, detail = _probe_one(entry, service_key)
            result[status].append({"name": entry["name"], "url": entry["url"], "detail": detail})

            if status == STATUS_DEAD:
                logger.error(
                    "[api_version] 폐기 감지 — %s (%s) :: %s", entry["name"], entry["url"], detail
                )
            elif status == STATUS_DEGRADED:
                # 간헐 오류 — 알림 없이 기록만 (오탐 방지, 모듈 docstring §감지 원리)
                logger.warning(
                    "[api_version] 비정상 응답(폐기 아님) — %s :: %s", entry["name"], detail
                )
            else:
                logger.info("[api_version] 정상 — %s", entry["name"])

        dead = result[STATUS_DEAD]
        if dead:
            _alert_api_version(_build_alert_message(dead))

        logger.info(
            "[api_version] 프로브 완료 — 정상 %d / 폐기 %d / 비정상 %d",
            len(result[STATUS_ALIVE]),
            len(dead),
            len(result[STATUS_DEGRADED]),
        )
        _complete_job(db, job, collected=len(result[STATUS_ALIVE]), failed=len(dead))
        return result

    except Exception as e:
        logger.error("[api_version] 프로브 실패: %s", e, exc_info=True)
        if job is not None:
            # 기록 성공 시 재전파하면 [내부즉시](job_error_listener)+[내부모니터](monitor)
            # 이중 알림 — 삼켜서 monitor 단독 알림으로 통일 (s391).
            # 다른 수집기 전부가 이미 이 패턴(예외 삼킴 + CrawlJob failed 기록)이다.
            # 트레이드오프: 즉시 알림 대신 monitor 주기(최대 10분) 지연을 감수 —
            # 주 1회 도는 감시 잡이라 10분 지연은 수용 가능하다.
            _fail_job(db, job, str(e))
            return result
        # CrawlJob 기록 전 사망 — monitor 가 볼 행 자체가 없으므로
        # 스케줄러 리스너(job_error_listener)가 유일한 그물이다. 재전파 유지.
        raise
    finally:
        db.close()
