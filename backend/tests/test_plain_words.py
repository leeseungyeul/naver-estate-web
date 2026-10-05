"""텔레그램 알림 '쉬운 말' 사전 테스트 — crawler/plain_words.py (세션 407)

사장님 지시(2026-09-15): *"텔레그램 알림은 일반인이 봐도 무엇이 어떻게 잘못되었는지
손쉽게 알 수 있어야 해. 어려운 말은 금지야."*

이 파일이 지키는 것은 두 가지다.
  ① **사전 누락 차단** — 새 job_type 이 생겼는데 사전에 안 넣으면 알림에 영문이 샌다.
     FE 사전(crawl-job-labels.ts)과 키를 대조해 기계적으로 잡는다.
  ② **어려운 말 재유입 차단** — 누군가 알림 문구에 영문 코드·개발자 에러를 다시
     넣으면 실패한다. 사람 눈 검토로는 반복해서 새던 것이라 가드로 고정한다.

DB 의존 없는 순수 함수 테스트.
"""

import logging
import re
from pathlib import Path

from crawler.plain_words import (
    JOB_WORDS,
    STALE_SWEPT_WORDS,
    UNKNOWN_ERROR_WORDS,
    action_words,
    explain_error,
    explain_stored_error,
    job_words,
    plainify_detail,
    status_words,
)

# FE 사전 — 같은 job_type 키 체계를 쓴다(양쪽 다 DB job_type 기준).
_FE_LABELS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "crawl-job-labels.ts"


def _fe_job_type_keys() -> set[str]:
    """crawl-job-labels.ts 의 최상위 키(job_type) 추출 — TS 파싱 없이 텍스트로.

    check-job-labels.mjs 의 extractLabelKeys 와 같은 규칙(들여쓰기 2칸 + 대문자 허용).
    """
    src = _FE_LABELS.read_text(encoding="utf-8")
    body = src.split("CRAWL_JOB_LABELS")[1]
    return set(re.findall(r"^ {2}([A-Za-z0-9_]+):\s*\{", body, re.M))


# ── ① 사전 정합 ──────────────────────────────────────────────────────────


def test_be_dict_covers_every_fe_job_type():
    """FE 화면이 아는 작업은 알림도 전부 우리말로 부를 수 있어야 한다.

    빠지면 그 작업이 실패했을 때 텔레그램에 영문 코드가 그대로 찍힌다 — 사장님
    지적("어려운 말 너무 많다")의 실체가 바로 이것이었다(세션 399·403 선례).
    """
    missing = sorted(_fe_job_type_keys() - set(JOB_WORDS))
    assert not missing, f"알림 사전에 우리말 이름이 없는 작업: {missing}"


# FE 사전이 일부러 비워 둔 값 — `check-job-labels.mjs` 의 LABEL_EXEMPT 와 같은 뜻.
# 화면에는 이름표가 불필요하지만 **알림에는 영문이 그대로 찍히므로** BE 사전에는 둔다
# (세션 407 적대검증 MEDIUM-8).
_FE_EXEMPT = {"manual", "test", "x"}


def test_fe_dict_covers_every_be_job_type():
    """반대 방향 — 알림만 알고 화면이 모르는 작업이 없어야 한다(양쪽 표기 통일)."""
    missing = sorted(set(JOB_WORDS) - _fe_job_type_keys() - _FE_EXEMPT)
    assert not missing, f"화면 사전(crawl-job-labels.ts)에 없는 작업: {missing}"


def test_job_words_values_have_no_english():
    """우리말 이름에 영문이 섞이면 안 된다 (K-apt·data.go.kr 같은 고유명사만 예외).

    세션 407 이전 FE 라벨에는 "단지 상세 backfill APT" 처럼 영문이 남아 있었다.
    """
    allowed = ("K-apt", "data.go.kr")
    offenders = []
    for code, word in JOB_WORDS.items():
        stripped = word
        for a in allowed:
            stripped = stripped.replace(a, "")
        if re.search(r"[A-Za-z]{2,}", stripped):
            offenders.append((code, word))
    assert not offenders, f"우리말 이름에 영문이 남아 있다: {offenders}"


def test_job_words_unknown_code_falls_back_to_raw():
    """사전에 없는 코드는 원문 그대로 — 알림 자체가 안 나가는 것보다 낫다."""
    assert job_words("some_new_job") == "some_new_job"
    assert job_words(None) == ""


# ── ② 에러 번역 ──────────────────────────────────────────────────────────
#
# 아래 원문은 전부 prod crawl_jobs.error_message 실측값이다(세션 407, 최근 14일 +
# monitor_alerts 22건). 지어낸 에러는 넣지 않는다 — 안 맞는 번역이 오해를 만든다.


def test_explain_error_translates_real_prod_errors():
    """실측 에러 5종이 전부 우리말 한 줄이 된다 (개발자 용어 0)."""
    cases = [
        "(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout",
        '(psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type integer: ""',
        "(psycopg2.OperationalError) SSL connection has been closed unexpectedly",
        "(psycopg2.errors.ForeignKeyViolation) insert or update on table violates foreign key",
        "CPMS 치명적 에러: CPMS API INFO-300: 일 요청 건수(1000건)를 초과하였습니다",
    ]
    for raw in cases:
        plain = explain_error(raw)
        assert "psycopg2" not in plain, plain
        assert "SQL" not in plain, plain
        assert re.search(r"[가-힣]", plain), f"우리말이 아니다: {plain}"
        assert plain.endswith("요."), f"설명 문장이 아니다: {plain}"


def test_explain_error_unknown_has_no_raw_text():
    """모르는 에러는 **원문을 한 조각도 싣지 않는다** (세션 410 적대검증 MEDIUM).

    옛 구현은 앞 80자를 "개발자용 기록"이라는 이름표를 달아 실어 보냈는데, 이름표를
    달아도 못 읽는 글자는 못 읽는다 — PG 사유(`card_declined`) 같은 영문이 그대로
    나갔다. 원문은 로그·crawl_jobs.error_message 에 남으므로
    알림에서 빼도 추적에 지장이 없다.
    """
    plain = explain_error("완전히 새로운 종류의 문제 " + "x" * 300)
    assert plain.startswith("처음 보는 문제예요"), plain
    assert "완전히 새로운 종류의 문제" not in plain, plain
    assert "xxx" not in plain, plain
    assert re.search(r"[A-Za-z]", plain) is None, f"영문이 남았다: {plain}"
    assert len(plain) <= 120, f"너무 길다: {len(plain)}"


