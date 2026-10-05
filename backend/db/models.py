"""SQLAlchemy ORM 모델"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base
from utils import utcnow


class Complex(Base):
    __tablename__ = "complexes"
    __table_args__ = (
        Index("ix_complexes_region", "sido", "sigungu", "dong"),
    )

    complex_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    complex_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cortar_no: Mapped[str | None] = mapped_column(String(20))
    real_estate_type_code: Mapped[str | None] = mapped_column(String(10))
    real_estate_type_name: Mapped[str | None] = mapped_column(String(50))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    total_household_count: Mapped[int | None] = mapped_column(Integer)
    high_floor: Mapped[int | None] = mapped_column(Integer)
    low_floor: Mapped[int | None] = mapped_column(Integer)
    use_approve_ymd: Mapped[str | None] = mapped_column(String(8))
    total_dong_count: Mapped[int | None] = mapped_column(Integer)
    min_supply_area_m2: Mapped[float | None] = mapped_column(Float)
    max_supply_area_m2: Mapped[float | None] = mapped_column(Float)
    cortar_address: Mapped[str | None] = mapped_column(String(500))
    # 비정규화 지역 컬럼
    sido: Mapped[str | None] = mapped_column(String(30))
    sigungu: Mapped[str | None] = mapped_column(String(30))
    dong: Mapped[str | None] = mapped_column(String(30))
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # V058 — 우리 목록 크롤 완주 시각(1페이지 정상 응답 + 마지막 페이지까지 오류 0). 자매 일괄 스탬프·오류 경로가 못 찍는 배치 선정 키
    articles_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # V058 — 사용자가 start-crawl 을 호출한 시각(= 사람이 그 단지를 봤다). 인기 크롤 선정 키
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 단지 상세 정보 (get_complex_detail API)
    heat_method_type: Mapped[str | None] = mapped_column(String(50))
    total_parking_count: Mapped[int | None] = mapped_column(Integer)
    construction_company: Mapped[str | None] = mapped_column(String(200))
    floor_area_ratio: Mapped[str | None] = mapped_column(String(20))
    building_coverage_ratio: Mapped[str | None] = mapped_column(String(20))
    detail_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 국토부 실거래가 백필 마지막 시도 시각 (V046 — 매칭 결과 무관, 시도 사실만 기록.
    # "이미 시도했지만 국토부 데이터 자체가 없던 단지"의 무한 재시도 방지용)
    public_data_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 단지 상세 보완 필드
    address: Mapped[str | None] = mapped_column(String(500))
    road_address: Mapped[str | None] = mapped_column(String(500))
    heat_fuel_type: Mapped[str | None] = mapped_column(String(50))
    parking_count_by_household: Mapped[float | None] = mapped_column(Float)
    management_office_tel: Mapped[str | None] = mapped_column(String(30))
    # Phase 1: 시세 관련
    nearby_median_price: Mapped[int | None] = mapped_column(Integer)
    jeonse_rate: Mapped[float | None] = mapped_column(Float)
    recent_trades_6m: Mapped[int | None] = mapped_column(Integer)
    has_pool: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        Index("ix_articles_complex_active", "complex_no", "is_active"),
        Index("ix_articles_price_changed", "price_changed_at", "is_active"),
        Index("ix_articles_trade_active", "complex_no", "is_active", "trade_type_name"),
    )

    article_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    # index=True 없음 (V059, 세션 406) — 단독 인덱스 ix_articles_complex_no 는
    # 위 ix_articles_complex_active/idx_articles_confirm_sort 의 선행 칼럼에 완전히
    # 포섭돼 읽기에 기여하지 않으면서 쓰기 비용만 더했다. 되살리면 prod 와 어긋난다.
    complex_no: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_type_name: Mapped[str | None] = mapped_column(String(20))
    building_name: Mapped[str | None] = mapped_column(String(50))
    floor_info: Mapped[str | None] = mapped_column(String(20))
    floor_number: Mapped[int | None] = mapped_column(Integer)
    deal_or_warrant_prc: Mapped[str | None] = mapped_column(String(50))
    rent_prc: Mapped[str | None] = mapped_column(String(50))
    area1_m2: Mapped[float | None] = mapped_column(Float)
    area2_m2: Mapped[float | None] = mapped_column(Float)
    direction: Mapped[str | None] = mapped_column(String(20))
    article_feature_desc: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(ARRAY(Text))
    realtor_name: Mapped[str | None] = mapped_column(String(100))
    article_confirm_ymd: Mapped[str | None] = mapped_column(String(8))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    complex_name: Mapped[str | None] = mapped_column(String(200))
    article_name: Mapped[str | None] = mapped_column(String(200))
    realtor_id: Mapped[str | None] = mapped_column(String(50))
    realtor_phone: Mapped[str | None] = mapped_column(String(50))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    article_real_estate_type_name: Mapped[str | None] = mapped_column(String(50))
    is_presale: Mapped[bool] = mapped_column(Boolean, default=False)
    # 상세 정보
    detail_description: Mapped[str | None] = mapped_column(Text)
    room_count: Mapped[int | None] = mapped_column(Integer)
    bathroom_count: Mapped[int | None] = mapped_column(Integer)
    move_in_date: Mapped[str | None] = mapped_column(String(20))
    maintenance_cost: Mapped[str | None] = mapped_column(String(20))
    parking_count: Mapped[str | None] = mapped_column(String(20))
    photo_urls: Mapped[list | None] = mapped_column(ARRAY(Text))
    representative_img_url: Mapped[str | None] = mapped_column(Text)
    realtor_phone_display: Mapped[str | None] = mapped_column(String(50))
    realtor_address: Mapped[str | None] = mapped_column(String(300))
    heating_type: Mapped[str | None] = mapped_column(String(50))
    total_floor_count: Mapped[int | None] = mapped_column(Integer)
    jibun_address: Mapped[str | None] = mapped_column(String(500))
    use_approve_ymd: Mapped[str | None] = mapped_column(String(8))
    acquisition_tax: Mapped[str | None] = mapped_column(String(50))
    broker_fee: Mapped[str | None] = mapped_column(String(50))
    # 사전 계산 컬럼
    numeric_price: Mapped[int | None] = mapped_column(Integer)
    numeric_rent_price: Mapped[int | None] = mapped_column(Integer)
    price_per_pyeong: Mapped[int | None] = mapped_column(Integer)
    numeric_maintenance_cost: Mapped[int | None] = mapped_column(Integer)
    # Phase 1: 가격 변동 추적
    previous_price: Mapped[int | None] = mapped_column(Integer)
    price_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # #9 매물 가치 필드 (리스트 API 응답, 크롤 시점 값)
    price_change_state: Mapped[str | None] = mapped_column(String(20))
    article_status: Mapped[str | None] = mapped_column(String(10))
    same_addr_cnt: Mapped[int | None] = mapped_column(Integer)
    same_addr_min_prc: Mapped[str | None] = mapped_column(String(50))
    same_addr_max_prc: Mapped[str | None] = mapped_column(String(50))
    verification_type_code: Mapped[str | None] = mapped_column(String(20))
    is_direct_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    cp_name: Mapped[str | None] = mapped_column(String(50))
    site_image_count: Mapped[int | None] = mapped_column(Integer)
    same_addr_premium_min: Mapped[str | None] = mapped_column(String(30))
    same_addr_premium_max: Mapped[str | None] = mapped_column(String(30))
    premium_prc: Mapped[str | None] = mapped_column(String(30))
    # #10 매물 상세 4필드 (상세 API articleDetail 응답, 크롤 시점 값)
    # detail_status_code 는 위 #9 article_status(리스트 API)와 출처가 다름 — 혼동 주의
    walking_time_to_subway: Mapped[int | None] = mapped_column(Integer)  # 지하철역 도보시간 (분)
    isale_right_type_name: Mapped[str | None] = mapped_column(String(30))  # 분양권 유형명 (분양권 매물만)
    detail_status_code: Mapped[str | None] = mapped_column(String(10))  # 상세 API 매물 상태코드
    trade_complete: Mapped[bool] = mapped_column(Boolean, default=False)  # 거래완료 여부
    # 크롤러 메타데이터
    detail_crawled: Mapped[bool] = mapped_column(Boolean, default=False)
    # 상세 API 가 이 매물에 "매물 단위 오류"(error 가 dict, code != NotExistInformation)를
    # 연속으로 답한 횟수. _DETAIL_FAIL_CAP 이상이면 상세 시도 대상에서 제외 (V056, 세션 395).
    # 시스템성 transient(error 가 문자열)는 세지 않는다 — 네이버 전체 장애로 살아있는 매물이
    # 무더기 제외되는 것을 막기 위함.
    detail_fail_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(50))
    scheduler_job_id: Mapped[str | None] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MonitorAlert(Base):
    """크롤링 모니터 알림 쿨다운 상태 (V026)."""

    __tablename__ = "monitor_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    detail: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_notified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    daily_crawl_quota: Mapped[int] = mapped_column(Integer, default=5)
    daily_export_quota: Mapped[int] = mapped_column(Integer, default=10)
    daily_price_collect_quota: Mapped[int] = mapped_column(Integer, default=5)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    login_count: Mapped[int] = mapped_column(Integer, default=0)
    agree_marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 유료 이용권 만료일 (NULL = 유료 이력 없음). approved_until(무료 검증, 무기한)과 독립 —
    # 게이트는 둘 중 하나라도 유효하면 통과해 결제가 무료 무기한 승인을 격하시키지 않는다. (V035)
    paid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentVerification(Base):
    """공인중개사 검증 — 자격증/사업자등록 검증 데이터"""
    __tablename__ = "agent_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    license_number: Mapped[str | None] = mapped_column(String)
    license_doc_path: Mapped[str | None] = mapped_column(String)
    business_number: Mapped[str | None] = mapped_column(String)
    office_name: Mapped[str | None] = mapped_column(String)
    representative_name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String)  # 연락처 (선택 입력, V033)
    business_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    license_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # V-WORLD 부동산중개업사무소 대조 결과 (V034) — "진짜 중개사무소인가" 검증
    broker_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # 매칭+영업중
    broker_jurirno: Mapped[str | None] = mapped_column(String)  # 매칭된 국토부 등록번호
    broker_status: Mapped[str | None] = mapped_column(String)  # 영업상태명 또는 미매칭 사유
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(String)
    reviewed_by: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Payment(Base):
    """결제 내역 — 유료 구독 1회 결제 기록 (V035).

    payment_id 가 PK 인 이유: PortOne paymentId 와 동일 값을 우리가 생성해 멱등성 보장
    (같은 ID 재시도 가능, complete 가 status=paid 면 재연장 거부). 금액 대조·환불 추적은
    구조화 컬럼이라야 가능해 audit_logs JSON 이 아닌 정식 테이블로 둔다.
    """
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_user_id", "user_id"),
    )

    payment_id: Mapped[str] = mapped_column(String, primary_key=True)  # pay{uuid} (영숫자만 — PortOne KPN/KCP 특수문자 금지)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    plan: Mapped[str] = mapped_column(String, nullable=False)  # PLAN_PRICES 키
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 원 단위, 서버 결정값
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")  # ready|paid|failed|refunded
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict | None] = mapped_column(JSON)  # PortOne 응답 원본 (감사·환불)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BillingKey(Base):
    """빌링키 등록 — 카드 한 번 등록 → 매달 자동결제 (V036, 방식 B: 우리 cron).

    카드번호는 저장하지 않는다 — PortOne 빌링키 문자열(billing_key)만 보관하는 결제 위임 토큰.
    자동결제는 APScheduler 잡이 next_charge_at 도래분(status='active')을 찾아 PortOne 빌링키
    결제(POST /payments/{id}/billing-key)를 호출하고, 성공 시 paid_until 연장 + next_charge_at
    갱신, 실패 시 retry_count 증가. 해지는 status='deleted' (cron 이 더는 집지 않음).

    customer_name·customer_phone 을 저장하는 이유: KPN 빌링키 결제 호출에 customer.fullName +
    phoneNumber 가 필수라 발급 시점 값을 보관해 자동결제마다 재사용한다 (KPN 공식 제약).
    payments 테이블(V035)과의 관계: 자동결제 1건마다 payments 행이 별도 기록된다 — 멱등·금액대조·
    환불추적은 기존 payments 인프라 재활용. 본 테이블은 "카드 등록 상태"만 보유.
    """
    __tablename__ = "billing_keys"
    __table_args__ = (
        Index("ix_billing_keys_user_id", "user_id"),
    )

    # PG=BIGSERIAL(V036), SQLite(CI)=INTEGER autoincrement (BIGINT 은 SQLite ROWID 자동증가 미적용 →
    # with_variant 로 dialect 분기, domain-mapping-ssot.md dialect 패턴 답습).
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    billing_key: Mapped[str] = mapped_column(String, nullable=False)  # PortOne 빌링키 (카드번호 아님)
    plan: Mapped[str] = mapped_column(String, nullable=False)  # PLAN_PRICES 키 (자동결제 플랜)
    card_name: Mapped[str | None] = mapped_column(String)  # 카드사명 (화면 표시)
    card_last4: Mapped[str | None] = mapped_column(String)  # 카드 마지막 4자리 (화면 표시)
    customer_name: Mapped[str | None] = mapped_column(String)  # KPN 결제 필수 (customer.fullName)
    customer_phone: Mapped[str | None] = mapped_column(String)  # KPN 결제 필수 (customer.phoneNumber)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active|deleted|failed
    next_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 다음 자동결제 예정
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 결제 실패 재시도 횟수
    # 카드 여러 장 보관 시 자동결제는 is_default=True 1장으로만 (V037). 부분 유니크 인덱스는
    # prod SQL 에만(SQLite 미지원) — 한 user 당 active 기본 카드 1장 강제. cron(PR3)이 이 카드만 집음.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# 화면·API 는 세션 419(2026-09-26 사장님 결정)에 삭제, 표는 기록 보존용
class AdminSetting(Base):
    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ComplexPriceHistory(Base):
    __tablename__ = "complex_price_history"
    __table_args__ = (
        Index("idx_cph_complex", "complex_no", "trade_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complex_no: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)
    area_no: Mapped[str | None] = mapped_column(String(20))
    price_upper: Mapped[int | None] = mapped_column(Integer)
    price_lower: Mapped[int | None] = mapped_column(Integer)
    price_avg: Mapped[int | None] = mapped_column(Integer)
    base_month: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD (weekly) or YYYYMM (legacy)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ArticlePriceHistory(Base):
    __tablename__ = "article_price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[int | None] = mapped_column(Integer)
    rent_price: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CrawlerCheckpoint(Base):
    __tablename__ = "crawler_checkpoints"

    job_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ComplexPyeongDetail(Base):
    __tablename__ = "complex_pyeong_details"
    __table_args__ = (
        UniqueConstraint("complex_no", "pyeong_no", name="complex_pyeong_details_complex_no_pyeong_no_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complex_no: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    pyeong_no: Mapped[int] = mapped_column(Integer, nullable=False)
    pyeong_name: Mapped[str | None] = mapped_column(String(20))
    supply_area: Mapped[str | None] = mapped_column(String(20))
    supply_area_double: Mapped[float | None] = mapped_column(Float)
    exclusive_area: Mapped[str | None] = mapped_column(String(20))
    exclusive_rate: Mapped[str | None] = mapped_column(String(10))
    household_count_by_pyeong: Mapped[str | None] = mapped_column(String(20))
    entrance_type: Mapped[str | None] = mapped_column(String(30))
    room_count: Mapped[int | None] = mapped_column(Integer)
    bathroom_count: Mapped[int | None] = mapped_column(Integer)
    avg_maintenance_cost: Mapped[int | None] = mapped_column(Integer)
    summer_maintenance_cost: Mapped[int | None] = mapped_column(Integer)
    winter_maintenance_cost: Mapped[int | None] = mapped_column(Integer)
    # 면적별 상세 보완 필드
    floor_plan_url: Mapped[str | None] = mapped_column(Text)
    supply_pyeong: Mapped[str | None] = mapped_column(String(20))
    exclusive_pyeong: Mapped[str | None] = mapped_column(String(20))
    latest_maintenance_cost: Mapped[int | None] = mapped_column(Integer)
    maintenance_cost_basis: Mapped[str | None] = mapped_column(String(6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NaverApiCallCount(Base):
    """네이버 API 호출 시간당 집계 (영속 계측)"""
    __tablename__ = "naver_api_call_counts"
    __table_args__ = (
        UniqueConstraint("label", "bucket_hour", name="uq_nacc_label_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    bucket_hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ComplexTradeRaw(Base):
    """단지 실거래 개별 원본 (국토교통부 공공데이터) — 개별 점 차트용.

    기존 complex_price_history 는 월별 min/max/avg 집계 행이라 원본 가격을
    잃는다. 이 테이블은 거래 1건 = 행 1건으로 개별 거래를 보존한다.
    complex_no 는 FK 없음 — 매칭 실패 원본도 버리지 않기 위함(공시가격 답습).
    """

    __tablename__ = "complex_trade_raw"
    __table_args__ = (
        Index("idx_ctr_complex_ym", "complex_no", "deal_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complex_no: Mapped[str | None] = mapped_column(String(20))  # 매칭 실패 시 NULL 허용
    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)  # A1=매매
    deal_year_month: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    deal_day: Mapped[str | None] = mapped_column(String(2))
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # 만원
    area2_m2: Mapped[float | None] = mapped_column(Float)  # 전용면적 ㎡
    floor_number: Mapped[int | None] = mapped_column(Integer)
    apt_dong: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(20), nullable=False)


class ComplexOfficialPrice(Base):
    """공동주택 공시가격 (국토교통부 getApartHousingPriceAttr) — V044.

    단지 × 기준연도 × 전용면적 단위 집계. 같은 조합의 여러 호(dongNm/hoNm)를
    중위값(price_median)으로 묶고 표본 수를 ho_count 에 남긴다.

    값 계약: prvuse_ar 는 반드시 문자열 경유 Decimal 로 넣는다 — float 경유 시
    NUMERIC(8,2) 반올림으로 인접 면적과 병합될 수 있다(충돌키의 한 축).
    stdr_year 는 4자리 문자열("2026") 고정.
    """
    __tablename__ = "complex_official_prices"
    __table_args__ = (
        UniqueConstraint("complex_no", "stdr_year", "prvuse_ar", name="complex_official_prices_key"),
        # 별도 (complex_no, stdr_year) 인덱스는 두지 않는다 — UNIQUE 인덱스 선두 접두사로 커버 (V030 답습)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complex_no: Mapped[str] = mapped_column(
        String(20), ForeignKey("complexes.complex_no"), nullable=False
    )
    stdr_year: Mapped[str] = mapped_column(String(4), nullable=False)
    prvuse_ar: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    price_median: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ho_count: Mapped[int] = mapped_column(Integer, nullable=False)
    aphus_code: Mapped[str | None] = mapped_column(String(20))
    aphus_nm: Mapped[str | None] = mapped_column(String(200))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubwayStation(Base):
    """전국 도시철도 역사 (국가철도공단 레일포털 표준데이터) — V047.

    원본 그대로 "역사 × 노선" 1행 구조를 유지한다 — 환승역은 같은 station_name 이
    노선 수만큼 여러 행으로 존재하며, 묶는 것은 조회 시점의 책임이다(역명 그룹핑).

    갱신은 연 1회 CSV 전량 재적재(scripts/import_subway_stations.py)라 upsert 키가
    없다. data_date 는 원본의 행별 게시일이며 결측·비정상값(1900-01-00 등)이 섞여
    있어 nullable — 데이터셋 기준일은 이 컬럼이 아니라 CSV 파일명이 진실의 원천이다.
    """
    __tablename__ = "subway_stations"
    __table_args__ = (
        # 1,099행 소형 테이블이라 좌표 인덱스는 두지 않는다 — 조회는 전량 로드 후
        # 파이썬 haversine 계산이며 결과가 단지별 12시간 캐시된다.
        Index("ix_subway_stations_name", "station_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_number: Mapped[str | None] = mapped_column(Text)
    station_name: Mapped[str] = mapped_column(Text, nullable=False)
    line_number: Mapped[str | None] = mapped_column(Text)
    line_name: Mapped[str] = mapped_column(Text, nullable=False)
    operator: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    data_date: Mapped[date | None] = mapped_column(Date)


class KaptComplexMap(Base):
    """우리 단지 ↔ K-apt 단지 매칭 (getTotalAptList4) — V051.

    complex_no 가 PK 라 단지당 매칭은 1건 뿐이다(재매칭 시 upsert 로 덮어씀).
    저장되는 것은 **3중 게이트를 통과한 매칭만** — 법정동 일치 + 이름 유사도
    + 세대수 근사. 관리비 오표시가 치명적이라 애매하면 저장하지 않는 보수 원칙.

    match_score 는 이름 유사도(difflib ratio 0~1)로, 매칭 근거를 남겨 사후
    감사·임계 조정에 쓴다. corridor_type·kapt_household_count 는 매칭 확정 후
    getAphusBassInfoV5 로 채운다(복도유형은 관리비 수준을 좌우하는 설명 변수).
    """
    __tablename__ = "kapt_complex_map"
    __table_args__ = (
        Index("ix_kapt_map_code", "kapt_code"),
    )

    complex_no: Mapped[str] = mapped_column(
        String(20), ForeignKey("complexes.complex_no"), primary_key=True
    )
    kapt_code: Mapped[str] = mapped_column(Text, nullable=False)
    kapt_name: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[float | None] = mapped_column(Float)
    corridor_type: Mapped[str | None] = mapped_column(Text)
    kapt_household_count: Mapped[int | None] = mapped_column(Integer)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # V068: 관리비 후보월이 전부 미공개로 확인된 마지막 시각(UTC). 수집 성공 시 NULL.
    # 7일 안·같은 달이면 관리비 수집이 그 단지를 건너뛴다(세션 426).
    cost_blank_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class KaptManagementCost(Base):
    """K-apt 월별 관리비 (공용 V3 17항목 + 개별 V3 5항목) — V051.

    단지 × 조회월(YYYYMM) 1행. 같은 달 재수집 시 최신값으로 덮어쓴다.

    금액 컬럼이 전부 nullable 인 이유: 미공개 단지·미공개 항목이 흔하다.
    전 항목이 없으면 아예 행을 만들지 않는다(수집기가 skip) — 0원과 미공개를
    구분하기 위해서다. cost_per_household 는 총액/세대수이며 세대수가 없으면 None.

    breakdown 은 {오퍼레이션명: 금액} 원값으로, 합계가 이상할 때 원인 항목을
    추적하는 감사 자료다. JSON 타입 사용은 의도 — PG 는 jsonb 로, SQLite(CI)는
    직렬화로 동작해 dialect 분기 없이 같은 코드가 돈다.
    """
    __tablename__ = "kapt_management_costs"
    __table_args__ = (
        UniqueConstraint("complex_no", "cost_month", name="kapt_management_costs_key"),
        Index("ix_kapt_cost_complex", "complex_no", "cost_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    complex_no: Mapped[str] = mapped_column(
        String(20), ForeignKey("complexes.complex_no"), nullable=False
    )
    cost_month: Mapped[str] = mapped_column(String(6), nullable=False)
    common_cost: Mapped[int | None] = mapped_column(BigInteger)
    individual_cost: Mapped[int | None] = mapped_column(BigInteger)
    total_cost: Mapped[int | None] = mapped_column(BigInteger)
    cost_per_household: Mapped[int | None] = mapped_column(Integer)
    household_count: Mapped[int | None] = mapped_column(Integer)
    breakdown: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceWatchTarget(Base):
    """관심 호가 추적 대상 (V069) — 단지 + 전용면적(None = 전체 평형)."""

    __tablename__ = "price_watch_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "complex_no", "area_m2", name="uq_price_watch_target",
                         postgresql_nulls_not_distinct=True),
        Index("idx_price_watch_targets_complex", "complex_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    complex_no: Mapped[str] = mapped_column(String(20), nullable=False)
    area_m2: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceWatchSnapshot(Base):
    """관심 단지 활성 매매 매물의 날짜별(KST) 호가 기록 (V069). 하루 1행/매물."""

    __tablename__ = "price_watch_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "article_no", name="uq_price_watch_snapshot"),
        Index("idx_price_watch_snapshots_complex_date", "complex_no", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    complex_no: Mapped[str] = mapped_column(String(20), nullable=False)
    article_no: Mapped[str] = mapped_column(String(20), nullable=False)
    building_name: Mapped[str | None] = mapped_column(String(50))
    floor_info: Mapped[str | None] = mapped_column(String(20))
    area1_m2: Mapped[float | None] = mapped_column(Float)
    area2_m2: Mapped[float | None] = mapped_column(Float)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
