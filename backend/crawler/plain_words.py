"""텔레그램 알림을 '일반인이 읽을 수 있는 말'로 바꾸는 사전 (세션 407).

사장님 지시(2026-09-15): *"텔레그램 알림은 일반인이 봐도 무엇이 어떻게 잘못되었는지
손쉽게 알 수 있어야 해. 그 부분을 절대로 간과하면 안 돼. 어려운 말은 금지야."*

알림에 새던 어려운 말은 세 갈래였다 — 이 모듈이 셋을 전부 맡는다.

1. **영문 작업 이름** (`field_drift_monitor`, `article_detail_backfill`)
   → `job_words()` 로 "정보 안 채워지면 알림" 처럼 우리말만 내보낸다.
2. **개발자용 에러 원문** (`(psycopg2.errors.QueryCanceled) canceling statement ...`)
   → `explain_error()` 로 "데이터베이스가 너무 오래 걸려 스스로 멈췄어요" 한 줄로.
3. **사장님이 할 수 없는 행동 안내** ("크롤링 로그 확인 — 네이버 응답 점검")
   → `alert_format._action` 이 이 모듈의 문구를 쓴다.

⚠ **키는 `job_type`(DB 값)이지 스케줄러 잡 id 가 아니다.**
   이 프로젝트에는 이름 체계가 둘 있고 서로 다르다(infra.md §잡 이름 ≠ job_type):
     - 스케줄러 잡 id: `backfill_detail_dawn` / `crawl_articles` / `crawl_details`
     - DB job_type    : `article_detail_backfill` / `complex_articles` / `article_detail`
   알림이 받는 값은 `monitor.py` 가 넣는 `CrawlJob.job_type` 이라 **후자**다.
   `job_error_listener._JOB_LABEL_FALLBACK` 은 전자로 키가 잡혀 있어 여기 쓰면
   정작 문제가 된 잡들이 사전에서 미스가 나 영문이 그대로 샌다 — 세션 407 설계 시
   실제로 그 경로로 갈 뻔했다. 두 사전은 **일부러 별개로 둔다**.

⚠ FE `frontend/src/lib/crawl-job-labels.ts` 와 **같은 키 체계**다(양쪽 다 job_type).
   화면과 알림이 같은 작업을 다른 이름으로 부르면 사장님이 두 이름을 대조해야 하므로,
   키 누락은 `tests/test_plain_words.py` 가 FE 사전과 대조해 막는다.
"""

import logging
import re
from collections.abc import Callable

logger = logging.getLogger(__name__)

# ── 1. 작업 이름 — 영문 job_type → 사장님이 읽는 우리말 ──────────────────
#
# 값은 "무엇을 하는 작업인지"가 이름만 보고 드러나야 한다. FE 사전(crawl-job-labels.ts)의
# label 을 기준으로 삼되, 거기 남아 있는 어려운 말은 여기서 더 쉽게 고쳐 쓴다
# (예: "단지 상세 backfill APT" → "아파트 단지 정보 채우기" — 영문 backfill 제거).
# ⚠ 새 job_type 이 생기면 여기와 FE 사전 양쪽에 넣는다(테스트가 누락을 잡는다).
JOB_WORDS: dict[str, str] = {
    # 매물·단지 수집
    "complex_articles": "단지 매물 가져오기",
    "complex_list": "새 단지 찾기",
    "popular_crawl": "자주 보는 단지 미리 갱신",
    "article_detail": "매물 상세 내용 채우기",
    "article_detail_backfill": "빠진 정보 뒤늦게 채우기",
    "field_drift_monitor": "정보 안 채워지면 알림",
    "bulk_recrawl": "여러 단지 한꺼번에 다시 받기",
    # 시세·실거래
    "price_history": "단지 시세 기록 모으기",
    "price_backfill": "옛 시세 채워 넣기",
    "public_trade_data": "정부 실거래가 받기",
    "complex_metric": "단지 가치 점수 계산",
    "official_price": "정부 공시가격 받기",
    # 청약
    "officetel_presale": "오피스텔 청약 공고 받기",
    "rental_presale": "민간임대 청약 공고 받기",
    # 생활 환경
    "air_quality": "동네 공기질 받기",
    "emergency": "응급실 위치 받기",
    "childcare": "어린이집 정보 받기",
    "crime_stats": "동네 범죄 통계 받기",
    # 관리비(K-apt)
    "kapt_match": "관리비 단지 연결하기",
    "kapt_costs": "단지 관리비 받기",
    # 살림
    "billing_charge": "구독료 자동 결제",
    "vacuum_maintenance": "자료 보관함 정리",
    "api_version_probe": "정부 자료 창구 살아있나 확인",
    # 수동·테스트 실행 — FE 가드는 이 셋을 "이름표 불필요"로 면제하지만, 알림에는
    # 그대로 영문이 찍힌다(적대검증 MEDIUM-8). 알림 사전에는 우리말을 둔다.
    "manual": "사람이 직접 실행",
    "test": "시험 실행",
    # 단지 상세 보강 — 매물 유형별. FE label 의 "backfill" 영문을 우리말로 바꿨다.
    "complex_detail_APT": "아파트 단지 정보 채우기",
    "complex_detail_OPST": "오피스텔 단지 정보 채우기",
    "complex_detail_JGC": "재건축 단지 정보 채우기",
    "complex_detail_ABYG": "아파트 분양권 단지 정보 채우기",
    "complex_detail_OBYG": "오피스텔 분양권 단지 정보 채우기",
}


