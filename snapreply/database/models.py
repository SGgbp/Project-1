import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text,
    ForeignKey, Numeric, func, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, mapped_column

from database.connection import Base


def _uuid():
    return str(uuid.uuid4())


class Business(Base):
    __tablename__ = "businesses"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email                 = Column(String(255), unique=True, nullable=False)
    password_hash         = Column(String(255), nullable=False)
    owner_name            = Column(String(255), nullable=False)
    business_name         = Column(String(255), nullable=False)
    business_type         = Column(String(100), nullable=False)
    plan                  = Column(String(20), default="starter")  # starter | growth | pro
    owner_whatsapp        = Column(String(20), nullable=False)
    business_whatsapp     = Column(String(20))
    snapreply_number      = Column(String(20))
    twilio_number         = Column(String(20))
    city                  = Column(String(100))
    custom_greeting       = Column(Text)
    ai_persona_name       = Column(String(100), default="Your assistant")
    google_calendar_token = Column(JSONB)
    google_calendar_id    = Column(String(255))
    google_place_id       = Column(String(100))
    setup_complete        = Column(Boolean, default=False)
    setup_step            = Column(Integer, default=0)
    active                    = Column(Boolean, default=True)
    paused                    = Column(Boolean, default=False)
    consecutive_quiet_weeks   = Column(Integer, default=0)
    last_owner_message        = Column(DateTime(timezone=True))
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    updated_at            = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    subscription    = relationship("Subscription", back_populates="business", uselist=False)
    enquiries       = relationship("Enquiry", back_populates="business")
    conversations   = relationship("Conversation", back_populates="business")
    bookings        = relationship("Booking", back_populates="business")
    analytics       = relationship("DailyAnalytics", back_populates="business")
    referrals       = relationship("Referral", back_populates="referrer_business")

    @property
    def is_growth_or_pro(self) -> bool:
        return self.plan in ("growth", "pro")

    @property
    def is_pro(self) -> bool:
        return self.plan == "pro"

    @property
    def first_name(self) -> str:
        return self.owner_name.split()[0] if self.owner_name else "there"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id            = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    stripe_customer_id     = Column(String(100), unique=True, nullable=False)
    stripe_subscription_id = Column(String(100), unique=True)
    status                 = Column(String(50), default="trial")  # trial | active | cancelled | past_due
    plan                   = Column(String(20), default="starter")
    annual                 = Column(Boolean, default=False)
    trial_ends_at          = Column(DateTime(timezone=True))
    current_period_end     = Column(DateTime(timezone=True))
    cancelled_at           = Column(DateTime(timezone=True))
    sent_notifications     = Column(JSONB, default=dict)
    created_at             = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="subscription")


class Enquiry(Base):
    __tablename__ = "enquiries"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id      = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    customer_phone   = Column(String(20), nullable=False)
    customer_name    = Column(String(255))
    source           = Column(String(50), default="whatsapp")  # whatsapp | missed_call | sms
    first_message    = Column(Text)
    reply_sent       = Column(Boolean, default=False)
    seconds_to_reply = Column(Integer)
    call_sid         = Column(String(100))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="enquiries")


class Conversation(Base):
    __tablename__ = "conversations"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id    = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    customer_phone = Column(String(20), nullable=False)
    messages       = Column(JSONB, default=list)
    status         = Column(String(20), default="active")  # active | ended | booked
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    business = relationship("Business", back_populates="conversations")
    bookings = relationship("Booking", back_populates="conversation")

    @property
    def message_count(self) -> int:
        return len(self.messages) if self.messages else 0


class Booking(Base):
    __tablename__ = "bookings"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id     = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    customer_name   = Column(String(255))
    customer_phone  = Column(String(20))
    service_type    = Column(String(255))
    preferred_date  = Column(String(100))
    preferred_time  = Column(String(100))
    location        = Column(Text)
    notes           = Column(Text)
    status          = Column(String(20), default="pending")  # pending | confirmed | completed | no_show | cancelled
    reminder_sent   = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    business     = relationship("Business", back_populates="bookings")
    conversation = relationship("Conversation", back_populates="bookings")


class OwnerCommand(Base):
    __tablename__ = "owner_commands"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    command     = Column(String(50), nullable=False)
    response    = Column(Text)
    extra_data  = Column("metadata", JSONB, default=dict)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"
    __table_args__ = (UniqueConstraint("business_id", "date"),)

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id         = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    date                = Column(String(10), nullable=False)  # YYYY-MM-DD
    enquiries_count     = Column(Integer, default=0)
    conversations_count = Column(Integer, default=0)
    bookings_count      = Column(Integer, default=0)
    avg_reply_seconds   = Column(Integer, default=0)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="analytics")


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (UniqueConstraint("business_id", "customer_phone", "consent_type"),)

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id    = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"))
    customer_phone = Column(String(20), nullable=False)
    consent_type   = Column(String(50), nullable=False)
    given_at       = Column(DateTime(timezone=True), server_default=func.now())
    ip_address     = Column(String(45))


class Referral(Base):
    __tablename__ = "referrals"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True)
    referred_email       = Column(String(255))
    referral_code        = Column(String(20), unique=True, nullable=False)
    status               = Column(String(20), default="pending")  # pending | converted | rewarded
    free_months_earned   = Column(Integer, default=0)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())

    referrer_business = relationship("Business", back_populates="referrals")


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id   = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"))
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent         = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class Partner(Base):
    __tablename__ = "partners"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                     = Column(String(255), nullable=False)
    type                     = Column(String(50), nullable=False)  # insurance_broker | association | coach | whitelabel
    contact_email            = Column(String(255))
    referral_code            = Column(String(20), unique=True, nullable=False)
    commission_per_customer  = Column(Numeric(10, 2), default=10.00)
    customers_referred       = Column(Integer, default=0)
    active                   = Column(Boolean, default=True)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