def test_explain_error_translates_billing_reasons():
    """billing_charge._mark_retry 가 만드는 두 사유가 우리말이 된다 (세션 410).

    옛 코드에선 이 둘이 '모르는 에러' 로 빠져 `결제 미완료 (status=FAILED)` 처럼
    영문 상태값이 그대로 텔레그램에 실렸다.
    """
    assert "카드 결제가 승인되지 않았어요" in explain_error("결제 미완료 (status=FAILED)")
    # 상태값마다 원인이 다르다 — 처리 중·취소됨을 "승인 안 됨" 으로 뭉개면 틀린 안내
    # (세션 410 결제 검사관 MEDIUM). 목록에 없는 상태는 원인을 추측하지 않되,
    # **결제 맥락은 지키는** 포괄 규칙이 받는다(D3 — 옛 코드는 "처음 보는 문제" 로
    # 떨어져 결제 알림인지조차 사라졌다).
    assert "아직 처리 중" in explain_error("결제 미완료 (status=PENDING)")
    assert "아직 처리 중" in explain_error("결제 미완료 (status=READY)")
    assert "취소됐어요" in explain_error("결제 미완료 (status=CANCELLED)")
    assert "취소됐어요" in explain_error("결제 미완료 (status=PARTIAL_CANCELLED)")
    unknown = explain_error("결제 미완료 (status=SOMETHING_NEW)")
    assert "결제가 완료되지 않았어요" in unknown and "SOMETHING_NEW" not in unknown, unknown
    # `_portone_status()` 가 빈 문자열을 돌려주는 실경로 (routers/payment.py)
    empty = explain_error("결제 미완료 (status=)")
    assert "결제가 완료되지 않았어요" in empty, empty
    assert "결제 대행 회사" in explain_error("결제 호출 실패: boom")
    # 규칙이 맨 앞이라 예외 본문의 timeout 낱말보다 결제 접두어가 이긴다(결제 맥락 보존, 세션 410)
    assert "결제 대행 회사" in explain_error("결제 호출 실패: ReadTimeout")
    assert "결제 대행 회사" in explain_error("결제 호출 실패: HTTP 502 Bad Gateway")


def test_unknown_sentence_has_no_internal_period():
    """'처음 보는 문제' 문장에는 마침표가 **맨 끝 하나뿐**이어야 한다 (세션 410 검사관 MEDIUM).

    해소 알림은 `plainify_detail()` 이 꼬리 마침표만 떼고 " — 정상으로 돌아왔습니다" 를
    이어 붙인다. 문장 중간에 마침표가 있으면 "…문제예요. …남아 있어요 — 정상으로…"
    처럼 한 줄 안에서 흐름이 두 번 끊긴다(세션 407 이 같은 증상을 고쳤던 자리).
    """
    out = explain_error("SomethingNew: zzz")
    assert out.endswith("."), out
    assert out.count(".") == 1, out
    assert "." not in out[:-1], out


def test_explain_error_empty_is_empty():
    assert explain_error("") == ""
    assert explain_error(None) == ""
    # 공백뿐인 원문도 "메시지 없음" — job_error_listener 가 더 정확한 문구로 폴백한다
    assert explain_error("   ") == ""


# ── ②-b 관리자 화면에 뜨는 저장된 에러 (세션 411) ───────────────────────
#
# `crawl_jobs.error_message` 는 알림뿐 아니라 관리자 화면(스케줄러 표·일괄 재크롤
# 진행률)에도 그대로 보인다 — 같은 기준(전부 쉬운 우리말)을 적용한다.


def test_explain_stored_error_translates_known():
    """아는 에러는 저장값이어도 우리말 한 줄로."""
    out = explain_stored_error(
        '(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout'
    )
    assert out == "데이터베이스가 너무 오래 걸려 스스로 멈췄어요."


def test_explain_stored_error_keeps_already_plain_korean():
    """이미 우리말인 저장값은 **원문 그대로** — 뭉개면 정보가 오히려 줄어든다.

    prod 저장값 상당수가 우리 코드가 직접 쓴 우리말 문장이다("3/50개 단지 실패").
    이걸 '처음 보는 문제' 로 바꾸면 화면이 더 불친절해진다.
    """
    assert explain_stored_error("3/50개 단지 실패") == "3/50개 단지 실패"


def test_explain_stored_error_translates_korean_mixed_english():
    """우리말이 섞여 있어도 아는 에러면 번역한다 (판정 순서 회귀 — 세션 407).

    '이미 사람 말인가' 를 먼저 보면 이 입력이 통과해버려 `statement timeout` 이
    화면에 그대로 남는다.
    """
    out = explain_stored_error("(s378 수동 정정) 14:54 statement timeout 연쇄 크래시")
    assert out == "데이터베이스가 너무 오래 걸려 스스로 멈췄어요."
    assert "timeout" not in out


def test_explain_stored_error_unknown_falls_back_to_fixed_sentence():
    """모르는 영문은 고정 문장 — 원문은 화면의 title 과 DB 에 그대로 남는다."""
    out = explain_stored_error("KeyError: articleList")
    assert out == explain_error("KeyError: articleList")
    assert "KeyError" not in out


def test_explain_stored_error_translates_stale_running_marker():
    """스윕 마커(화면 최다 값)도 우리말로 — 개발자 흔적이 없어 '우리말' 로 오판되던 값."""
    for raw in (
        "stale running — swept by monitor",
        "stale running — swept on startup",
    ):
        out = explain_stored_error(raw)
        assert out == "작업이 오래 멈춰 있어 자동으로 정리됐어요.", raw
        assert "stale" not in out, raw


def test_explain_stored_error_splits_appended_stale_marker():
    """스윕 마커가 **뒤에 붙은** 형태 — 앞의 진짜 사유를 살리고 정리 문장을 잇는다.

    두 스윕 모두 `COALESCE(error_message || ' | ', '') || 'stale running — …'` 로
    원문 뒤에 덧붙인다(main.py / crawler/monitor.py, #443). 이게 오히려 흔한 모양인데
    앵커(`^stale running`) 규칙만으로는 안 맞아 영문이 그대로 샜다(세션 411 HIGH-1).
    """
    out = explain_stored_error("3/50개 단지 실패 | stale running — swept by monitor")
    assert out == "3/50개 단지 실패 — 그 뒤 " + STALE_SWEPT_WORDS
    assert "stale" not in out


def test_explain_stored_error_translates_head_before_appended_marker():
    """앞머리가 개발자 에러면 그것도 번역한 뒤 정리 문장을 잇는다 (꼬리 마침표는 뗀다)."""
    out = explain_stored_error(
        "(psycopg2.errors.QueryCanceled) canceling statement due to statement timeout"
        " | stale running — swept on startup"
    )
    assert out == "데이터베이스가 너무 오래 걸려 스스로 멈췄어요 — 그 뒤 " + STALE_SWEPT_WORDS
    assert "psycopg2" not in out and "stale" not in out


def test_explain_stored_error_pure_stale_marker_still_uses_rule():
    """원문 없이 마커만 있는 순수형은 규칙 경로 그대로 — ⓪단계가 이걸 망치지 않는다."""
    assert explain_stored_error("stale running — swept on startup") == STALE_SWEPT_WORDS


def test_explain_stored_error_stale_marker_is_case_insensitive():
    """대문자로 저장돼도 정리 문장으로 — 마커 문구는 사람이 손으로 쓰는 자리라 흔들린다."""
    assert explain_stored_error("STALE RUNNING — swept") == STALE_SWEPT_WORDS


def test_explain_stored_error_korean_head_with_marker_inside_is_kept():
    """우리말 앞머리 뒤에 마커가 섞여 있으면 **원문 그대로** — 진짜 사유를 지우지 않는다.

    규칙을 완전히 앵커 없이 두면 이 값이 통째로 "자동 정리됐어요" 로 뭉개져
    `3/50개 단지 실패` 라는 진짜 사유가 사라진다(세션 411 리뷰어 MEDIUM 실측).
    생산자는 마커를 줄머리나 `' | '` 뒤에만 붙이므로, 이런 값은 ③(이미 우리말)
    경로로 가는 게 맞다.
    """
    raw = "3/50개 단지 실패 (stale running 뒤처리)"
    assert explain_stored_error(raw) == raw


def test_explain_stored_error_manual_stale_marker_at_line_start():
    """줄머리 마커는 뒤에 우리말 설명이 붙어도 정리 문장으로 — 사람이 손으로 쓴 값."""
    out = explain_stored_error(
        "stale running — 세션409 수동 재시작(02:24)으로 중단, 부팅 스윕 5분 임계 사각"
    )
    assert out == STALE_SWEPT_WORDS