def job_words(job_type) -> str:
    """영문 job_type → 우리말 작업 이름. 사전에 없으면 원문 그대로.

    폴백이 원문(영문)인 이유: 알림 자체가 안 나가는 것보다 영문이라도 나가는 게 낫다.
    사전 누락은 테스트가 CI 에서 잡으므로, 이 폴백이 운영에서 보일 일은 없어야 한다.
    """
    if not job_type:
        return ""
    return JOB_WORDS.get(str(job_type), str(job_type))


# ── 2. 에러 — 개발자용 원문 → 사장님이 읽는 한 줄 ────────────────────────
#
# 아래 패턴은 **추측이 아니라 prod `crawl_jobs.error_message` 실측**이다
# (세션 407, 최근 14일 + monitor_alerts 저장분 22건 전수). 실제로 나온 적 없는
# 에러를 미리 번역해 두지 않는다 — 안 맞는 번역이 오히려 오해를 만든다.
#
# 부팅 스윕·모니터 스윕이 남기는 정리 문장 (아래 규칙 + explain_stored_error ⓪ 공용).
STALE_SWEPT_WORDS = "작업이 오래 멈춰 있어 자동으로 정리됐어요."

# 원문 뒤에 붙은 스윕 마커를 갈라내는 정규식 (`explain_stored_error` ⓪단계 전용).
# `.*?` 가 **처음 나온** 구분자에서 끊으므로 head 에는 `| stale running` 이 다시
# 들어갈 수 없다 — 되돌이(재귀) 깊이 1 의 근거. `\s*` 덕에 앞머리가 비어 구분자의
# 앞 공백이 깎인 형태(`| stale running …`)도 head 빈 문자열로 함께 잡힌다.
_STALE_TAIL = re.compile(r"^(?P<head>.*?)\s*\|\s*stale running.*$", re.I | re.S)

