"""SQLAlchemy 엔진 및 세션 팩토리"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from services.slow_query_log import attach as _attach_slow_query_log

load_dotenv()

# 폭주 쿼리 안전망 임계값(ms) — env STATEMENT_TIMEOUT_MS, 기본 8000ms(8초).
# 0 이하면 비활성 (Supabase 기본 2min cap 으로 폴백).
STATEMENT_TIMEOUT_MS = int(os.getenv("STATEMENT_TIMEOUT_MS", "8000"))

# ── estate DB (기존) ──
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다")


def _with_explicit_driver(url: str) -> str:
    """`postgresql://` 주소에 접속 부품 이름(psycopg2)을 붙인다.

    SQLAlchemy 2.1 부터 드라이버 없는 `postgresql://` 의 기본값이 psycopg2 → psycopg(3) 로
    바뀌었다(공식 migration_21 "Default PostgreSQL driver changed to psycopg"). 설치된 건
    psycopg2 뿐이라 그대로면 엔진 생성에서 ModuleNotFoundError — 서버가 안 뜬다(세션 431,
    Dependabot #621 검토 중 venv 재현). 2.0 에서도 같은 드라이버라 동작 변화 0.
    """
    prefix = "postgresql://"
    if url.startswith(prefix):
        return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = _with_explicit_driver(DATABASE_URL)

# Sync 엔진 (크롤러 + 웹앱 공용) — NullPool: 요청마다 연결/해제 (Supabase 커넥션 한도 방지).
# pool_pre_ping: 매 checkout 전에 SELECT 1로 유효성 검사. Supabase idle timeout으로 끊긴
# 연결을 붙잡아 재사용하다가 "server closed connection unexpectedly"로 터지던 문제 방지
# (popular 크롤링 4일 실패 원인, 2026-04-10~14).
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
    echo=False,
    # connect_timeout: TCP 연결 "수립" 단계만 5초로 bound (psycopg2/libpq 네이티브).
    # Supabase 가 unreachable(느림 아니라 먹통)이면 NullPool 이 매 요청 새 connect →
    # 기본 ~2min 무한 대기하며 /health/db 워커 스레드가 쌓이던 것 차단(세션 341).
    # ⚠ 연결 수립만 제한 — 이미 맺은 연결의 쿼리 지속엔 영향 0(그건 statement_timeout
    # 담당). pool_pre_ping 의 SELECT 1 도 이미 맺은 연결이라 무관 → 크롤 회귀 없음.
    # keepalives_idle/interval: 이미 맺은 연결이 "조용히" 죽었을 때(상대가 끊김 신호도 없이
    # 사라짐) 알아채는 간격. 안 정하면 Windows 기본 2시간이다. 2026-10-05 01:26 단지 매물
    # 가져오기가 DB 연결이 끊긴 직후 멈춰 03:09 재부팅까지 약 1시간 40분 서 있었다(DB 응답
    # 대기로 추정 — 멈춘 줄을 찍은 기록은 없음, 세션 432). 60초 조용하면
    # 확인 신호, 무응답이면 30초마다 재확인 · Windows 는 횟수 10회 고정(keepalives_count
    # 무시) → 약 6분(60+30×10초) 동안 상대 컴퓨터가 신호에 전혀 답하지 않을 때만 끊김 판정.
    # 신호는 DB 프로그램이 아니라 상대 OS 가 받아 주므로, DB 가 바쁘거나 쿼리가 오래 돌아도
    # 오판하지 않는다(세션 432 실측: 5초/2초 간격에서도 pg_sleep(75) 쿼리 생존). 일부러
    # 넉넉히 잡았다(사장님 지시 — 부하로 늦어지는 경우 여유). ⚠ 한계: 풀러(Supavisor)가
    # 살아서 신호엔 답하는데 뒤쪽 DB 연결만 잃은 경우는 이 설정으로 못 잡는다.
    connect_args={"connect_timeout": 5, "keepalives_idle": 60, "keepalives_interval": 30},
)


# statement_timeout 안전망: 폭주 쿼리를 8초에 죽여 NullPool 연결을 오래 점유하며
# micro 인스턴스를 굶기는 것 방지 (세션 255). 0.46초 region 경로보다 한참 위.
#
# ⚠ 적용 방식 주의(세션 255 실측+공식문서): Supabase Supavisor 풀러는 startup
# 파라미터 options="-c statement_timeout=..." 를 무시한다(SHOW 가 2min 그대로).
# role-level ALTER ROLE 도 transaction mode 에선 무효. 실측 결과 연결 직후 명시
# SET 쿼리만 세션에 적용됨(SHOW → 8s 확인). NullPool 이라 매 요청 새 연결 →
# connect 이벤트에서 매번 SET → 모든 세션 보장.
@event.listens_for(engine, "connect")
def _set_statement_timeout(dbapi_conn, _connection_record):
    if STATEMENT_TIMEOUT_MS <= 0:
        return
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        cursor.close()
    except Exception:  # best-effort — 실패해도 연결은 정상 사용
        pass


# 슬로우 쿼리 로깅 부착 (1초 초과 SQL → logger.warning). best-effort, 실패해도 앱 정상.
# 테스트는 conftest 가 SQLite 엔진을 주입하므로 본 prod 엔진에는 미부착 → 영향 0.
_attach_slow_query_log(engine)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """DB 세션 제너레이터 (with 문 또는 의존성 주입용)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