def test_explain_error_does_not_swallow_korean_head_with_marker():
    """알림 경로(`explain_error`)에는 ③이 없다 — 규칙이 안 맞으면 고정 문장이 정답.

    이 사전은 화면과 알림이 함께 쓴다. 규칙을 앵커 없이 되돌리면 이 값이 정리 문장으로
    바뀌어(진짜 사유 소실) 이 단언이 깨진다 — 알림 경로의 계약을 박제하는 자리다.
    """
    assert explain_error("작업 3건 실패 stale running 관련") == UNKNOWN_ERROR_WORDS


def test_explain_stored_error_appended_stale_marker_case_insensitive():
    """뒤에 붙은 마커도 대소문자를 가리지 않고 갈라낸다 — 앞의 사유는 그대로 살린다."""
    out = explain_stored_error("3/50개 단지 실패 | Stale Running — swept by monitor")
    assert out == "3/50개 단지 실패 — 그 뒤 " + STALE_SWEPT_WORDS
    assert "Stale" not in out


def test_explain_stored_error_does_not_log_unknown_original(caplog):
    """화면용 경로는 **수집 로그를 남기지 않는다** (세션 411).

    관리자 화면은 스케줄러 상태를 60초, 재크롤 진행률을 3~15초마다 다시 부른다.
    여기서 `explain_error` 를 부르면 페이지를 열어둔 내내 같은 원문이 INFO 로 쌓여,
    "같은 원문 3번 이상 = 새 규칙 후보" 집계가 **화면을 켜둔 시간에 좌우된다**.
    원문은 `crawl_jobs.error_message` 에 이미 있으므로 추적에는 지장이 없다.
    """
    with caplog.at_level(logging.INFO, logger="crawler.plain_words"):
        out = explain_stored_error("KeyError: articleList")

    assert out == UNKNOWN_ERROR_WORDS
    leaked = [r for r in caplog.records if "번역 사전에 없는" in r.getMessage()]
    assert not leaked, f"화면 경로가 수집 로그를 남겼다 — P1-2 집계 오염: {leaked}"


def test_explain_error_still_logs_unknown_original(caplog):
    """반대로 알림 경로(`explain_error`)는 예전처럼 수집 로그를 남긴다 (대조군).

    위 테스트가 '로그가 안 찍힌다' 를 단언하는데, 로거 이름이나 레벨이 틀려서
    애초에 아무것도 안 잡히는 것이면 그 단언은 늘 통과한다 — 이 대조군이 그걸 막는다.
    """
    with caplog.at_level(logging.INFO, logger="crawler.plain_words"):
        out = explain_error("KeyError: articleList")

    assert out == UNKNOWN_ERROR_WORDS
    assert [r for r in caplog.records if "번역 사전에 없는" in r.getMessage()], (
        "알림 경로의 새 규칙 후보 수집 로그가 사라졌다 — 유일한 grep 자리다"
    )


def test_explain_stored_error_empty_is_empty():
    """빈값은 빈 문자열 — 화면이 '에러 없음' 을 스스로 판단한다."""
    assert explain_stored_error("") == ""
    assert explain_stored_error(None) == ""
    assert explain_stored_error("   ") == ""


# ── ③ 저장된 옛 문장 되살리기 (render-time) ──────────────────────────────
#
# monitor_alerts.detail 에는 세션 407 이전 형식이 22건 남아 있다. 저장값은 건드리지
# 않고(되돌리기 안전) 발송 직전에만 바꾼다 — 사장님 결정(2026-09-15).


def test_plainify_legacy_failed_detail():
    """옛 실패 문장 → 영문 작업명·개발자 에러가 둘 다 사라진다."""
    legacy = (
        "field_drift_monitor 작업 1건 실패 — (psycopg2.errors.InvalidTextRepresentation) "
        'invalid input syntax for type integer: ""'
    )
    out = plainify_detail(legacy)
    assert "field_drift_monitor" not in out, out
    assert "psycopg2" not in out, out
    assert "정보 안 채워지면 알림" in out, out


def test_plainify_legacy_stale_detail():
    """옛 마비 문장 → 'running 상태' 같은 영문 상태어까지 우리말로."""
    legacy = "article_detail_backfill 작업 1건이 1시간 넘게 running 상태 — 마비 의심"
    out = plainify_detail(legacy)
    assert "article_detail_backfill" not in out, out
    assert "running" not in out, out
    assert "빠진 정보 뒤늦게 채우기" in out, out


def test_plainify_translates_known_error_even_when_korean_mixed():
    """우리말이 섞여 있어도 아는 에러면 번역한다.

    ⚠ 세션 407 구현 중 실제로 샜던 경로다 — 판정 순서를 '이미 우리말인가' 먼저로
    두면 "(s378 수동 정정) 14:54 statement timeout 연쇄 크래시" 처럼 우리말이 섞인
    문장이 '사람 말'로 오판돼 statement timeout 이 그대로 나갔다.
    """
    legacy = "official_price 작업 1건 실패 — (s378 수동 정정) 14:54 statement timeout 연쇄 크래시"
    out = plainify_detail(legacy)
    assert "statement timeout" not in out, out
    assert "정부 공시가격 받기" in out, out


def test_plainify_leaves_already_plain_tail_alone():
    """이미 우리말 안내인 꼬리는 건드리지 않는다 (마비 의심 등)."""
    out = plainify_detail("crawl_details 작업 1건이 1시간 넘게 돌고 있는 상태 — 마비 의심")
    assert "마비 의심" in out, out


def test_plainify_freshness_status_word():
    """신선도 색 코드(red)도 우리말로."""
    out = plainify_detail("매물 데이터 미축적 (신선도 red, 마지막 갱신 09-12 19:29)")
    assert "red" not in out, out
    assert "한참 안 들어옴" in out, out


def test_dev_error_hint_catches_python_exceptions():
    """파이썬 예외(`XxxError: …`)가 '이미 사람 말'로 오판되면 안 된다.

    ⚠ 세션 407 적대검증 HIGH-1 회귀 가드. 옛 `_DEV_ERROR_HINT` 는 `Error\\)` 로
    **닫는 괄호가 붙은** 형태만 잡아서, `KeyError: articleList` 처럼 괄호 없는 표준
    파이썬 예외가 통째로 샜다. 이 경로는 `explain_error` 조차 우회해 80자 컷도
    안 걸리므로, 원문이 그대로 텔레그램에 나갔다 — 이 PR 이 없애려던 바로 그 증상.
    """
    leaky = [
        "KeyError: articleList",
        "ValueError: bad literal",
        "TypeError: NoneType is not subscriptable",
        "IndexError: list index out of range",
        "AttributeError: 'NoneType' object has no attribute 'get'",
        "RuntimeError: session closed",
        "Traceback (most recent call last):",
    ]
    for raw in leaky:
        out = plainify_detail(f"complex_articles 작업 1건 실패 — {raw}")
        # 예외 이름·원문이 한 조각도 안 남아야 한다 (세션 410 — 옛 코드는 "개발자용
        # 기록" 이라는 이름표를 달아 앞 80자를 그대로 실어 보냈다).
        assert "처음 보는 문제예요" in out, f"개발자 예외가 그대로 노출됐다: {out}"
        exc_name = raw.split(":")[0].strip()  # KeyError / Traceback (most recent call last) …
        assert exc_name.split()[0] not in out, out


