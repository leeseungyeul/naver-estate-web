"""db/database.py `_with_explicit_driver` 회귀 가드 (세션 431).

SQLAlchemy 2.1 부터 드라이버 없는 `postgresql://` 의 기본 드라이버가 psycopg(3) 로 바뀌었다.
운영 DATABASE_URL 은 `postgresql://` 꼴이고 설치된 건 psycopg2 뿐이라, 주소를 고치지 않으면
엔진 생성에서 ModuleNotFoundError — 서버가 안 뜬다. CI 는 SQLite 라 이 결함을 못 본다.

conftest 가 sys.modules["db.database"] 를 가짜 모듈로 바꾸므로(test_database_connect_timeout.py
와 같은 이유) 소스에서 함수 정의만 꺼내 따로 실행한다 — 진짜 모듈의 부작용(.env·엔진 생성) 0.
"""

import ast
import os

import sqlalchemy as sa

_DATABASE_PY = os.path.join(os.path.dirname(__file__), "..", "db", "database.py")


def _load_fn():
    with open(_DATABASE_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_with_explicit_driver"
    )
    ns: dict = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), _DATABASE_PY, "exec"), ns)
    return ns["_with_explicit_driver"]


def test_plain_postgresql_url_gets_psycopg2():
    """드라이버 없는 주소 → psycopg2 를 명시."""
    fn = _load_fn()
    assert fn("postgresql://u:p@h:5432/d") == "postgresql+psycopg2://u:p@h:5432/d"


def test_other_urls_unchanged():
    """이미 드라이버가 있거나 다른 DB 면 그대로."""
    fn = _load_fn()
    for url in ("postgresql+psycopg2://u:p@h/d", "sqlite://", "sqlite:///x.db"):
        assert fn(url) == url


def test_engine_uses_psycopg2_driver():
    """설치된 SQLAlchemy 판에서 고친 주소로 엔진을 만들면 psycopg2 를 고른다.

    create_engine 은 연결을 맺지 않으므로 네트워크 0. 2.1 에서 함수를 빼면(주소 그대로)
    psycopg 미설치로 ModuleNotFoundError — 이 테스트가 그 회귀를 잡는다.
    """
    fn = _load_fn()
    engine = sa.create_engine(fn("postgresql://u:p@127.0.0.1:1/d"))
    assert engine.dialect.driver == "psycopg2"
    engine.dispose()


def test_module_applies_normalization():
    """모듈이 실제로 DATABASE_URL 에 함수를 적용하는지(정의만 하고 안 쓰는 회귀 방지)."""
    with open(_DATABASE_PY, encoding="utf-8") as f:
        src = f.read()
    assert "DATABASE_URL = _with_explicit_driver(DATABASE_URL)" in src
    assert src.index("DATABASE_URL = _with_explicit_driver(DATABASE_URL)") < src.index(
        "engine = create_engine("
    )