# (정규식, 사장님이 읽을 한 줄)  — 위에서부터 먼저 맞는 것을 쓴다.
#   값이 문자열이 아니라 **호출 가능 객체**면 `plain(원문)` 을 돌려준다(원문 보존 규칙용).
_ERROR_RULES: list[tuple[re.Pattern, str | Callable[[str], str]]] = [
    # ── 우리 국토부 실거래가 수집기 문구 — 원문 그대로 (세션 420 검사관 M2) ──
    # `service_public.py` 가 error_message·예외 문구로 만드는 문장은 처음부터 쉬운 우리말이고
    # "190/253개 시군구까지만" 같은 숫자가 핵심이다. 그런데 아래 한도 규칙(`한도.*초과`)이
    # 먼저 잡으면 숫자가 사라진 한 줄로 바뀌고, 한도가 아닌 문장은 규칙에 안 맞아 알림에서
    # "처음 보는 문제" 로 떨어졌다. ⚠ 반드시 **맨 앞**(한도 규칙보다 앞)이다.
    # 줄머리가 우리 문구로 시작하고 **영문 글자·`|` 가 하나도 없을 때만** 원문을 돌려준다 —
    # 영문(개발자 원문)이나 스윕 마커(`| stale running`)가 섞인 값은 이 규칙을 지나쳐
    # 아래 규칙·고정 문장이 받는다(원문 보존이 영문 누출 통로가 되지 않게).
    # 머리 두 가지 = "정부 실거래가 창구…"(중단·부분 실패·소급 단지/배치 문구 전부) ·
    # "N개 시군구는 못 받음…"(부분 실패인데 completed 로 끝난 회차).
    (
        re.compile(r"^(?:정부 실거래가 창구|\d+개 시군구는 못 받음)[^A-Za-z|]*$"),
        lambda text: text,
    ),
    # ── 우리 관리비 단지 연결하기(kapt_match) 문구 — 원문 그대로 (세션 426 검사관) ──
    # `service_kapt.match_kapt_complexes` 가 failed 로 끝날 때 남기는 문장
    # ("단지 기본정보 N건 받기 실패 — … · 연결 M건", "대상 단지 N개 전부 매칭 실패 (매칭 0건)")은
    # 처음부터 쉬운 우리말이고 숫자가 핵심인데, 어느 규칙에도 안 맞아 알림이 "처음 보는 문제" 로
    # 떨어졌다(검사관 실행 확인). 위 실거래가 규칙과 같은 꼴 — **영문 글자·`|` 가 섞이면 통과
    # 안 함**(개발자 원문·스윕 마커는 아래 규칙·고정 문장이 받는다). 부분 목록 문구는 "K-apt"
    # 라는 영문이 있어 여기 안 걸리는 게 맞다.
    # "관리비 받기가 끝나지 않아 …"(세션 427) = 관리비 받기 회차를 45분 기다려도 안 끝나 매칭을
    # 시작하지 못한 사유 — "끝난 뒤 다시 눌러 주세요" 안내가 알림에서 사라지면 안 된다.
    (
        re.compile(
            r"^(?:단지 기본정보 \d+건 받기 실패|대상 단지 \d+개 전부 매칭 실패"
            r"|관리비 받기가 끝나지 않아)[^A-Za-z|]*$"
        ),
        lambda text: text,
    ),
    # ── 우리 단지 가치 점수 계산(complex_metric) 문구 — 원문 그대로 (세션 428 재검사관) ──
    # 최근 6개월 시세 줄을 하나도 못 읽어 아무것도 안 쓰고 멈춘 날의 사유 — "시세 기록을 확인해 주세요"
    # 안내가 알림에서 "처음 보는 문제" 로 바뀌지 않게. 위 두 규칙과 같은 꼴(영문·`|` 섞이면 통과 안 함).
    (
        re.compile(r"^최근 6개월 시세 기록을 하나도 못 읽어서[^A-Za-z|]*$"),
        lambda text: text,
    ),
    # ── 결제 사유 2종 — billing_charge._mark_retry 가 만드는 우리 접두어 (세션 410) ──
    # ⚠ 반드시 **맨 앞**이다. 사유 문자열 뒤에 PortOne 예외 원문이 이어 붙는데, 그 안의
    #   timeout·50x 가 먼저 이기면 "상대 서버(네이버·정부 자료)가 …" 안내가 나가 결제
    #   맥락이 통째로 지워진다. 우리 코드가 박은 접두어가 예외 본문의 낱말 추측보다
    #   확실하다 — 구체 원인은 billing 로그(logger.warning)에 그대로 있다.
    #   상태값(PortOne SDK PaymentStatus)에 따라 원인이 다르다 — 처리 중·취소됨을 "승인 안 됨"
    #   으로 뭉개면 틀린 안내가 된다(세션 410 결제 검사관 MEDIUM). 목록에 없는 상태는
    #   **원인을 추측하지 않되 결제 맥락은 지키는** 맨 아래 포괄 규칙이 받는다 —
    #   `_portone_status()` 가 빈 문자열을 돌려주면(`routers/payment.py`, SDK 응답에
    #   status 가 없는 경우) `결제 미완료 (status=)` 가 만들어지는데, 옛 코드에선 이게
    #   아무 규칙에도 안 맞아 "처음 보는 문제" 로 떨어져 **결제 알림인지조차 사라졌다**
    #   (세션 410 결제 검사관 D3).
    (
        re.compile(r"결제 미완료 \(status=(?:PENDING|READY|VIRTUAL_ACCOUNT_ISSUED)\)"),
        "결제 대행 회사에서 아직 처리 중이라 결제가 확인되지 않았어요.",
    ),
    (
        re.compile(r"결제 미완료 \(status=(?:CANCELLED|PARTIAL_CANCELLED)\)"),
        "결제됐다가 취소됐어요.",
    ),
    (
        re.compile(r"결제 미완료 \(status=FAILED\)"),
        "카드 결제가 승인되지 않았어요(잔액 부족·한도 초과·카드 정지 등).",
    ),
    (
        # 위 세 줄이 못 잡은 상태값(빈 문자열 포함)을 받는 포괄 규칙 — 반드시 셋 **뒤**다.
        # 까닭은 추측하지 않되 "결제 문제"라는 맥락만은 남긴다.
        re.compile(r"결제 미완료 \(status="),
        "결제가 완료되지 않았어요(까닭은 서버 기록에 있어요).",
    ),
    (
        re.compile(r"결제 호출 실패"),
        "결제 대행 회사 서버를 부르다 실패했어요.",
    ),
    # ── data.go.kr 오류 봉투 — `kapt_api._body_or_raise` 가 만드는 우리 접두어 (09-25 실사고) ──
    # 메시지 모양: "data.go.kr 오류 코드 04(HTTP 에러) — op=getHsmpLaborCostInfoV3".
    # ⚠ 아래 timeout·HTTP 규칙보다 **앞**이어야 한다 — 05 의 원문 사유(SERVICETIMEOUT_ERROR)
    #   가 `timed? ?out` 에 먼저 걸리면 "상대 서버가 제때…" 로 번역돼 사유 번호가 사라진다.
    # 번호별 뜻은 이 레포가 실제 응답 원문으로 본 것만 적는다(kapt_api._error_envelope 표).
    # 한 문장에 마침표 하나 — plainify_detail 이 꼬리 마침표만 떼고 뒤에 말을 붙인다.
    (
        re.compile(r"data\.go\.kr 오류 코드 04\b"),
        "공공데이터 서버가 자료를 못 줬어요(사유 번호 04, 우리 잘못이 아니라 상대 서버 문제라 다음 회차에 다시 받아요).",
    ),
    (
        re.compile(r"data\.go\.kr 오류 코드 05\b"),
        "공공데이터 서버가 제때 답하지 않았어요(사유 번호 05, 상대 서버 문제라 다음 회차에 다시 받아요).",
    ),
    (
        re.compile(r"data\.go\.kr 오류 코드 12\b"),
        "공공데이터 쪽에서 이 자료 서비스가 없어졌다고 알려 왔어요(사유 번호 12, Claude 에게 알려주세요).",
    ),
    (
        re.compile(r"data\.go\.kr 오류 코드 30\b"),
        "공공데이터 서버가 우리 사용 신청을 모른다고 했어요(사유 번호 30, Claude 에게 알려주세요).",
    ),
    (
        # 위 넷이 못 받은 번호 — 뜻을 추측하지 않되 "상대 서버가 거절했다"는 사실만 남긴다.
        re.compile(r"data\.go\.kr 오류 코드"),
        "공공데이터 서버가 오류를 알려 왔어요(사유 번호는 서버 기록에 있어요).",
    ),
    (
        re.compile(r"statement timeout|QueryCanceled", re.I),
        "데이터베이스가 너무 오래 걸려 스스로 멈췄어요.",
    ),
    (
        re.compile(r"invalid input syntax for type (\w+)", re.I),
        "저장된 값의 모양이 예상과 달라 계산하다 멈췄어요.",
    ),
    (
        re.compile(r"SSL connection has been closed|OperationalError|connection.*closed", re.I),
        "데이터베이스와의 연결이 도중에 끊겼어요.",
    ),
    (
        re.compile(r"ForeignKeyViolation|violates foreign key", re.I),
        "짝이 맞는 자료가 없어 저장하지 못했어요.",
    ),
    (
        # ⚠ `quota` 를 단어 경계 없이 잡으면 `disk quota`·`QuotaManager init failed` 까지
        #    "정부 자료 요청 횟수 소진"으로 오역한다(세션 407 적대검증 MEDIUM-2).
        #    틀린 번역은 번역 안 함보다 나쁘다 — 사장님이 "내일 풀리겠지" 하고 기다리는데
        #    실제 원인은 디스크 부족일 수 있다. 이 레포엔 일일 크롤 쿼터(auth/permissions.py
        #    check_quota)가 따로 있어 정부 API 무관 맥락에서 그 낱말이 나올 여지가 실재한다.
        re.compile(r"일 요청 건수.*초과|INFO-300|한도.*초과|\bquota exceeded\b|\bdaily quota\b", re.I),
        "오늘 쓸 수 있는 정부 자료 요청 횟수를 다 썼어요.",
    ),
    (
        # 실측에 있던 것 — 2026-04 air_quality 10건.
        re.compile(r"UniqueViolation|duplicate key value", re.I),
        "같은 자료를 두 번 저장하려다 멈췄어요.",
    ),
    (
        # 실측에 있던 것 — 2026-03 article_detail 2건.
        re.compile(r"NUL \(0x00\)|cannot contain NUL", re.I),
        "받아온 글자에 저장할 수 없는 문자가 섞여 있었어요.",
    ),
    # ── 여기부터는 **아직 prod 에 나온 적 없는** 선제 규칙 ──────────────────
    # 세션 407 적대검증이 정확히 짚었다: 위 문단은 "실측만 넣는다"고 적어 놓고
    # 아래 3종(429·50x·timeout)은 전 기간 0건인 선제 작성이었다 — 글과 코드가
    # 어긋난 상태였다. 지우지 않고 **남기되 구분해서 표시**한다:
    #   ① 네이버·정부 API 를 HTTP 로 부르는 코드라 언젠가 반드시 나올 형태이고
    #   ② 안 맞아도 폴백(앞 80자)으로 안전하게 처리되며
    #   ③ 미리 있으면 그날 사장님이 읽을 수 있는 문장을 받는다.
    # 실측으로 승격되면 이 구분선 위로 올린다.
    (
        re.compile(r"\b(429|too many requests)\b", re.I),
        "상대 서버가 너무 자주 왔다며 잠시 막았어요.",
    ),
    (
        # ⚠ 맨숫자 `\b50[0234]\b` 로 잡으면 "504 단지 수집 실패"·"complex 500 건 처리 후
        #    중단" 처럼 **평범한 개수**를 HTTP 상태코드로 오인한다(세션 407 적대검증
        #    MEDIUM-9 실측). 원인이 통째로 다른 것으로 바뀌어 전달되므로 맥락을 요구한다.
        re.compile(r"(?:HTTP|status[ _]?code)\D{0,6}(?:50[0234])\b|Bad Gateway|Service Unavailable", re.I),
        "상대 서버(네이버·정부 자료)가 응답하지 못했어요.",
    ),
    (
        re.compile(r"timed? ?out|ReadTimeout|ConnectTimeout", re.I),
        "상대 서버가 제때 답하지 않아 기다리다 멈췄어요.",
    ),
    (
        # 관리자 화면(스케줄러 표)에 가장 많이 뜨는 값 — 부팅 스윕·모니터 스윕이 붙이는
        # 영문 마커다(최근 90일 약 36건, `main.py` / `crawler/monitor.py`).
        # ⚠ 이 규칙이 없으면 `_is_plain_korean_tail` 이 이 영문을 "이미 우리말"로 오판한다
        #    — 개발자 흔적 정규식(`_DEV_ERROR_HINT`)에 걸리는 글자가 하나도 없어서다.
        #    그러면 `explain_stored_error` 3단계에서 원문이 그대로 화면에 남는다.
        # ⚠ **줄머리 또는 구분자(`|`) 바로 뒤**에서만 맞춘다 — 완전히 앵커를 떼면 안 된다.
        #    이 사전은 관리자 화면(`explain_stored_error`)과 텔레그램(`explain_error`)이
        #    함께 쓰는데, 아무 데서나 맞으면 `3/50개 단지 실패 (stale running 뒤처리)`
        #    처럼 **우리말 앞머리가 있는 값**이 통째로 "자동 정리됐어요" 한 줄로 뭉개져
        #    진짜 사유가 사라진다(세션 411 리뷰어 MEDIUM 실측).
        #    반대로 앵커만 두면 `원문 | stale running …` 형태를 놓치는데, 그 형태는
        #    `explain_stored_error` ⓪단계가 **먼저** 갈라 앞 원문을 따로 판정하므로
        #    여기까지 오지 않는다 — 다만 ⓪이 없는 알림 경로를 위해 `|` 뒤도 함께 본다.
        #    대소문자는 무시한다(`STALE RUNNING`).
        # ⚠ 생산자는 마커를 줄머리(`main.py:70`) 또는 `' | '` 뒤(`crawler/monitor.py:394`)
        #    에만 붙인다. prod 90일 실측(재현 가능한 질의):
        #      SELECT count(*) FROM crawl_jobs WHERE error_message LIKE 'stale running%'
        #        → 80
        #      SELECT count(*) FROM crawl_jobs WHERE error_message LIKE '%stale running%'
        #        AND error_message NOT LIKE 'stale running%'   → 0
        re.compile(r"(?:^|\|\s*)stale running", re.I),
        STALE_SWEPT_WORDS,
    ),
]