def test_error_rules_do_not_misfire_on_plain_numbers():
    """평범한 개수를 HTTP 상태코드로 오인하면 안 된다 (적대검증 MEDIUM-9).

    `\\b50[0234]\\b` 는 "504 단지 수집 실패"·"complex 500 건 처리" 를 서버 오류로
    오역했다. 틀린 번역은 번역 안 함보다 나쁘다 — 원인이 통째로 바뀌어 전달된다.
    """
    assert "상대 서버" not in explain_error("504 단지 수집 실패")
    assert "상대 서버" not in explain_error("complex 500 건 처리 후 중단")
    # 맥락이 있으면 제대로 잡는다
    assert "상대 서버" in explain_error("HTTP 502 Bad Gateway")


def test_quota_rule_needs_context():
    """`quota` 단독 매칭은 무관한 에러를 오역한다 (적대검증 MEDIUM-2)."""
    assert "정부 자료 요청 횟수" not in explain_error("disk quota warning")
    assert "정부 자료 요청 횟수" not in explain_error("QuotaManager init failed")
    assert "정부 자료 요청 횟수" in explain_error("일 요청 건수(1000건)를 초과하였습니다")


def test_unknown_error_has_no_raw_text():
    """아는 에러는 번역하고, 모르는 에러는 원문 없이 고정 문장만 내보낸다 (세션 410)."""
    out = explain_error("(psycopg2.errors.UniqueViolation) duplicate key value")
    # UniqueViolation 은 실측 규칙에 있으므로 번역돼야 한다
    assert "두 번 저장" in out, out
    out2 = explain_error("SomethingCompletelyNew: 처음 보는 형식")
    assert "처음 보는 문제예요" in out2, out2
    assert "SomethingCompletelyNew" not in out2, out2


def test_traceback_is_not_leaked():
    """트레이스백은 어느 줄도 알림에 싣지 않는다 (세션 410).

    옛 구현은 마지막 줄을 '단서'로 남겼는데, 그 줄이 곧 개발자 원문이라
    "어려운 말 금지" 지시와 충돌했다. 원문은 서버 로그에 그대로 있다.
    """
    tb = "Traceback (most recent call last):\n  File x, line 1\nValueError: 진짜 원인"
    out = explain_error(tb)
    assert out.startswith("처음 보는 문제예요"), out
    assert "Traceback" not in out, out
    assert "ValueError" not in out, out
    assert "진짜 원인" not in out, out


def test_rendered_alert_has_no_english_identifiers():
    """렌더된 알림 전문에 영문 식별자가 없어야 한다 (적대검증 MEDIUM-8).

    기존 테스트는 `assert "complex_articles" not in msg` 처럼 **이미 아는 문자열만**
    막아서, 사전에 없는 새 job_type 이 생기면 영문이 그대로 나가는 것을 못 잡았다.
    허용 목록(고유명사·URL)을 뺀 뒤 영문 낱말이 남으면 실패한다.
    """
    from datetime import datetime, timezone

    from crawler.alert_format import format_issue_message

    ctx = {"active_count": 1, "now": datetime(2026, 9, 14, 19, 4, tzinfo=timezone.utc)}
    cases = [
        ("crawl_failed", {"job_type": "field_drift_monitor", "count": 1,
                          "error": "(psycopg2.errors.QueryCanceled) statement timeout",
                          "processed": 0, "total": 0}),
        ("crawl_stale", {"job_type": "article_detail_backfill", "count": 1, "stale_hours": 4}),
        ("crawl_failed_burst", {"job_type": "complex_articles", "count": 13,
                                "window_min": 60, "error": "statement timeout", "targets": 13}),
    ]
    # 허용: HTML 태그·고유명사. URL 이 나오는 freshness 는 별도 케이스라 여기서 제외.
    allowed = ("b", "K-apt", "Claude", "data.go.kr")
    for kind, data in cases:
        msg = format_issue_message(kind, data, event="new", header_ctx=ctx)
        stripped = re.sub(r"<[^>]+>", "", msg)
        for a in allowed:
            stripped = stripped.replace(a, "")
        leftovers = re.findall(r"[A-Za-z][A-Za-z0-9_.]{2,}", stripped)
        assert not leftovers, f"{kind}: 영문이 남아 있다 {leftovers}\n{msg}"


def test_plainify_new_format_not_double_translated():
    """세션 407 이후 새 형식은 이미 우리말이라 내용이 바뀌지 않는다 (이중 변환 방지).

    단 **꼬리 마침표 하나는 의도적으로 떼어낸다** — 이 문장 뒤에 해소 알림이
    " — 정상으로 돌아왔습니다." 를 이어 붙이므로, 마침표가 남으면 문장 한가운데
    마침표가 박힌다("…멈췄어요. — 정상으로 돌아왔습니다."). 세션 407 렌더 실측으로
    발견해 plainify_detail ④ 단계에서 처리한다.
    """
    new = "정보 안 채워지면 알림 작업 1건 실패 — 저장된 값의 모양이 예상과 달라 계산하다 멈췄어요."
    out = plainify_detail(new)
    assert out == new.rstrip("."), out
    # 내용 자체는 그대로 — 단어가 다시 번역되거나 사라지지 않는다
    assert "정보 안 채워지면 알림" in out and "계산하다 멈췄어요" in out


def test_plainify_empty():
    assert plainify_detail("") == ""
    assert plainify_detail(None) == ""


# ── ④ 상태·행동 문구 ─────────────────────────────────────────────────────


def test_status_words_covers_all_freshness_states():
    """신선도 4상태 전부 우리말 (freshness._status 의 값 영역)."""
    for code in ("red", "yellow", "green", "unknown"):
        assert re.search(r"[가-힣]", status_words(code)), code


# ── ⑤ 접두어 통일 — 알림 모듈 전수 스캔 (세션 408) ────────────────────────
#
# 텔레그램 알림 접두어는 3채널 공통 `[서버 알림]` 이다. 채널마다 다른 이름
# (`[내부모니터]`·`[내부즉시]`)을 쓰면 사장님이 발신처마다 다른 낱말을 외워야 하고,
# 무엇보다 "내부/즉시" 는 개발자 관점의 분류라 읽는 사람에게 뜻이 없다.
#
# ⚠ 손으로 파일 목록을 적지 않는다 — 이 레포는 "가드가 한쪽만 봐서 놓친" 전례가 있다
#    ([[feedback_guard_skipped_by_path_filter]], s403 #521). send_telegram 을 부르는
#    모듈을 **소스에서 추출**해 전수 대조한다(test_alert_time_kst_guard 의 검증된 패턴).
# ⚠ 테스트 파일은 스캔 대상에서 뺀다 — 이 파일 자신이 금지 문자열을 담고 있어
#    스스로를 잡는다(가드가 자기 오탐으로 죽는 것 방지).

_BACKEND = Path(__file__).resolve().parent.parent
_TELEGRAM_SEARCH_DIRS = ("crawler", "routers", "services")
_TELEGRAM_SENDER = "services/telegram.py"

# 옛 채널별 접두어 — 알림 문구에 다시 나타나면 안 된다.
_LEGACY_PREFIXES = ("[내부모니터]", "[내부즉시]", "[외부감시]")


def _telegram_modules() -> list[Path]:
    """`send_telegram` 을 호출하는 모듈 전수 — 손 목록이 아니라 추출."""
    found: list[Path] = []
    for d in _TELEGRAM_SEARCH_DIRS:
        for path in (_BACKEND / d).rglob("*.py"):
            if "__pycache__" in path.parts or path.name.startswith("test_"):
                continue
            if path.relative_to(_BACKEND).as_posix() == _TELEGRAM_SENDER:
                continue
            if "send_telegram" in path.read_text(encoding="utf-8"):
                found.append(path)
    return found


