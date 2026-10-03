"""data.go.kr API 버전 격변 감시 단위 테스트 (2026-08-19 폐기 사고 재발방지).

검증 축 3개:
  ① 전부 alive → 텔레그램 알림 0
  ② 1건 dead(returnReasonCode 12) → 알림 1건 + 본문에 그 API 이름 포함
  ③ degraded(코드 30 서비스키 미등록 등) → 알림 0, 로그만 (간헐 오류 오탐 방지)

⚠ 실호출·실발송 봉쇄 (세션 325 텔레그램 실알림 사고 + 세션 375 V-WORLD flaky 답습):
  - ``crawler.api_version_monitor.requests.get`` 을 **직접** 목킹한다. 키 부재에 기대지
    않는다 — 로컬 .env 의 PUBLIC_DATA_API_KEY 가 crawler.scheduler 등의 load_dotenv() 로
    세션 전역에 로드되면, 단독 실행은 무해한데 전체 회귀에서만 실호출이 생기는 flaky 가
    된다(세션 375 실측 패턴). 그래서 키도 monkeypatch 로 고정 주입한다.
  - 텔레그램은 ``_alert_api_version`` 이 lazy import 하는 ``services.telegram.send_telegram``
    을 목킹해 호출 횟수를 센다. conftest 가 TELEGRAM_ENABLED=false 로 전역 봉쇄하고 있어
    이중 안전망이다.

실행: python -m pytest tests/test_api_version_monitor.py -q
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from crawler.api_version_monitor import (
    FLAVOR_DATAGOKR,
    FLAVOR_ODCLOUD,
    PROBE_REGISTRY,
    STATUS_ALIVE,
    STATUS_DEAD,
    STATUS_DEGRADED,
    _extract_odcloud_code,
    classify_by_flavor,
    classify_odcloud_response,
    classify_response,
    probe_api_versions,
)
from db.models import CrawlJob

# ── 응답 픽스처 (data.go.kr 실제 응답 형태 답습) ────────────────────────────

# 살아있음: 필수 파라미터 부족(코드 11) — 서비스가 요청을 검증했다는 증거
BODY_ALIVE_NO_PARAMS = (
    '{"response":{"header":{"resultCode":"11",'
    '"resultMsg":"NO_MANDATORY_REQUEST_PARAMETERS_ERROR"}}}'
)
# 살아있음: 정상 응답
BODY_ALIVE_OK = (
    '{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL SERVICE."},'
    '"body":{"totalCount":1,"items":{"item":[{"aptNm":"테스트단지"}]}}}}'
)
# 폐기: 2026-08-19 사고 당시 실제 응답 형태 (HTTP 400 + returnReasonCode 12)
BODY_DEAD = (
    '{"cmmMsgHeader":{"errMsg":"SERVICE ERROR",'
    '"returnAuthMsg":"NO_OPENAPI_SERVICE_ERROR","returnReasonCode":"12"}}'
)
# 폐기(XML 변형) — 같은 상황을 XML 로 주는 엔드포인트 대응
BODY_DEAD_XML = (
    "<OpenAPI_ServiceResponse><cmmMsgHeader>"
    "<returnAuthMsg>NO_OPENAPI_SERVICE_ERROR</returnAuthMsg>"
    "<returnReasonCode>12</returnReasonCode>"
    "</cmmMsgHeader></OpenAPI_ServiceResponse>"
)
# 비정상이나 폐기 아님: 서비스키 미등록(코드 30) — 간헐 발생, 알림 금지
BODY_DEGRADED_KEY = (
    '{"cmmMsgHeader":{"returnAuthMsg":"SERVICE_KEY_IS_NOT_REGISTERED_ERROR",'
    '"returnReasonCode":"30"}}'
)
# 비정상이나 폐기 아님: 타임아웃(코드 05)
BODY_DEGRADED_TIMEOUT = (
    '{"cmmMsgHeader":{"returnAuthMsg":"SERVICETIMEOUT_ERROR","returnReasonCode":"05"}}'
)

OD_ALIVE_LIST = '{"currentCount":1,"data":[{"HOUSE_NM":"테스트오피스텔"}],"totalCount":123}'
OD_ALIVE_NTS = (
    '{"request_cnt":1,"status_code":"OK","data":[{"b_no":"0000000000",'
    '"b_stt":"","b_stt_cd":""}]}'
)
OD_DEAD = '{"code":-3,"msg":"등록되지 않은 서비스 입니다."}\n'
OD_DEGRADED_KEY = '{"code":-4,"msg":"등록되지 않은 인증키 입니다."}\n'
OD_MALFORMED_BODY = '{"status_code":"REQUEST_DATA_MALFORMED"}\n'


def _resp(body: str, status_code: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.text = body
    return m


@pytest.fixture(autouse=True)
def _no_sleep_no_realkey(monkeypatch):
    """프로브 간 sleep 제거(테스트 속도) + API 키 고정 주입(실키 의존 제거).

    ⚠ ``requests.post`` 도 여기서 막는다. 레지스트리에 POST 전용 항목(국세청
    status)이 생긴 뒤로는, ``requests.get`` 만 목킹하는 테스트가 **실제
    odcloud 로 POST 를 날린다**(실제로 이 픽스처 추가 전 라이브 401 응답이
    로그에 찍혀 발견). 개별 테스트의 목킹 누락에 기대지 않고 픽스처에서
    기본 차단한 뒤, 필요한 테스트만 자기 목으로 덮어쓴다.
    """
    monkeypatch.setattr("crawler.api_version_monitor.time.sleep", lambda *_: None)
    monkeypatch.setenv("PUBLIC_DATA_API_KEY", "test-service-key")

    def _blocked(*args, **kwargs):  # pragma: no cover - 방어선
        raise AssertionError("테스트에서 실제 HTTP 호출이 나갔다 (목킹 누락)")

    monkeypatch.setattr("crawler.api_version_monitor.requests.get", _blocked)
    monkeypatch.setattr("crawler.api_version_monitor.requests.post", _blocked)


def _patch_http(get_body=None, post_body=None, get_status=200, post_status=200):
    """계열별 응답을 한 번에 깔아주는 헬퍼.

    레지스트리에 apis.data.go.kr(GET)·odcloud(GET/POST) 두 계열이 섞여 있어,
    "모든 엔드포인트에 같은 본문 하나" 를 주면 계열이 안 맞는 응답이 섞인다.
    그래서 계열별로 알맞은 본문을 지정할 수 있게 한다.
    """
    return (
        patch(
            "crawler.api_version_monitor.requests.get",
            return_value=_resp(get_body, status_code=get_status),
        ),
        patch(
            "crawler.api_version_monitor.requests.post",
            return_value=_resp(post_body, status_code=post_status),
        ),
    )


# ── classify_response 단위 (분류 규칙 자체) ─────────────────────────────────


@pytest.mark.parametrize(
    "body,expected",
    [
        (BODY_ALIVE_NO_PARAMS, STATUS_ALIVE),
        (BODY_ALIVE_OK, STATUS_ALIVE),
        (BODY_DEAD, STATUS_DEAD),
        (BODY_DEAD_XML, STATUS_DEAD),
        (BODY_DEGRADED_KEY, STATUS_DEGRADED),
        (BODY_DEGRADED_TIMEOUT, STATUS_DEGRADED),
        # ⚠ "죽음 신호가 없다" ≠ "살아있다" — 생존 근거 0 인 본문은 alive 가 아니다.
        ("", STATUS_DEGRADED),
        ("<html><body>502 Bad Gateway</body></html>", STATUS_DEGRADED),
        # 트래픽 초과(22)도 폐기 아님
        ('{"cmmMsgHeader":{"returnReasonCode":"22"}}', STATUS_DEGRADED),
        # 정상 코드 변형 — RTMS 는 "000", K-apt 는 "00" 을 준다(라이브 실측)
        ("<response><header><resultCode>000</resultCode></header></response>", STATUS_ALIVE),
        ('{"response":{"header":{"resultCode":"00"}}}', STATUS_ALIVE),
    ],
)
def test_classify_response(body, expected):
    """응답 본문 → alive/dead/degraded 분류가 실제 data.go.kr 응답 형태에 맞는가."""
    assert classify_response(body) == expected


def test_empty_or_gateway_body_is_not_alive():
    """생존 근거가 없는 본문을 alive 로 세면 감시기가 '안심을 파는' 최악이 된다.

    빈 응답·HTML 502 는 폐기의 증거도 아니지만 생존의 증거도 아니다 → degraded.
    (알림은 안 나가되 로그로 남아 사람이 볼 수 있다)
    """
    for body in ("", "   ", "<html><body>502 Bad Gateway</body></html>"):
        assert classify_response(body) == STATUS_DEGRADED, f"alive 로 오분류: {body!r}"


# ── ① 전부 alive → 알림 0 ──────────────────────────────────────────────────


def test_all_alive_sends_no_alert(db):
    """레지스트리 전부 살아있으면 텔레그램 알림이 나가지 않는다.

    계열이 둘이라 GET/POST 각각에 그 계열의 정상 응답을 깐다 — odcloud 항목에
    datagokr 본문을 주면 판정기가 생존 근거를 못 찾아 degraded 로 샌다.
    """
    _, post_patch = _patch_http(post_body=OD_ALIVE_NTS)

    def _by_flavor(url, **kwargs):
        entry = next(e for e in PROBE_REGISTRY if e["url"] == url)
        body = OD_ALIVE_LIST if entry.get("flavor") == FLAVOR_ODCLOUD else BODY_ALIVE_NO_PARAMS
        return _resp(body)

    with (
        patch("crawler.api_version_monitor.requests.get", side_effect=_by_flavor) as mock_get,
        post_patch as mock_post,
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()

    assert len(result[STATUS_ALIVE]) == len(PROBE_REGISTRY)
    assert result[STATUS_DEAD] == []
    # GET·POST 를 합쳐 레지스트리 전체가 정확히 한 번씩 프로브된다
    assert mock_get.call_count + mock_post.call_count == len(PROBE_REGISTRY)
    mock_send.assert_not_called()

    # 감시 잡은 정상 완료로 기록된다
    job = db.query(CrawlJob).filter(CrawlJob.job_type == "api_version_probe").one()
    assert job.status == "completed"


# ── ② 1건 dead → 알림 1건 + 본문에 API 이름 ────────────────────────────────


def test_one_dead_sends_single_alert_with_api_name(db):
    """폐기 1건이면 알림 **1건으로 묶어** 발송하고, 본문에 죽은 API 이름·URL 이 담긴다."""
    dead_entry = PROBE_REGISTRY[0]

    def _fake_get(url, **kwargs):
        if url == dead_entry["url"]:
            return _resp(BODY_DEAD, status_code=400)
        entry = next(e for e in PROBE_REGISTRY if e["url"] == url)
        if entry.get("flavor") == FLAVOR_ODCLOUD:
            return _resp(OD_ALIVE_LIST)
        return _resp(BODY_ALIVE_NO_PARAMS)

    _, post_patch = _patch_http(post_body=OD_ALIVE_NTS)
    with (
        patch("crawler.api_version_monitor.requests.get", side_effect=_fake_get),
        post_patch,
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()

    assert len(result[STATUS_DEAD]) == 1
    assert result[STATUS_DEAD][0]["name"] == dead_entry["name"]
    assert len(result[STATUS_ALIVE]) == len(PROBE_REGISTRY) - 1

    # 알림은 여러 건이 아니라 묶어서 1건
    assert mock_send.call_count == 1
    message = mock_send.call_args.args[0]
    # 단언 의도("어느 API 가 죽었는지 알림에 드러나는가")는 그대로 — 이름은 유지.
    assert dead_entry["name"] in message
    # ⚠ URL 은 세션 409 에 알림에서 뺐다 — 사장님께 의미 없는 개발자용 단서라
    #   logger.error 로 옮겼다(추적 근거는 서버 로그에 그대로). 되돌리지 말 것.
    assert dead_entry["url"] not in message, f"URL 이 알림에 다시 들어왔다: {message}"
    assert "엔드포인트" not in message and "NO_OPENAPI" not in message, message
    # 사람이 다음에 할 행동이 안내되는가 — 세션 409 에 "data.go.kr 공지를 확인하고
    # 신버전 엔드포인트로 교체하세요"(개발자가 할 일)를 사장님이 할 수 있는 안내로 바꿨다.
    assert "Claude" in message, f"무엇을 하면 되는지가 없다: {message}"

    # dead 발견은 잡 실패가 아니다 — 감시기는 제 할 일을 다 했다
    job = db.query(CrawlJob).filter(CrawlJob.job_type == "api_version_probe").one()
    assert job.status == "completed"


def _all_dead_patches():
    """레지스트리 전체를 '폐기' 로 만드는 목 — 계열별로 알맞은 폐기 본문을 준다."""

    def _fake_get(url, **kwargs):
        entry = next(e for e in PROBE_REGISTRY if e["url"] == url)
        if entry.get("flavor") == FLAVOR_ODCLOUD:
            return _resp(OD_DEAD, status_code=404)
        return _resp(BODY_DEAD, status_code=400)

    return (
        patch("crawler.api_version_monitor.requests.get", side_effect=_fake_get),
        patch(
            "crawler.api_version_monitor.requests.post",
            return_value=_resp(OD_DEAD, status_code=404),
        ),
    )


def test_multiple_dead_are_batched_into_one_alert():
    """폐기 여러 건이어도 알림은 1건(2026-08-19 처럼 전량 폐기 시 알림 폭탄 방지)."""
    get_patch, post_patch = _all_dead_patches()
    with (
        get_patch,
        post_patch,
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()

    assert len(result[STATUS_DEAD]) == len(PROBE_REGISTRY)
    assert mock_send.call_count == 1
    message = mock_send.call_args.args[0]
    for entry in PROBE_REGISTRY:
        assert entry["name"] in message


# ── ③ degraded → 알림 0 (간헐 오류 오탐 방지) ──────────────────────────────


def test_degraded_sends_no_alert_and_logs_only(db, caplog):
    """서비스키 미등록(코드 30)은 폐기가 아니다 — 알림 0, 경고 로그만."""
    with (
        patch(
            "crawler.api_version_monitor.requests.get",
            return_value=_resp(BODY_DEGRADED_KEY, status_code=401),
        ),
        patch("services.telegram.send_telegram") as mock_send,
        caplog.at_level("WARNING", logger="crawler.api_version_monitor"),
    ):
        result = probe_api_versions()

    assert len(result[STATUS_DEGRADED]) == len(PROBE_REGISTRY)
    assert result[STATUS_DEAD] == []
    mock_send.assert_not_called()
    assert "폐기 아님" in caplog.text

    job = db.query(CrawlJob).filter(CrawlJob.job_type == "api_version_probe").one()
    assert job.status == "completed"


def test_network_exception_is_degraded_not_dead():
    """타임아웃·연결 끊김은 폐기의 증거가 아니다 — degraded 로만 분류, 알림 0."""
    with (
        patch(
            "crawler.api_version_monitor.requests.get",
            side_effect=TimeoutError("connect timeout"),
        ),
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()

    assert len(result[STATUS_DEGRADED]) == len(PROBE_REGISTRY)
    assert result[STATUS_DEAD] == []
    mock_send.assert_not_called()


# ── 부수 가드 ──────────────────────────────────────────────────────────────


def test_no_api_key_skips_probe_entirely(monkeypatch):
    """PUBLIC_DATA_API_KEY 미설정이면 아무것도 호출하지 않고 조용히 건너뛴다."""
    monkeypatch.setenv("PUBLIC_DATA_API_KEY", "")

    with (
        patch("crawler.api_version_monitor.requests.get") as mock_get,
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()

    mock_get.assert_not_called()
    mock_send.assert_not_called()
    assert result == {STATUS_ALIVE: [], STATUS_DEAD: [], STATUS_DEGRADED: []}


def test_telegram_failure_does_not_break_probe(db):
    """텔레그램 발송이 터져도 감시 자체는 완료된다 (best-effort, 기존 관례)."""
    get_patch, post_patch = _all_dead_patches()
    with (
        get_patch,
        post_patch,
        patch("services.telegram.send_telegram", side_effect=RuntimeError("bot down")),
    ):
        result = probe_api_versions()

    assert len(result[STATUS_DEAD]) == len(PROBE_REGISTRY)
    job = db.query(CrawlJob).filter(CrawlJob.job_type == "api_version_probe").one()
    assert job.status == "completed"


def test_registry_covers_known_datagokr_endpoints():
    """레지스트리가 실사용 엔드포인트를 빠짐없이 담고 있는가 (새 API 추가 시 갱신 의무).

    2026-08-19 사고의 본질 = "코드가 쓰는데 아무도 안 보고 있던 엔드포인트". 레지스트리에서
    빠지면 그 사각지대가 그대로 재현되므로, 알려진 8개를 명시적으로 단언해 못 박는다.
    """
    urls = {entry["url"] for entry in PROBE_REGISTRY}
    expected = {
        "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
        "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire",
        "https://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getNearbyMsrstnList",
        "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty",
        "https://apis.data.go.kr/1613000/AptListService4/getSidoAptList4",
        "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5",
        "https://apis.data.go.kr/1613000/AptIndvdlzManageCostServiceV3/getHsmpHeatCostInfoV3",
        "https://apis.data.go.kr/1613000/AptCmnuseManageCostServiceV3/getHsmpLaborCostInfoV3",
    }
    assert expected <= urls, f"레지스트리 누락: {sorted(expected - urls)}"

    # 이름·URL 이 비어 있으면 알림 본문이 무의미해진다
    for entry in PROBE_REGISTRY:
        assert entry["name"].strip()
        assert entry["url"].startswith("https://")


def test_registry_urls_match_actual_collector_modules():
    """레지스트리 URL 이 실제 수집기 모듈 상수와 일치하는가 (drift 가드).

    수집기가 엔드포인트를 바꿨는데 레지스트리를 안 고치면, 감시는 옛 URL 만 찔러
    "정상"이라 보고하고 실제 수집기는 죽는다 — 감시가 오히려 안심을 파는 최악의 경우.
    """
    from crawler.air_quality_api import NEARBY_STATION_URL, REALTIME_AIR_URL
    from crawler.emergency_api import EMERGENCY_BEDS_URL, EMERGENCY_LIST_URL
    from crawler.public_data_api import BASE_URL

    urls = {entry["url"] for entry in PROBE_REGISTRY}
    for actual in (
        BASE_URL, EMERGENCY_LIST_URL, EMERGENCY_BEDS_URL, NEARBY_STATION_URL, REALTIME_AIR_URL,
    ):
        assert actual in urls, (
            f"수집기 모듈이 쓰는 {actual} 이 PROBE_REGISTRY 에 없다 — "
            "crawler/api_version_monitor.py PROBE_REGISTRY 에 추가할 것"
        )

    # K-apt 4종 — 2026-08-19 인증 개편으로 **실제로 폐기당한 당사자**라
    # 이 감시에서 빠지면 재발 방지 장치가 정작 재발 지점을 못 본다.
    # kapt_api 는 서비스 base URL 만 상수로 들고 오퍼레이션명을 호출부에서
    # 붙이므로(f"{_LIST_URL}/getTotalAptList4"), 레지스트리의 전체 URL 과는
    # prefix 로 대조한다.
    from crawler.kapt_api import _BASIS_URL, _CMNUSE_URL, _INDVDLZ_URL, _LIST_URL

    for base in (_LIST_URL, _BASIS_URL, _CMNUSE_URL, _INDVDLZ_URL):
        assert any(url.startswith(base + "/") for url in urls), (
            f"K-apt 수집기가 쓰는 {base} 로 시작하는 프로브가 PROBE_REGISTRY 에 없다 — "
            "crawler/api_version_monitor.py PROBE_REGISTRY 에 추가할 것"
        )


# ── odcloud 계열 (응답 포맷이 apis.data.go.kr 과 다름) ─────────────────────
#
# 아래 픽스처는 **2026-08-29 라이브 프로브 실측 원문**이다(키 값 제외). 추측이 아니라
# 실제 응답이라야 판정 규칙이 현실과 어긋나지 않는다.
#   정상(GET)   HTTP 200 {"currentCount":1,"data":[...]}
#   정상(POST)  HTTP 200 {"request_cnt":1,"status_code":"OK","data":[...]}
#   폐기        HTTP 404 {"code":-3,"msg":"등록되지 않은 서비스 입니다."}
#   인증키 오류 HTTP 401 {"code":-4,"msg":"등록되지 않은 인증키 입니다."}
#   바디 오류   HTTP 411 {"status_code":"REQUEST_DATA_MALFORMED"}

@pytest.mark.parametrize(
    "body,expected",
    [
        (OD_ALIVE_LIST, STATUS_ALIVE),
        (OD_ALIVE_NTS, STATUS_ALIVE),
        (OD_DEAD, STATUS_DEAD),
        # ⚠ 인증키 오류(-4)를 폐기로 세면 키 만료 때마다 가짜 경보가 울린다.
        (OD_DEGRADED_KEY, STATUS_DEGRADED),
        # 바디 형식 오류 — 서비스가 요청을 파싱했다는 증거라 폐기 아님
        (OD_MALFORMED_BODY, STATUS_ALIVE),
        # 생존 근거 0 → alive 아님 (datagokr 판정기와 같은 원칙)
        ("", STATUS_DEGRADED),
        ("<html><body>502 Bad Gateway</body></html>", STATUS_DEGRADED),
    ],
)
def test_classify_odcloud_response(body, expected):
    """odcloud 응답 → alive/dead/degraded 가 라이브 실측 형태에 맞는가."""
    assert classify_odcloud_response(body) == expected


def test_odcloud_dead_and_key_error_are_distinguished():
    """폐기(-3)와 인증키 오류(-4)를 부호·숫자까지 정확히 갈라야 한다.

    둘 다 `{"code": -N}` 한 글자 차이다. 절댓값으로 뭉개거나 '-' 를 흘리면
    키 만료가 폐기로 오탐돼, 진짜 폐기 경보까지 같이 무시하게 된다.
    """
    assert classify_odcloud_response(OD_DEAD) == STATUS_DEAD
    assert classify_odcloud_response(OD_DEGRADED_KEY) == STATUS_DEGRADED
    assert _extract_odcloud_code(OD_DEAD) == -3
    assert _extract_odcloud_code(OD_DEGRADED_KEY) == -4
    # 정상 응답엔 code 키 자체가 없다
    assert _extract_odcloud_code(OD_ALIVE_LIST) is None


def test_datagokr_classifier_would_misjudge_odcloud_bodies():
    """왜 전용 판정기가 필요한가 — 기존 판정기로는 odcloud 폐기를 못 잡는다.

    이 단언이 깨진다면(= 기존 판정기가 알아서 dead 를 준다면) flavor 분기는
    불필요한 복잡도이므로 되돌려야 한다. 즉 이 테스트는 '분기의 존재 이유' 가드다.
    """
    assert classify_response(OD_DEAD) != STATUS_DEAD
    assert classify_by_flavor(OD_DEAD, FLAVOR_ODCLOUD) == STATUS_DEAD
    # datagokr 계열은 flavor 를 생략해도 기존 판정기로 라우팅된다(기존 8종 무변경)
    assert classify_by_flavor(BODY_DEAD, FLAVOR_DATAGOKR) == STATUS_DEAD


def test_odcloud_dead_triggers_alert_with_api_name(db):
    """odcloud 엔드포인트가 폐기되면 다른 계열과 똑같이 알림 1건이 나간다."""
    dead_entry = next(e for e in PROBE_REGISTRY if e.get("flavor") == FLAVOR_ODCLOUD)

    def _fake_get(url, **kwargs):
        return _resp(OD_DEAD, status_code=404) if url == dead_entry["url"] else _resp(
            BODY_ALIVE_NO_PARAMS
        )

    def _fake_post(url, **kwargs):
        return _resp(OD_DEAD, status_code=404) if url == dead_entry["url"] else _resp(
            OD_ALIVE_NTS
        )

    with (
        patch("crawler.api_version_monitor.requests.get", side_effect=_fake_get),
        patch("crawler.api_version_monitor.requests.post", side_effect=_fake_post),
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()

    assert [d["name"] for d in result[STATUS_DEAD]] == [dead_entry["name"]]
    assert mock_send.call_count == 1
    assert dead_entry["name"] in mock_send.call_args.args[0]

    job = db.query(CrawlJob).filter(CrawlJob.job_type == "api_version_probe").one()
    assert job.status == "completed"


def test_post_only_endpoint_is_probed_with_post():
    """국세청 status 는 POST 전용 — GET 으로 찌르면 405 라 생사를 못 가린다.

    실제 코드와 같은 메서드로 부르는지 단언한다. GET 으로 새면 그 API 는
    영영 degraded 로만 보고돼 감시 사각지대가 된다(오탐이 아니라 '무탐').
    """
    post_entries = [e for e in PROBE_REGISTRY if e.get("method") == "POST"]
    assert post_entries, "POST 전용 항목이 사라짐 — business_api status/validate 프로브 확인"

    posted, got = [], []
    with (
        patch(
            "crawler.api_version_monitor.requests.get",
            side_effect=lambda url, **kw: (got.append(url), _resp(BODY_ALIVE_NO_PARAMS))[1],
        ),
        patch(
            "crawler.api_version_monitor.requests.post",
            side_effect=lambda url, **kw: (posted.append((url, kw.get("json"))), _resp(OD_ALIVE_NTS))[1],
        ),
        patch("services.telegram.send_telegram"),
    ):
        result = probe_api_versions()

    for entry in post_entries:
        assert entry["url"] in [u for u, _ in posted], f"{entry['name']} 이 POST 로 안 나감"
        assert entry["url"] not in got, f"{entry['name']} 이 GET 으로도 나감"
    # 실제로 나간 바디가 레지스트리에 적힌 그대로인가 (status·validate 는 스키마가 다르다)
    expected_bodies = {e["url"]: e["json"] for e in post_entries}
    for url, payload in posted:
        assert payload == expected_bodies[url], f"{url} 바디가 레지스트리와 다름"
    # 부수효과 0 — 조회 전용이라 더미 사업자번호(0000000000)만 실려 나간다
    for url, payload in posted:
        assert "0000000000" in json.dumps(payload, ensure_ascii=False), (
            f"{url} 바디에 더미 사업자번호가 없다 — 실제 번호가 새어나갈 위험"
        )
    assert result[STATUS_DEAD] == []


def test_registry_odcloud_urls_match_actual_collector_modules():
    """odcloud 레지스트리 URL 이 실제 수집기 모듈 상수와 일치하는가 (drift 가드).

    apis.data.go.kr 쪽과 같은 이유 — 수집기가 엔드포인트를 바꿨는데 레지스트리를
    안 고치면 감시는 옛 URL 만 찔러 "정상" 이라 보고하고 실제 수집기는 죽는다.
    """
    from crawler.applyhome_officetel_api import BASE_URL as APPLYHOME_BASE
    from crawler.business_api import STATUS_URL, VALIDATE_URL
    from crawler.crime_stats_api import CRIME_STATS_URL

    urls = {entry["url"] for entry in PROBE_REGISTRY}

    # 청약홈은 서비스 base 아래 4개 오퍼레이션이라 prefix 로 대조 (K-apt 선례 답습)
    assert any(url.startswith(APPLYHOME_BASE + "/") for url in urls), (
        f"청약홈 수집기가 쓰는 {APPLYHOME_BASE} 로 시작하는 프로브가 없다 — "
        "crawler/api_version_monitor.py PROBE_REGISTRY 에 추가할 것"
    )
    # 국세청 status·validate·범죄통계는 전체 URL 이 곧 엔드포인트라 완전일치로 대조.
    # ⚠ 국세청 두 오퍼레이션은 서비스가 같아도 개별 폐기가 가능해 각각 등록한다
    #   (청약홈처럼 대표 1개 prefix 대조로 갈음하지 않는다).
    for actual in (STATUS_URL, VALIDATE_URL, CRIME_STATS_URL):
        assert actual in urls, (
            f"수집기 모듈이 쓰는 {actual} 이 PROBE_REGISTRY 에 없다 — "
            "crawler/api_version_monitor.py PROBE_REGISTRY 에 추가할 것"
        )

    # odcloud 항목은 flavor 지정이 의무 — 빠뜨리면 판정기가 어긋나 감시가 무력화된다
    for entry in PROBE_REGISTRY:
        if "odcloud.kr" in entry["url"]:
            assert entry.get("flavor") == FLAVOR_ODCLOUD, (
                f"{entry['name']} 에 flavor=odcloud 누락 — 모든 응답이 degraded 로 뭉개진다"
            )


# ── 세션 391: 이중 알림 제거 (§5-C) ────────────────────────────────────────
# CrawlJob 기록에 성공한 뒤 죽으면 monitor 가 그 failed 행을 보고 알린다.
# 여기서 예외를 재전파하면 스케줄러 리스너([내부즉시])까지 발화해 같은 사고가
# 두 번 통지된다 — 다른 수집기 전부가 쓰는 '삼킴 + failed 기록' 패턴으로 통일.


def test_probe_failure_after_job_recorded_is_swallowed(db):
    """잡 기록 후 예외 → 재전파 없음 + 부분 result 반환 + CrawlJob failed."""
    def _boom(*args, **kwargs):
        raise RuntimeError("프로브 도중 폭발")

    with (
        patch("crawler.api_version_monitor._probe_one", side_effect=_boom),
        patch("services.telegram.send_telegram") as mock_send,
    ):
        result = probe_api_versions()  # raise 하면 이 줄에서 테스트 실패

    # 반환 계약 유지 — 세 키가 모두 있는 dict (스케줄러·수동 실행이 쓰는 형태)
    assert set(result) == {STATUS_ALIVE, STATUS_DEAD, STATUS_DEGRADED}
    assert result[STATUS_DEAD] == []
    mock_send.assert_not_called()

    job = db.query(CrawlJob).filter(CrawlJob.job_type == "api_version_probe").one()
    assert job.status == "failed"
    assert "프로브 도중 폭발" in (job.error_message or "")


def test_probe_failure_before_job_recorded_still_raises():
    """잡 기록 **전** 예외 → 재전파 유지 (monitor 가 볼 행이 없어 리스너가 유일 그물)."""
    with (
        patch(
            "crawler.api_version_monitor._record_job",
            side_effect=RuntimeError("DB 커넥션 사망"),
        ),
        patch("services.telegram.send_telegram"),
        pytest.raises(RuntimeError, match="DB 커넥션 사망"),
    ):
        probe_api_versions()


def test_registry_covers_all_thirteen_endpoints():
    """감시 대상 총 13종 (apis.data.go.kr 9 + odcloud 4) — 누락 시 사각지대.

    세션 417: 응급실 실시간 가용병상 op 추가(병상 수를 이 op 에서만 받는다) 12 → 13.
    """
    urls = {entry["url"] for entry in PROBE_REGISTRY}
    assert len(PROBE_REGISTRY) == len(urls), "레지스트리에 중복 URL 이 있다"
    assert len(PROBE_REGISTRY) == 13, f"감시 대상이 13종이 아님: {len(PROBE_REGISTRY)}"
    assert sum(1 for e in PROBE_REGISTRY if e.get("flavor") == FLAVOR_ODCLOUD) == 4


def test_registry_common_cost_probe_uses_first_op():
    """공용관리비 프로브가 수집기의 **첫 op** 를 찌르는가 (단일 실패점 감시).

    수집기는 첫 op(`COMMON_COST_OPS[0]`)가 비면 그 서비스·월 전체를 미공개로 보고
    나머지 16콜을 건너뛰고(kapt_api._collect_ops), "전량 미공개" 회차의 카나리도
    그 op 하나로 API 생사를 판정한다. 그래서 첫 op 만 죽어도 관리비 수집이 통째로
    멈추는데, 감시가 다른 op(옛 getHsmpGuardCostInfoV3)를 보고 있으면 그 사이
    "정상" 이라고 보고한다 — 2026-08-19 사고가 만든 감시 원칙("코드가 의지하는
    지점을 본다")의 직접 적용이다.
    """
    from crawler.kapt_api import _CMNUSE_URL, COMMON_COST_OPS

    expected = f"{_CMNUSE_URL}/{COMMON_COST_OPS[0]}"
    urls = {entry["url"] for entry in PROBE_REGISTRY}
    assert expected in urls, (
        f"공용관리비 프로브가 첫 op 가 아니다 — {expected} 를 PROBE_REGISTRY 에 넣을 것 "
        f"(현재: {sorted(u for u in urls if u.startswith(_CMNUSE_URL))})"
    )


def test_registry_covers_nts_validate_operation():
    """국세청 진위확인(validate)이 status 와 **별개 오퍼레이션**으로 등록돼 있는가.

    두 오퍼레이션은 같은 서비스(nts-businessman/v1) 아래지만 data.go.kr 은
    오퍼레이션 단위로도 폐기·개편한다. status 만 감시하면 validate 만 죽었을 때
    공인중개사 **가입 검증**(routers/verify.py)이 조용히 막혀도 감시망이 못 잡는다.
    """
    from crawler.business_api import VALIDATE_URL

    entry = next((e for e in PROBE_REGISTRY if e["url"] == VALIDATE_URL), None)
    assert entry is not None, (
        f"국세청 진위확인 {VALIDATE_URL} 이 PROBE_REGISTRY 에 없다 — "
        "crawler/api_version_monitor.py PROBE_REGISTRY 에 추가할 것"
    )
    # POST 전용이라 GET 으로 찌르면 405 → 생사 판별 불가
    assert entry.get("method") == "POST", "validate 는 POST 전용 — method 지정 필수"
    # flavor 를 빠뜨리면 판정기가 어긋나 모든 응답이 degraded 로 뭉개진다
    assert entry.get("flavor") == FLAVOR_ODCLOUD, "validate 에 flavor=odcloud 누락"
    # 실제 코드(business_api.verify_business_registration)와 같은 바디 스키마 +
    # 조회 전용 더미 번호 (부수효과 0)
    businesses = entry["json"]["businesses"]
    assert businesses[0]["b_no"] == "0000000000"