def _translate_known(raw) -> str | None:
    """실측 규칙에 맞으면 우리말 한 줄, 아니면 None ('모르는 에러'와 구분)."""
    if not raw:
        return None
    text = str(raw).strip()
    for pattern, plain in _ERROR_RULES:
        if pattern.search(text):
            return plain(text) if callable(plain) else plain
    return None


# 못 알아본 에러에 쓰는 고정 문장.
# ⚠ 한 문장 안에 마침표를 **두 번** 넣지 않는다. 이 문장은 해소 알림에서
#    `plainify_detail()` 이 꼬리 마침표만 떼고 " — 정상으로 돌아왔습니다" 를 붙이므로,
#    내부 마침표가 있으면 "…문제예요. …남아 있어요 — 정상으로…" 처럼 중간에 끊긴다
#    (세션 407 이 같은 증상을 고쳤던 자리 — 세션 410 검사관 MEDIUM 재발 지적).
# 상수로 뺀 까닭: 화면용 `explain_stored_error` 가 **로그 없이** 같은 문장을 써야 한다
#    (세션 411 — 아래 explain_stored_error docstring ④).
UNKNOWN_ERROR_WORDS = "처음 보는 문제예요(자세한 내용은 서버 기록에 남아 있어요)."


def explain_error(raw) -> str:
    """에러 원문 → 사장님이 읽는 한 줄.

    실측 패턴에 맞으면 우리말 한 줄로 바꾸고, **못 알아본 것은 원문을 싣지 않는다**
    — 원문은 로그·`crawl_jobs.error_message` 에 그대로 남아
    추적에 지장이 없다(세션 410 적대검증 MEDIUM).

    옛 구현은 앞 80자를 "개발자용 기록"이라는 이름표를 달아 실어 보냈는데, PG·PortOne
    사유(`card_declined`)나 우리 사유(`결제 미완료 (status=FAILED)`)가 영문 그대로
    나가 "어려운 말 금지" 지시를 어겼다. 이름표를 달아도 못 읽는 글자는 못 읽는다.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    # 공백뿐인 원문도 "메시지 없음"으로 본다 — 빈 문자열을 돌려주면 호출부가 더 정확한
    # 문구로 폴백한다(job_error_listener: "무슨 일인지 메시지가 남지 않았어요").
    if not text:
        return ""
    plain = _translate_known(text)
    if plain is not None:
        return plain
    # 새 규칙 후보를 모으는 유일한 grep 자리 — 못 알아본 원문은 알림에 싣지 않으므로
    # (위 docstring) 이 로그가 없으면 "어떤 말을 번역해야 하는지"를 뒤늦게 알 길이
    # crawl_jobs 뒤지기뿐이다. INFO 인 이유: 이 경로는 해소 알림 재렌더·검증 스크립트
    # 에서도 지나가므로 WARNING 이면 멀쩡한 실행이 경보처럼 보인다.
    logger.info("[plain_words] 번역 사전에 없는 에러 원문: %s", text[:300])
    return UNKNOWN_ERROR_WORDS


# ── 3. 행동 안내 — 사장님이 실제로 할 수 있는 것만 ────────────────────────
#
# 옛 문구("크롤링 로그 확인 — 네이버 응답·서버 상태 점검", "/admin#freshness 데이터
# 신선도 확인")는 사장님이 직접 할 수 있는 행동이 아니다. 알림을 읽고 **무엇을 하면
# 되는지**가 남아야 알림이 쓸모가 있다 — 그래서 전부 "Claude 에게 알려주세요" 로 끝난다.
# ⚠ "저절로 낫는 경우가 많아요" 는 **사실과 반대**였다(세션 407 적대검증 HIGH-5).
#    monitor.py 의 자가복구 선필터가 "마지막 failed 뒤 completed 가 있으면" 알림을
#    아예 안 보낸다 — 즉 **이 알림이 왔다는 건 아직 복구가 안 됐다는 뜻**인데 문구는
#    안심시키고 있었다. 사장님이 알림을 무시하는 습관이 들면 진짜 급한 알림도 묻힌다.
#
# 또 하나: 이 알림은 대부분 **새벽 2~6시 크론**에서 난다. 그 시각엔 Claude 세션이
#    없어 "알려주세요" 만으로는 할 수 있는 게 없다. 그래서 행동 안내보다 **"지금
#    손님 화면은 어떤가 / 자고 일어나도 되는가"** 를 먼저 말한다 — 사장님이 그 시각에
#    실제로 내리는 결정은 그것 하나뿐이다.
ACTION_WORDS: dict[str, str] = {
    "crawl_failed": (
        "→ 손님 화면은 그대로 보입니다(예전에 받아둔 자료). 새 자료만 안 들어와요.\n"
        "   아침에 Claude 에게 알려주시면 됩니다."
    ),
    "crawl_failed_burst": (
        "→ 같은 작업이 짧은 사이에 여러 번 실패했어요. 손님 화면은 그대로 보입니다.\n"
        "   아침에 Claude 에게 알려주세요."
    ),
    "crawl_stale": (
        "→ 작업이 멈춘 채로 있어요. 손님 화면은 그대로 보입니다.\n"
        "   서버를 다시 켜야 할 수 있으니 아침에 Claude 에게 알려주세요."
    ),
    "freshness": (
        "→ 손님 화면은 그대로 보이지만 자료가 오래됐어요.\n"
        "   하루가 지나도 그대로면 Claude 에게 알려주세요."
    ),
    # ⚠ 결제·정산 잡은 "자료가 안 들어온다"가 아니라 **돈이 안 걷힌다**는 뜻이라
    #    crawl_failed 문구를 쓰면 심각도를 정반대로 안내하게 된다(세션 408 실측:
    #    빌링키 자동결제 실패에 "새 자료만 안 들어와요"가 붙어 나갔다).
    "billing_failed": (
        "→ 구독료가 자동으로 걷히지 않았어요. 손님 화면은 그대로 쓰입니다.\n"
        "   돈이 걸린 일이라 아침에 꼭 Claude 에게 알려주세요."
    ),
}


def _has_final_consonant(word: str) -> bool:
    """마지막 글자에 받침이 있나 — 한글이 아니면 False(안전한 기본값)."""
    if not word:
        return False
    last = word[-1]
    if "가" <= last <= "힣":
        return bool((ord(last) - 0xAC00) % 28)
    return False


def eul_reul(word: str) -> str:
    """앞말 받침 유무로 '을/를' 선택 — "공시가격 수집를" 같은 문장 방지(세션 408)."""
    return "을" if _has_final_consonant(word) else "를"


# 결제·정산 성격의 잡 — 이 목록에 있으면 billing_failed 안내를 쓴다.
#
# ⚠ 이 레포엔 잡 이름 체계가 **둘** 있고 서로 다르다(infra.md §잡 이름 ≠ job_type).
#    두 경로가 서로 다른 값을 넘기므로 집합도 둘로 나눈다 — 한쪽만 채우면
#    "고쳤는데 실제로는 그대로 나가는" 상태가 된다(세션 408 적대검증 실사고).
#      · 스케줄러 잡 id : job_error_listener 가 APScheduler event.job_id 로 받음
#      · DB job_type    : monitor.py → alert_format 이 CrawlJob.job_type 으로 받음 (주 경로)
#    billing 은 두 체계에서 이름이 같지만(둘 다 "billing_charge"), 그건 우연이라
#    의존하지 않는다.
_BILLING_JOB_IDS: frozenset[str] = frozenset({"billing_charge"})
_BILLING_JOB_TYPES: frozenset[str] = frozenset({"billing_charge"})


def action_words_for_job(job_id: str) -> str:
    """스케줄러 잡 id → 그 잡 성격에 맞는 행동 안내 (job_error_listener 경로).

    결제 잡과 수집 잡은 사장님이 받아야 할 뜻이 다르다(돈 vs 자료).
    """
    if job_id in _BILLING_JOB_IDS:
        return ACTION_WORDS["billing_failed"]
    return ACTION_WORDS["crawl_failed"]


def action_words_for_job_type(kind: str, job_type=None) -> str:
    """장애 종류 + DB job_type → 행동 안내 (monitor → alert_format 주 경로).

    kind 가 크롤 실패 계열이고 job_type 이 결제 잡이면 결제 안내로 갈린다.
    freshness 등 job_type 이 없는 알림은 기존 kind 기반 문구를 그대로 쓴다.
    """
    if job_type and str(job_type) in _BILLING_JOB_TYPES:
        if kind in ("crawl_failed", "crawl_failed_burst", "crawl_stale"):
            return ACTION_WORDS["billing_failed"]
    return action_words(kind)


_ACTION_DEFAULT = "→ 무슨 일인지 확인이 필요해요. 아침에 Claude 에게 알려주세요."


def action_words(kind: str) -> str:
    """장애 종류 → 사장님이 실제로 할 수 있는 행동 한 줄."""
    return ACTION_WORDS.get(kind, _ACTION_DEFAULT)


# ── 4. 신선도 상태 — 신호등 색 코드 → 우리말 ──────────────────────────────
#
# freshness 알림은 red 일 때만 나가지만(monitor.py), 값 영역 전체를 덮어 둔다 —
# 나중에 yellow 도 알리게 바뀌어도 영문이 새지 않도록.
_STATUS_WORDS: dict[str, str] = {
    "red": "한참 안 들어옴",
    "yellow": "조금 늦음",
    "green": "정상",
    "unknown": "알 수 없음",
}


def status_words(status) -> str:
    """신선도 상태 코드 → 우리말. 모르는 값은 원문."""
    if not status:
        return ""
    return _STATUS_WORDS.get(str(status), str(status))


# ── 5. 저장된 옛 문장 되살리기 (render-time 번역) ────────────────────────
#
# `monitor_alerts.detail` 에는 옛 형식 문장이 22건 쌓여 있다(세션 407 실측):
#     "field_drift_monitor 작업 1건 실패 — (psycopg2.errors.InvalidTextRepresentation) ..."
#     "article_detail_backfill 작업 1건이 1시간 넘게 running 상태 — 마비 의심"
# 이 문장은 **복구 알림 때 그대로 다시 발송**된다(monitor.py 가 alert.detail 을
# format_resolved_batch 로 넘김). 그래서 "앞으로 만드는 문장"만 고치면 옛 22건이
# 해소될 때 영문이 한 번씩 더 나간다.
#
# 사장님 결정(2026-09-15): **저장된 값은 건드리지 않고 보낼 때 바꾼다.**
# DB 를 안 고치므로 되돌리기가 안전하고, 옛 기록·새 기록이 한 문장 형태로 통일된다.

# "<job_type> 작업" 으로 시작하는 옛 형식 — 맨 앞의 영문 토큰만 우리말로 바꾼다.
_LEGACY_JOB_PREFIX = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s+작업")

# 옛 문장 꼬리에 붙은 개발자 에러 — " — " 뒤를 통째로 번역 대상으로 본다.
_LEGACY_ERROR_TAIL = re.compile(r"^(?P<head>.*?작업.*?)\s+—\s+(?P<err>.+)$", re.S)

# 옛 문장에 박힌 영문 상태어 — 우리말로.
#
# "— 마비 의심" 은 단순 치환이 아니라 **떼어낸다**. 해소 알림이 이 문장 뒤에 다시
# " — 멈춘 작업을 강제 정리해…" 를 이어 붙이기 때문에, 그대로 두면 줄표가 세 번
# 이어진 "…돌고 있는 상태 — 마비 의심 — 멈춘 작업을…" 이 된다(세션 407 렌더 실측).
# 뒤 문구가 이미 "멈췄다" 는 사실을 말하므로 앞의 추측 표현은 군더더기다.
_LEGACY_WORDS = (
    ("running 상태 — 마비 의심", "돌고 있어요"),
    ("running 상태", "돌고 있는 상태"),
    ("신선도 red", "한참 안 들어옴"),
    ("신선도 yellow", "조금 늦음"),
    # 버스트(몰려서 실패) 옛 문장 — "자가복구로 분류" 는 순수 개발자 말이다
    # (세션 407 적대검증 MEDIUM-7).
    ("(일부 성공이 섞여 자가복구로 분류됐지만 묶음 실패)", "(일부는 됐지만 몰려서 실패)"),
)


def plainify_detail(detail) -> str:
    """저장된 옛 detail 문장 → 사장님이 읽는 문장 (발송 직전 변환).

    이미 우리말인 새 문장은 아무것도 안 바꾼다(정규식이 안 맞으면 원문 그대로).
    되돌리기 안전 — 이 함수를 빼도 저장된 값은 그대로다.
    """
    if not detail:
        return ""
    text = str(detail)

    # ① 맨 앞 영문 작업 이름 → 우리말
    m = _LEGACY_JOB_PREFIX.match(text)
    if m:
        code = m.group(1)
        text = f"{job_words(code)} 작업" + text[m.end():]

    # ② 꼬리의 개발자 에러 → 쉬운 한 줄
    #    "— 마비 의심" 처럼 이미 우리말인 꼬리는 번역기가 원문을 그대로 돌려주므로 안전.
    m = _LEGACY_ERROR_TAIL.match(text)
    if m:
        err = m.group("err").strip()
        # 판정 순서가 중요하다. ①먼저 "아는 에러인가"를 본다 — 실측 규칙에 맞으면
        # 우리말 표현이 섞여 있든 말든 번역한다. ②규칙에 안 맞을 때만 "이미 사람
        # 말인가"를 보고 그대로 둔다.
        # ⚠ 세션 407 구현 중 이 순서를 거꾸로 짰다가 실제로 새는 걸 봤다:
        #   "official_price 작업 1건 실패 — (s378 수동 정정) 14:54 statement timeout
        #    연쇄 크래시" 는 우리말이 섞여 있어 '사람 말'로 오판돼 번역을 건너뛰었고,
        #   정작 사장님이 모르는 'statement timeout' 이 그대로 나갔다.
        plain = _translate_known(err)
        if plain is not None:
            text = f"{m.group('head').strip()} — {plain}"
        elif not _is_plain_korean_tail(err):
            text = f"{m.group('head').strip()} — {explain_error(err)}"

    # ③ 남은 영문 상태어
    for old, new in _LEGACY_WORDS:
        text = text.replace(old, new)

    # ④ 문장 끝 마침표 정리.
    #    이 문장은 해소 알림에서 "<detail> — 정상으로 돌아왔습니다." 처럼 **뒤에 말이
    #    더 붙는다**. 번역된 까닭이 "…멈췄어요." 로 끝나면 마침표가 문장 중간에 박혀
    #    "…멈췄어요. — 정상으로 돌아왔습니다." 가 된다(세션 407 렌더 실측).
    #    읽는 흐름이 끊기므로 꼬리 마침표만 떼고, 뒤 문구가 이어 붙게 한다.
    return text.rstrip().rstrip(".")


# 꼬리가 이미 우리말 안내인지 — 개발자 에러 흔적이 하나라도 있으면 우리말이 아니다.
#
# ⚠ 이 정규식이 못 잡으면 **번역도 80자 컷도 건너뛰고 원문이 통째로 나간다**
#    (`plainify_detail` ②단계에서 `explain_error` 조차 우회하는 유일한 경로).
#    세션 407 적대검증 HIGH-1: 처음엔 `Error\)` 로 **닫는 괄호가 붙은** 형태
#    `(psycopg2.errors.X)` 만 잡아서, 파이썬 예외의 표준 형태인 `KeyError: articleList`
#    가 통째로 샜다. 네이버가 상세 API 응답 키를 바꾸면 실제로 나는 오류다(세션 401
#    키 드리프트 실사고) — 즉 이 PR 이 없애려던 증상이 그 입력에서 살아 있었다.
_DEV_ERROR_HINT = re.compile(
    r"[A-Za-z]{3,}[._][A-Za-z]"      # psycopg2.errors / module.attr
    r"|\(psycopg2"
    r"|[A-Za-z]+Error\b"             # KeyError: / ValueError: / RuntimeError …
    r"|\bTraceback\b|\bException\b"
    r"|SQL:"
    r"|[A-Z]{2,}-\d"                 # INFO-300 류
)


def _is_plain_korean_tail(text: str) -> bool:
    """꼬리 문구가 이미 사람 말인지 판정 — 개발자 에러 흔적이 없으면 True."""
    return not _DEV_ERROR_HINT.search(text)


def explain_stored_error(raw) -> str:
    """저장된 `crawl_jobs.error_message` → 관리자 화면에 보여줄 한 줄 (세션 411).

    화면(스케줄러 표·일괄 재크롤 진행률)에 뜨는 값도 알림과 같은 기준으로 다룬다
    (infra.md §텔레그램 알림 문구: "error_message 도 관리자 화면에 보이므로 같은 기준").
    원문은 지우지 않는다 — 라우터가 raw 를 그대로 함께 내보내고 화면은 `title` 로 남긴다.

    판정 순서 (`plainify_detail` ②단계와 **같은 순서, 같은 이유**):
      ⓪ 뒤에 붙은 스윕 마커 분리 — 앞의 원문이 진짜 사유라 그것부터 판정한다
      ① 빈값 → 빈 문자열 (호출부가 "메시지 없음" 을 스스로 판단하게)
      ② 아는 에러인가 — 실측 규칙에 맞으면 우리말이 섞여 있든 말든 번역한다
      ③ 규칙에 안 맞을 때만 "이미 사람 말인가" — 맞으면 **원문 그대로**
      ④ 그래도 아니면 고정 문장, 로그는 남기지 않는다 — 화면 폴링(60초·3~15초)마다
         수집 로그가 반복돼 P1-2 재료를 오염시키기 때문. 원문은 crawl_jobs 에 이미 있다

    ⚠ ②와 ③의 순서를 거꾸로 하면 실제로 샌다(세션 407 실측). 저장값 중에는
      `(s378 수동 정정) 14:54 statement timeout 연쇄 크래시` 처럼 **우리말이 섞인 영문**이
      있는데, ③을 먼저 보면 "사람 말" 로 오판해 번역을 건너뛰고 정작 사장님이 모르는
      `statement timeout` 이 화면에 그대로 남는다.

    ③이 필요한 까닭은 반대 방향이다. 저장값 상당수가 이미 우리말 문장
    (`3/50개 단지 실패`·`필드 드리프트 위반: …`)인데, ③ 없이 ④로 떨어뜨리면 멀쩡한
    설명이 "처음 보는 문제예요" 로 뭉개져 정보가 오히려 줄어든다.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""

    # 부팅 스윕·모니터 스윕이 `원문 || ' | ' || 'stale running — …'` 로 뒤에 붙인다
    # (main.py / crawler/monitor.py, #443). 앞의 원문이 진짜 사유라 그것부터 판정하고
    # 정리 문장을 뒤에 잇는다 — 규칙 하나로는 이 형태가 영문 그대로 샜다
    # (세션 411 검사관 HIGH-1).
    # 대소문자·구분자 앞뒤 공백은 `_STALE_TAIL` 이 함께 흡수한다. 되돌이(재귀) 깊이는
    # 1이다: head 에는 구분자가 다시 들어갈 수 없고(non-greedy), head 가 비면 두 번째
    # 호출이 빈값 검사에서 바로 끝난다.
    stale_m = _STALE_TAIL.match(text)
    if stale_m:
        head = stale_m.group("head").strip()
        head_plain = explain_stored_error(head)
        if not head_plain:
            return STALE_SWEPT_WORDS
        return f"{head_plain.rstrip('.')} — 그 뒤 {STALE_SWEPT_WORDS}"

    plain = _translate_known(text)
    if plain is not None:
        return plain
    if _is_plain_korean_tail(text):
        return text
    # ⚠ `explain_error(text)` 를 부르지 않는다 — 그 함수의 INFO 로그는 "새 규칙 후보"를
    #    모으는 자리인데, 이 경로는 관리자 화면 폴링(스케줄러 60초·재크롤 진행률 3~15초)이
    #    페이지를 열어둔 내내 반복 호출한다. 같은 원문이 수십 번 쌓여 "3번 이상 나온 원문
    #    = 규칙 후보" 집계가 화면을 켜둔 시간에 좌우된다. 원문은 crawl_jobs 에 이미 있다.
    return UNKNOWN_ERROR_WORDS