def _telegram_workflow_files() -> list[Path]:
    """텔레그램 API 를 직접 부르는 **워크플로 YAML** — `.py` 전용 스캔의 사각지대.

    ⚠ `[외부감시]` 는 이 레포에서 **오직 healthcheck.yml 만** 쓰던 접두어인데,
       모듈 스캔이 `.py` 만 보는 탓에 legacy 목록에 넣어 둔 의미가 0 이었다
       (세션 408 적대검증 MEDIUM-1: YAML 문구를 옛날로 되돌려도 CI 는 초록).
       파일명을 손으로 적지 않고 `api.telegram.org` 호출로 추출한다.
    """
    wf_dir = _BACKEND.parent / ".github" / "workflows"
    if not wf_dir.is_dir():
        return []
    return [
        p for p in wf_dir.rglob("*.yml")
        if "api.telegram.org" in p.read_text(encoding="utf-8")
    ]


def _code_lines(text: str) -> list[tuple[int, str]]:
    """주석·docstring 을 걷어낸 (줄번호, 코드줄) — 설계 근거 주석이 옛 접두어를
    인용하는 경우가 실제로 있어(job_error_listener 의 세션 359 설명 등) 걷어내지
    않으면 자기오탐이 된다. test_alert_time_kst_guard._strip_comments_and_docstrings
    와 같은 패턴."""
    out: list[tuple[int, str]] = []
    in_doc = False
    doc_delim = ""
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if in_doc:
            if doc_delim in stripped:
                in_doc = False
            continue
        for delim in ('"""', "'''"):
            if stripped.startswith(delim):
                if stripped.count(delim) == 1:
                    in_doc = True
                    doc_delim = delim
                break
        if in_doc or stripped.startswith("#"):
            continue
        out.append((i, raw.split("  # ")[0]))
    return out


def test_no_legacy_alert_prefix_in_any_telegram_module():
    """알림 모듈 전수에 옛 채널별 접두어가 남아 있으면 실패.

    뮤테이션: field_drift_monitor 나 job_error_listener 의 `[서버 알림]` 을 옛 값으로
    되돌리면 이 테스트가 그 파일:줄을 대며 FAIL 한다.
    """
    hits: list[str] = []
    for path in _telegram_modules():
        rel = path.relative_to(_BACKEND).as_posix()
        for lineno, code in _code_lines(path.read_text(encoding="utf-8")):
            for bad in _LEGACY_PREFIXES:
                if bad in code:
                    hits.append(f"    {rel}:{lineno}  {bad}  {code.strip()}")

    # 워크플로 YAML 도 함께 본다 — `[외부감시]` 는 거기서만 쓰이던 접두어라
    # .py 만 훑으면 그 항목이 장식이 된다(세션 408 적대검증 MEDIUM-1).
    # YAML 은 `#` 주석만 걷어낸다(docstring 개념 없음).
    for path in _telegram_workflow_files():
        rel = path.relative_to(_BACKEND.parent).as_posix()
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if raw.lstrip().startswith("#"):
                continue
            for bad in _LEGACY_PREFIXES:
                if bad in raw:
                    hits.append(f"    {rel}:{lineno}  {bad}  {raw.strip()}")

    assert not hits, (
        "\n알림 문구에 옛 채널별 접두어가 남아 있다 — 전부 '[서버 알림]' 로 통일한다:\n"
        + "\n".join(hits)
    )


def test_prefix_guard_also_scans_workflow_yaml():
    """가드가 워크플로 YAML 도 보고 있는지 — `[외부감시]` 항목이 장식이 되지 않게.

    뮤테이션: healthcheck.yml 의 `[서버 알림]` 을 `[외부감시]` 로 되돌리면
    test_no_legacy_alert_prefix_in_any_telegram_module 이 그 줄을 대며 FAIL 한다.
    """
    scanned = {p.name for p in _telegram_workflow_files()}
    assert "healthcheck.yml" in scanned, (
        f"텔레그램을 부르는 워크플로를 못 찾았다 (스캔: {sorted(scanned)})"
    )


def test_prefix_guard_actually_scans_alert_modules():
    """가드가 실제로 알림 모듈을 보고 있는지 (장식 방지 — 0건 스캔이면 무의미).

    경로가 바뀌거나 추출이 깨지면 위 테스트가 조용히 통과한다. 알림의 두 당사자
    모듈이 스캔 목록에 실재하는지 직접 확인한다.
    """
    scanned = {p.relative_to(_BACKEND).as_posix() for p in _telegram_modules()}
    for must in ("crawler/field_drift_monitor.py", "crawler/job_error_listener.py",
                 "crawler/monitor.py"):
        assert must in scanned, f"가드가 {must} 을 안 보고 있다 (스캔: {sorted(scanned)})"


def test_unified_prefix_actually_used():
    """통일 접두어가 실제로 쓰이고 있는지 — 옛 것을 지우기만 하고 새 것을 안 넣는 것 방지."""
    for rel in ("crawler/field_drift_monitor.py", "crawler/job_error_listener.py"):
        text = (_BACKEND / rel).read_text(encoding="utf-8")
        assert "[서버 알림]" in text, f"{rel} 에 통일 접두어가 없다"


# ── ⑥ 어려운 말 재유입 차단 — 알림 모듈 전수 (세션 409) ────────────────────
#
# 세션 408 까지 8개 창구 중 4곳만 우리말이었다("3창구 완료" 는 과장된 보고였다).
# 세션 409 에 나머지 4곳(api_version_monitor·scheduler_lock·billing_charge·payment)을
# 고치면서, **같은 말이 다시 새는 것**을 기계로 막는다.
#
# ⚠ 파일 목록을 손으로 적지 않는다 — `_telegram_modules()` 가 send_telegram 호출
#    모듈을 소스에서 추출하므로, 9번째 창구가 생겨도 자동으로 스캔된다
#    ([[feedback_guard_skipped_by_path_filter]] 답습).

# 알림 본문에 다시 나타나면 안 되는 말 — 사장님이 쓰지 않는 개발자 어휘.
_FORBIDDEN_IN_ALERTS = (
    "엔드포인트", "웹훅", "NO_OPENAPI", "[BILLING]", "[PAYMENT]",
    "PORTONE_WEBHOOK_SECRET", "VACUUM", "락 파일",
    # 세션 409 적대검증: 위 8단어만으로는 `service_official_price` 의 표준코드 이관
    # 알림("V-WORLD 표준코드 이관 감지 — cortar_legacy 코드 번역…")과 교집합이 0 이라
    # 그 창구가 영문인 채로 통과했다. 판정 로직에 능력은 있었는데 낱말이 부족했던 것.
    "cortar_legacy", "V-WORLD", "프리픽스", "표준코드", "드리프트", "백필",
)


