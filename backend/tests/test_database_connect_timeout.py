"""db/database.py 의 create_engine 에 connect_timeout 이 설정됐는지 회귀 가드 (세션 341).

배경: Supabase 가 unreachable(먹통)이면 NullPool 이 매 요청 새 connect → psycopg2 기본
~2min 무한 대기하며 /health/db 워커 스레드가 쌓이던 것을 connect_timeout=5 로 차단.

검증 방식 = AST 정적 파싱. conftest 가 sys.modules["db.database"] 를 가짜 SQLite 모듈로
교체하므로(conftest.py:79-85) 런타임 introspection 은 prod 엔진을 못 본다 — 그 자체가
"CI(SQLite) 영향 0" 의 증거다. 대신 소스를 AST 로 읽어 create_engine 호출의
connect_args 키워드에 connect_timeout 이 박혔는지 정적으로 확인한다(엔진 실행 부작용 0).
"""

import ast
import os

_DATABASE_PY = os.path.join(os.path.dirname(__file__), "..", "db", "database.py")


def _find_create_engine_call(tree: ast.AST) -> ast.Call | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == "create_engine":
                return node
    return None


def _connect_args_dict(call: ast.Call) -> dict | None:
    for kw in call.keywords:
        if kw.arg == "connect_args" and isinstance(kw.value, ast.Dict):
            out = {}
            for k, v in zip(kw.value.keys, kw.value.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                    out[k.value] = v.value
            return out
    return None


def test_create_engine_has_connect_timeout():
    """prod 엔진 create_engine 에 connect_args={'connect_timeout': N>0} 존재."""
    with open(_DATABASE_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    call = _find_create_engine_call(tree)
    assert call is not None, "database.py 에 create_engine 호출이 없음"

    connect_args = _connect_args_dict(call)
    assert connect_args is not None, "create_engine 에 connect_args 키워드가 없음"
    assert "connect_timeout" in connect_args, "connect_args 에 connect_timeout 없음"

    timeout = connect_args["connect_timeout"]
    assert isinstance(timeout, int) and timeout > 0, (
        f"connect_timeout 은 양의 정수여야 함 (현재 {timeout!r})"
    )


def test_create_engine_has_tcp_keepalive():
    """조용히 죽은 연결을 2시간(Windows 기본)이 아니라 수 분 안에 알아채도록 keepalive 간격 지정 (세션 432)."""
    with open(_DATABASE_PY, encoding="utf-8") as f:
        connect_args = _connect_args_dict(_find_create_engine_call(ast.parse(f.read())))
    assert connect_args is not None, "create_engine 에 connect_args 키워드가 없음"
    for key, upper in (("keepalives_idle", 300), ("keepalives_interval", 60)):
        val = connect_args.get(key)
        assert isinstance(val, int) and 0 < val <= upper, f"{key} 는 1~{upper}초여야 함 (현재 {val!r})"
    assert connect_args.get("keepalives", 1) != 0, "keepalives=0 이면 간격 설정이 무효"


def test_psycopg2_recognizes_keepalive_params():
    """keepalives_idle/interval 이 libpq 파라미터명으로 유효한지(오탈자 방지)."""
    from psycopg2.extensions import make_dsn

    dsn = make_dsn(keepalives_idle=30, keepalives_interval=10, host="localhost", dbname="x")
    assert "keepalives_idle=30" in dsn and "keepalives_interval=10" in dsn


def test_psycopg2_recognizes_connect_timeout_param():
    """psycopg2 가 connect_timeout 을 libpq 파라미터로 인식하는지(오탈자 방지).

    실제 네트워크 연결은 CI 방화벽·환경에 따라 flaky 하므로 하지 않는다. 대신
    psycopg2.extensions.make_dsn 이 connect_timeout 키워드를 유효한 DSN 으로
    변환하면(예외 없이) 파라미터명이 libpq 에 존재하는 것 — 오탈자면 여기서 터진다.
    """
    from psycopg2.extensions import make_dsn

    dsn = make_dsn(connect_timeout=5, host="localhost", dbname="x")
    assert "connect_timeout=5" in dsn
