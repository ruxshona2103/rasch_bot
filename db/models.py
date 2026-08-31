from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# public_id 1000 dan boshlab, faqat to'lov tasdiqlanganda nextval() bilan
# atomik beriladi (arxitektura II-qism, 🆕 public_id izohi). MAX()+1 ISHLATILMAYDI.
public_id_seq = Sequence("public_id_seq", start=1000, increment=1)


class User(Base):
    __tablename__ = "users"

    user_pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Test(Base):
    __tablename__ = "tests"

    test_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), default="matematika")
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # 'jonli' | 'arxiv'
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 🆕 PDF usulida yaratilgan testning to'liq original fayli (Telegram file_id) —
    # savollar alohida rasmlarga bo'linmaydi, shu faylning o'zi userga yuboriladi.
    pdf_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="tayyorlanmoqda")
    # tayyorlanmoqda | rejalashtirilgan | jonli_davom | hisoblanmoqda |
    # yakunlangan | arxivda | bekor_qilingan
    calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Question(Base):
    __tablename__ = "questions"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.test_id"))
    order_num: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..45, ko'rsatish tartibi
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    qtype: Mapped[str] = mapped_column(String(10), nullable=False)  # 'yopiq' | 'ochiq'
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    b_difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_pk: Mapped[int] = mapped_column(ForeignKey("users.user_pk"))
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.test_id"))
    receipt_file_id: Mapped[str] = mapped_column(String(200), nullable=False)
    receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="kutilmoqda")
    # kutilmoqda | tasdiqlangan | rad_etilgan
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("user_pk", "test_id", name="uq_purchase_user_test"),)

    purchase_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_pk: Mapped[int] = mapped_column(ForeignKey("users.user_pk"))
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.test_id"))
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.payment_id"))


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("user_pk", "test_id", name="uq_attempt_user_test"),)

    attempt_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_pk: Mapped[int] = mapped_column(ForeignKey("users.user_pk"))
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.test_id"))
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # 'jonli' | 'arxiv'
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="davom_etmoqda")
    # davom_etmoqda | yakunlangan | vaqt_tugagan
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    ball_75: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(3), nullable=True)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Answer(Base):
    __tablename__ = "answers"

    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.attempt_id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.question_id"), primary_key=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AdminLog(Base):
    __tablename__ = "admin_log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_pk: Mapped[int] = mapped_column(ForeignKey("users.user_pk"))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="navbatda")  # navbatda | yuborildi | xato
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# 🆕 Global sozlamalar (kalit-qiymat) — masalan marketing e'lonlari uchun logotip file_id
class BotSetting(Base):
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


# 🆕 Apellyatsiya (IV.5-bo'lim): o'quvchi savol/kalitga e'tiroz bildiradi
class Appeal(Base):
    __tablename__ = "appeals"

    appeal_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_pk: Mapped[int] = mapped_column(ForeignKey("users.user_pk"))
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.attempt_id"))
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.test_id"))
    question_order_num: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="kutilmoqda")
    # kutilmoqda | kalit_tuzatildi | savol_chiqarildi | rad_etildi
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