def test_no_developer_jargon_in_any_alert_module():
    """알림을 만드는 모듈 전수에 개발자 어휘가 남아 있으면 실패.

    뮤테이션: 어느 창구든 옛 문구(예: "[BILLING] 자동결제 …")로 되돌리면
    이 테스트가 그 파일:줄을 대며 FAIL 한다.

    ⚠ **알림으로 나가는 줄만** 본다. 아래는 전부 정당해서 제외한다(세션 409 실측으로
       하나씩 확인) — 이걸 안 거르면 가드가 거짓 경보만 내고 결국 꺼진다:
         - logger.*(...)      개발자가 보는 로그 (오히려 여기 남겨야 추적된다)
         - os.getenv("X")     환경변수 **이름**
         - X = "상수"          API 응답 판정용 토큰 등
         - HTTPException(...) 텔레그램이 아니라 API 응답 본문
    """
    # 한 줄 docstring(`"""설명"""`)은 _code_lines 가 못 거른다 — 여기서 함께 제외.
    # 한 줄 docstring(`"""설명"""`)은 _code_lines 가 못 거른다 — 여기서 함께 제외.
    # `"키": "값",` 형태(지역코드·설정 사전)도 알림 문구가 아니라 데이터다 — 세션 409.
    skip_markers = ("logger.", "os.getenv", "HTTPException", "raise ", "= \"", "= '", '"""')
    dict_entry = re.compile(r'^"[^"]+":\s')

    def _log_continuation_lines(pairs):
        """여러 줄 `logger.xxx(...)` 의 **이어지는 줄** 번호 집합.

        첫 줄에만 `logger.` 가 있어 줄 단위 마커로는 못 거른다 — 세션 409 에
        `logger.warning(\\n  "…드리프트…"` 형태가 오탐으로 잡혔다. 로그는 개발자용이라
        어려운 말이 남아 있는 게 **정상**이므로 검사 대상에서 뺀다.
        """
        out, open_depth = set(), 0
        for no, raw in pairs:
            st = raw.strip()
            if open_depth > 0:
                out.add(no)
                open_depth += st.count("(") - st.count(")")
                continue
            if "logger." in st:
                open_depth = max(0, st.count("(") - st.count(")"))
        return out
    hits: list[str] = []
    for path in _telegram_modules():
        rel = path.relative_to(_BACKEND).as_posix()
        code_lines = _code_lines(path.read_text(encoding="utf-8"))
        log_lines = _log_continuation_lines(code_lines)
        for lineno, code in code_lines:
            if lineno in log_lines:
                continue
            stripped = code.strip()
            if any(m in stripped for m in skip_markers):
                continue
            # 데이터 사전 항목은 알림 문구가 아니다(지역코드 표 등).
            # ⚠ 단 **잡 라벨 사전**(_JOB_LABEL_FALLBACK)은 값이 알림 본문에 그대로
            #    찍히므로 예외에서 제외한다 — 그게 세션 409 의 HIGH-1 이었다.
            if dict_entry.match(stripped) and "job_error_listener" not in rel:
                continue
            for bad in _FORBIDDEN_IN_ALERTS:
                if bad in stripped and ('"' in stripped or "'" in stripped):
                    hits.append(f"    {rel}:{lineno}  {bad}  {stripped[:90]}")
    assert not hits, (
        "\n알림 문구에 사장님이 못 읽는 말이 남아 있다 (infra.md §텔레그램 알림 문구):\n"
        + "\n".join(hits)
    )


def test_all_eight_alert_channels_use_unified_prefix():
    """8개 창구 전부 `[서버 알림]` 접두어를 쓰는지 — 하나라도 빠지면 실패.

    세션 409 에 마지막 4곳을 채웠다. 새 창구가 생기면 이 목록이 아니라
    `_telegram_modules()` 추출 결과가 늘어나므로 자동으로 검사 대상이 된다.
    """
    # 본문 조립을 alert_format 에 **위임**하는 모듈은 제외 — 접두어가 없는 게 정상이다
    # (monitor.py 는 format_issue_message 를 부르고, 그 안에서 접두어가 붙는다).
    missing = []
    for path in _telegram_modules():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_BACKEND).as_posix()
        if "format_issue_message" in text or "format_resolved_batch" in text:
            continue
        if "[서버 알림]" not in text:
            missing.append(rel)
    assert not missing, (
        f"통일 접두어 `[서버 알림]` 가 없는 알림 모듈: {missing}\n"
        "새 창구를 만들면 접두어도 함께 붙인다(infra.md §텔레그램 알림 문구)."
    )


def test_action_words_tell_owner_what_they_can_do():
    """행동 안내는 사장님이 실제로 할 수 있는 것이어야 한다.

    옛 문구는 "크롤링 로그 확인 — 네이버 응답·서버 상태 점검" 처럼 개발자가 할 일이라
    알림을 읽어도 할 수 있는 게 없었다. 전부 'Claude 에게 알려주세요' 로 끝난다.
    """
    for kind in ("crawl_failed", "crawl_failed_burst", "crawl_stale", "freshness"):
        line = action_words(kind)
        assert "Claude" in line, f"{kind}: 무엇을 하면 되는지가 없다 — {line}"
        assert "로그" not in line, f"{kind}: 개발자용 행동이 남아 있다 — {line}"


# ── data.go.kr 오류 봉투 (세션 417 후속, 09-25 실사고) ─────────────────────────


def test_explain_error_data_go_kr_reason_codes():
    """(h) "data.go.kr 오류 코드 NN" 이 텔레그램에 그대로 나가지 않는다 — 번호별 우리말 한 줄.

    ⚠ 05 의 원문 사유(SERVICETIMEOUT_ERROR)가 timeout 규칙에 먼저 걸리면 사유 번호가
    사라진다 — 규칙 순서 가드. 뮤테이션: 04 규칙을 지우면 포괄 규칙으로 떨어져 FAIL.
    """
    cases = {
        "data.go.kr 오류 코드 04(HTTP 에러) 재시도 3회 후 — op=getHsmpLaborCostInfoV3": "사유 번호 04",
        "data.go.kr 오류 코드 05(SERVICETIMEOUT_ERROR) — op=x": "사유 번호 05",
        "data.go.kr 오류 코드 12(NO_OPENAPI_SERVICE_ERROR) — op=x": "사유 번호 12",
        "data.go.kr 오류 코드 30(SERVICE_KEY_IS_NOT_REGISTERED_ERROR) — op=x": "사유 번호 30",
        "data.go.kr 오류 코드 31(DEADLINE) — op=x": "공공데이터 서버가 오류를 알려 왔어요",
    }
    for raw, expected in cases.items():
        plain = explain_error(raw)
        assert expected in plain, (raw, plain)
        assert "data.go.kr" not in plain and "op=" not in plain, plain
        assert plain.endswith("요)."), plain
        assert plain.count(".") == 1, f"마침표가 둘 이상 — 해소 알림에서 끊긴다: {plain}"


def test_kapt_job_messages_translate_to_plain_words():
    """잡 기록 문구(api_down·partial_outage)도 사유 코드 규칙으로 번역된다(화면·알림 둘 다)."""
    for raw in (
        "연속 5단지 호출 실패 — API 장애/한도 의심, 잔여 3 (수집 0, 실패 5, 미공개 0, "
        "마지막 오류: data.go.kr 오류 코드 04(HTTP 에러) 재시도 3회 후 — op=x; "
        "생존 확인 1건도 빈 응답 — 210초 대기 뒤 중단)",
        "공공데이터 서버는 응답하지만 7단지 전부 오류 — 수집 0 (미공개 0, "
        "마지막 오류: data.go.kr 오류 코드 04(HTTP 에러) — op=x)",
    ):
        assert "사유 번호 04" in explain_error(raw)
        assert "사유 번호 04" in explain_stored_error(raw)


# ── ⑦ 관리자 스케줄러 표 이름·주기·출처 — 개발자 낱말 금지 (세션 418) ────────────
#
# 관리자 화면의 잡 이름은 텔레그램 알림과 같은 이름(add_job 정본)이라 같은 기준을 쓴다.
# 세션 418 전에는 "단지 상세 backfill APT"·"상세 백필 00:20(키 드리프트 대응)"·
# "정기 VACUUM 유지보수" 처럼 사장님이 못 읽는 말이 화면에 그대로 떴다.

# 알림 금지어에 더해, 관리자 표에서 실제로 보였던 개발자 낱말.
_FORBIDDEN_IN_ADMIN_TABLE = ("배치", "크롤링", "backfill", "빌링키", "API", "PROBE_REGISTRY")
# 매물 유형 영문 코드 — 이름에 그대로 붙어 나가던 것(단어 경계로만 잡는다).
_TYPE_CODE = re.compile(r"\b(APT|OPST|JGC|ABYG|OBYG)\b")


def test_scheduler_meta_has_no_developer_words():
    """SCHEDULER_JOB_META 의 이름·주기 폴백·출처 표시에 개발자 낱말이 없어야 한다.

    이름·주기 = 알림 금지어 + 관리자 표 금지어 + 영문 유형 코드 전부.
    출처 = 관리자 표 금지어 + 영문 유형 코드만 — 출처 칸은 "이 자료가 어느 기관에서
    오나" 를 적는 자리라 기관의 고유 이름(V-WORLD 등)과 주소는 정보다.

    뮤테이션: 이름 하나를 "단지 상세 backfill APT" 로 되돌리거나 출처에
    "(PROBE_REGISTRY)" 를 되살리면 FAIL.
    """
    from routers.admin.scheduler import SCHEDULER_JOB_META, _source_text

    hits: list[str] = []
    for job_id, meta in SCHEDULER_JOB_META.items():
        for field in ("name", "schedule"):
            text = meta[field]
            for bad in _FORBIDDEN_IN_ALERTS + _FORBIDDEN_IN_ADMIN_TABLE:
                if bad in text:
                    hits.append(f"{job_id}.{field}: '{bad}' — {text}")
            if _TYPE_CODE.search(text):
                hits.append(f"{job_id}.{field}: 영문 유형 코드 — {text}")
        source_name, _url = _source_text(meta.get("source"))
        if source_name:
            for bad in _FORBIDDEN_IN_ADMIN_TABLE:
                if bad in source_name:
                    hits.append(f"{job_id}.source: '{bad}' — {source_name}")
            if _TYPE_CODE.search(source_name):
                hits.append(f"{job_id}.source: 영문 유형 코드 — {source_name}")
    assert not hits, "관리자 스케줄러 표에 사장님이 못 읽는 말:\n  " + "\n  ".join(hits)


# ── ⑧ 달력 수동 잡·신선도 카드 이름 — 같은 작업은 같은 이름 (세션 419) ────────────
#
# 관리자 화면에는 작업 이름이 네 군데서 나온다: 자동 작업 표(add_job(name)) · 작업 목록
# (FE crawl-job-labels.ts) · 달력의 수동 실행(MANUAL_JOB_NAMES) · 신선도 카드(freshness_meta).
# 앞의 둘은 위 가드와 FE crawl-job-labels-sync 가 JOB_WORDS 에 묶었고, 뒤의 둘이
# "관리자 일괄 재수집"·"K-apt 관리비" 처럼 세 번째·네 번째 이름을 쓰고 있었다.

# 수동 실행 잡 id → 그 실행이 남기는 crawl_jobs.job_type.
# 근거 = 각 실행 경로의 CrawlJob(job_type=…) 호출부:
#   backfill_apartment_public_data → scripts/…public_data.py → service_public.backfill_price_batch
#   backfill_missing_price_history → scripts/…price_history.py → service_price.collect_price_history
#   admin_recrawl        → routers/admin/recrawl.py 부모 CrawlJob(job_type="bulk_recrawl")
#   admin_single_recrawl → service_discover.crawl_complex_articles
#   collect_official_prices → service_official_price._record_job(db, "official_price", …)
_MANUAL_ID_TO_JOB_TYPE = {
    "backfill_apartment_public_data": "price_backfill",
    "backfill_missing_price_history": "price_history",
    "admin_recrawl": "bulk_recrawl",
    "admin_single_recrawl": "complex_articles",
    "collect_official_prices": "official_price",
}

# 신선도 카드 중 "자료 이름"(단지·매물·대기질…)이 아니라 "작업 이름"을 라벨로 쓰는 카드.
# 이 카드들은 테이블이 아니라 그 작업의 CrawlJob 완료 시각을 재므로 작업 이름이 곧 라벨이다.
_JOB_NAMED_FRESHNESS_KEYS = {
    "article_detail", "complex_metric", "complex_detail_apt",
    "complex_detail_opst", "kapt_match", "kapt_costs",
}

# 관리자 화면 이름에 다시 나오면 안 되는 영문 서비스명(옛 라벨 "K-apt 관리비").
_FORBIDDEN_IN_JOB_NAMES = ("K-apt", "kapt")

# 스케줄러 잡 중 crawl_jobs 를 남기지 않아 job_type 이 없는 것 — 이름 대조 대상이 아니다.
_NO_JOB_TYPE_IDS = {
    "crawler_monitor": "감시 잡 자신은 crawl_jobs 에 기록을 남기지 않는다(monitor.py 무음 설계)",
}


def _gen_schedule_module():
    """scripts/gen_restart_schedule_table 을 불러온다(패키지가 아니라 sys.path 에 얹는다)."""
    import sys

    scripts_dir = str(Path(__file__).resolve().parents[1] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import gen_restart_schedule_table

    return gen_restart_schedule_table


def _dev_word_hits(where: str, text: str) -> list[str]:
    hits = []
    for bad in _FORBIDDEN_IN_ALERTS + _FORBIDDEN_IN_ADMIN_TABLE + _FORBIDDEN_IN_JOB_NAMES:
        if bad in text:
            hits.append(f"{where}: '{bad}' — {text}")
    if _TYPE_CODE.search(text):
        hits.append(f"{where}: 영문 유형 코드 — {text}")
    return hits


def test_manual_names_and_freshness_labels_have_no_developer_words():
    """달력 수동 잡 이름·신선도 카드 라벨에도 개발자 낱말이 없어야 한다.

    뮤테이션: 신선도 라벨 하나를 "K-apt 관리비" 로, 수동 이름 하나를 "관리자 일괄
    재수집 배치" 로 되돌리면 FAIL.
    """
    from routers.admin.freshness_meta import FRESHNESS_ITEMS
    from routers.admin.scheduler import MANUAL_JOB_NAMES

    hits: list[str] = []
    for job_id, name in MANUAL_JOB_NAMES.items():
        hits += _dev_word_hits(f"MANUAL_JOB_NAMES[{job_id}]", name)
    for item in FRESHNESS_ITEMS:
        hits += _dev_word_hits(f"freshness[{item['key']}].label", item["label"])
    assert not hits, "관리자 화면 이름에 사장님이 못 읽는 말:\n  " + "\n  ".join(hits)


def test_manual_job_names_use_job_words_plus_manual_suffix():
    """수동 실행 이름 = 그 job_type 의 JOB_WORDS + " (수동)" — 자동 작업과 같은 낱말.

    짝 표(_MANUAL_ID_TO_JOB_TYPE)와 MANUAL_JOB_NAMES 의 키가 어긋나도 실패한다 —
    새 수동 잡을 이름표에만 넣고 짝을 빠뜨리면 이 가드가 조용히 그 잡을 건너뛰기 때문.
    뮤테이션: "admin_recrawl" 값을 "관리자 일괄 재수집" 으로 되돌리면 FAIL.
    """
    from routers.admin.scheduler import MANUAL_JOB_NAMES

    assert set(MANUAL_JOB_NAMES) == set(_MANUAL_ID_TO_JOB_TYPE)
    wrong = {
        job_id: (name, f"{JOB_WORDS[_MANUAL_ID_TO_JOB_TYPE[job_id]]} (수동)")
        for job_id, name in MANUAL_JOB_NAMES.items()
        if name != f"{JOB_WORDS[_MANUAL_ID_TO_JOB_TYPE[job_id]]} (수동)"
    }
    assert not wrong, f"수동 실행 이름이 JOB_WORDS 와 다르다 (현재, 기대): {wrong}"


def test_job_named_freshness_labels_equal_job_words():
    """작업 이름을 라벨로 쓰는 신선도 카드 = 그 잡의 JOB_WORDS (잡 id → job_type 다리 경유).

    뮤테이션: "kapt_costs" 카드 라벨을 "K-apt 관리비" 로 되돌리면 FAIL.
    """
    from routers.admin.freshness_meta import FRESHNESS_ITEMS

    id_to_type = _gen_schedule_module()._ID_TO_JOB_TYPE
    by_key = {item["key"]: item for item in FRESHNESS_ITEMS}
    assert _JOB_NAMED_FRESHNESS_KEYS <= set(by_key), _JOB_NAMED_FRESHNESS_KEYS - set(by_key)
    wrong = {}
    for key in sorted(_JOB_NAMED_FRESHNESS_KEYS):
        item = by_key[key]
        expected = JOB_WORDS[id_to_type[item["scheduler_job_id"]]]
        if item["label"] != expected:
            wrong[key] = (item["label"], expected)
    assert not wrong, f"신선도 카드 라벨이 JOB_WORDS 와 다르다 (현재, 기대): {wrong}"


def test_every_registered_job_name_starts_with_job_words():
    """등록된 스케줄러 잡 전부 — add_job(name) 이 JOB_WORDS[job_type] 로 시작해야 한다.

    잡 id 와 job_type 은 이름 체계가 다르다(infra.md 경고). 다리는
    scripts/gen_restart_schedule_table.py `_ID_TO_JOB_TYPE`(재시작 시각표와 같은 표) 이고,
    거기 없는 id 는 id 가 곧 job_type 이다. popular_1030 처럼 뒤에 시각이 붙는 것은 허용.
    뮤테이션: scheduler.py 의 add_job(name=...) 하나를 옛 이름으로 되돌리면 FAIL.
    """
    gen = _gen_schedule_module()
    jobs = gen.build_jobs()
    registered = {job.id for job in jobs}
    # 예외 목록이 낡지 않게 — 등록되지 않은 id 를 예외로 들고 있으면 실패
    assert set(_NO_JOB_TYPE_IDS) <= registered, set(_NO_JOB_TYPE_IDS) - registered

    wrong = []
    for job in jobs:
        if job.id in _NO_JOB_TYPE_IDS:
            continue
        job_type = gen._ID_TO_JOB_TYPE.get(job.id, job.id)
        words = JOB_WORDS.get(job_type)
        if words is None:
            wrong.append(f"{job.id}: job_type '{job_type}' 이 JOB_WORDS 에 없다")
        elif not job.name.startswith(words):
            wrong.append(f"{job.id}: '{job.name}' 가 '{words}' 로 시작하지 않는다")
    assert not wrong, "스케줄러 잡 이름이 JOB_WORDS 와 어긋난다:\n  " + "\n  ".join(wrong)


# ── 관리비 단지 연결하기(kapt_match) 우리 문구 — 원문 보존 (세션 426 검사관) ──
_KAPT_MATCH_NOTE = (
    "단지 기본정보 3건 받기 실패 — 그 단지들은 기존 연결을 그대로 두었어요(다음 달 다시 시도)"
)


def test_kapt_match_messages_kept_as_is():
    """매칭 회차가 남기는 우리말 문구 3종은 알림·화면에 원문 그대로 나간다.

    뮤테이션 N1: `_ERROR_RULES` 의 kapt_match 규칙을 지우면 "처음 보는 문제" 로 떨어져 FAIL.
    """
    for text in (
        f"{_KAPT_MATCH_NOTE} · 연결 1건",        # 실패 > 연결 → failed
        _KAPT_MATCH_NOTE,                         # 실패 ≤ 연결 → completed 문구
        "대상 단지 14747개 전부 매칭 실패 (매칭 0건)",
    ):
        assert explain_error(text) == text, explain_error(text)


def test_kapt_match_costs_still_running_reason_kept_in_alert():
    """관리비 받기를 45분 기다려도 안 끝나 매칭을 시작 못 한 사유는 알림에도 원문 그대로 (세션 427).

    고정 문장("처음 보는 문제")으로 바뀌면 "끝난 뒤 다시 눌러 주세요" 안내가 사라진다.
    사유 글자는 수집기 상수에서 가져온다 — 수집기 문구와 이 규칙의 머리말이 어긋나면 여기서 잡힌다.
    뮤테이션: `_ERROR_RULES` kapt_match 규칙에서 `관리비 받기가 끝나지 않아` 머리말을 빼면 FAIL.
    """
    from crawler.service_kapt import _MATCH_COSTS_RUNNING_WORDS

    assert _MATCH_COSTS_RUNNING_WORDS == (
        "관리비 받기가 끝나지 않아 시작하지 못했어요 — 끝난 뒤 관리자 화면에서 다시 눌러 주세요"
    )
    assert explain_error(_MATCH_COSTS_RUNNING_WORDS) == _MATCH_COSTS_RUNNING_WORDS


def test_complex_metric_no_recent_rows_reason_kept_in_alert():
    """가치 점수 계산이 최근 6개월 시세 줄을 하나도 못 읽어 멈춘 사유는 알림에도 원문 그대로 (세션 428).

    고정 문장("처음 보는 문제")으로 바뀌면 "시세 기록을 확인해 주세요" 안내가 사라진다.
    사유 글자는 수집기 상수에서 가져온다 — 수집기 문구와 이 규칙의 머리말이 어긋나면 여기서 잡힌다.
    뮤테이션: `_ERROR_RULES` 의 complex_metric 규칙을 빼면 FAIL.
    """
    from crawler.service_metrics import _NO_RECENT_ROWS_WORDS

    assert explain_error(_NO_RECENT_ROWS_WORDS) == _NO_RECENT_ROWS_WORDS
    assert explain_stored_error(_NO_RECENT_ROWS_WORDS) == _NO_RECENT_ROWS_WORDS
    # 영문(개발자 원문)이 섞이면 원문 보존 규칙을 지나친다
    assert explain_error(_NO_RECENT_ROWS_WORDS + " psycopg2 OperationalError") != (
        _NO_RECENT_ROWS_WORDS + " psycopg2 OperationalError"
    )


def test_kapt_match_message_with_english_falls_to_unknown():
    """우리 문구 뒤에 영문(개발자 원문)이 섞이면 원문 보존 규칙을 지나쳐 고정 문장이 된다."""
    out = explain_error(f"{_KAPT_MATCH_NOTE} KaptApiError")
    assert out != f"{_KAPT_MATCH_NOTE} KaptApiError"
    assert "KaptApiError" not in out
    assert out.startswith("처음 보는 문제예요"), out


def test_kapt_match_partial_list_note_not_kept_by_rule():
    """부분 목록 문구는 영문 "K-apt" 가 있어 원문 보존 규칙에 안 걸린다 — 이 사실을 고정."""
    text = "부분 목록으로 매칭 (K-apt 2000건만 수집) — 다음 회차 재시도 필요"
    assert explain_error(text) != text
