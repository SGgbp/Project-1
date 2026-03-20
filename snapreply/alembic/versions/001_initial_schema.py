"""Initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2025-03-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("owner_name", sa.String(255), nullable=False),
        sa.Column("business_name", sa.String(255), nullable=False),
        sa.Column("business_type", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(20), server_default="starter"),
        sa.Column("owner_whatsapp", sa.String(20), nullable=False),
        sa.Column("business_whatsapp", sa.String(20)),
        sa.Column("snapreply_number", sa.String(20)),
        sa.Column("twilio_number", sa.String(20)),
        sa.Column("city", sa.String(100)),
        sa.Column("custom_greeting", sa.Text),
        sa.Column("ai_persona_name", sa.String(100), server_default="Your assistant"),
        sa.Column("google_calendar_token", postgresql.JSONB),
        sa.Column("google_calendar_id", sa.String(255)),
        sa.Column("google_place_id", sa.String(100)),
        sa.Column("setup_complete", sa.Boolean, server_default="false"),
        sa.Column("setup_step", sa.Integer, server_default="0"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("paused", sa.Boolean, server_default="false"),
        sa.Column("consecutive_quiet_weeks", sa.Integer, server_default="0"),
        sa.Column("last_owner_message", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("stripe_customer_id", sa.String(100), unique=True, nullable=False),
        sa.Column("stripe_subscription_id", sa.String(100), unique=True),
        sa.Column("status", sa.String(50), server_default="trial"),
        sa.Column("plan", sa.String(20), server_default="starter"),
        sa.Column("annual", sa.Boolean, server_default="false"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("sent_notifications", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "enquiries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("source", sa.String(50), server_default="whatsapp"),
        sa.Column("first_message", sa.Text),
        sa.Column("reply_sent", sa.Boolean, server_default="false"),
        sa.Column("seconds_to_reply", sa.Integer),
        sa.Column("call_sid", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("messages", postgresql.JSONB, server_default="[]"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("customer_phone", sa.String(20)),
        sa.Column("service_type", sa.String(255)),
        sa.Column("preferred_date", sa.String(100)),
        sa.Column("preferred_time", sa.String(100)),
        sa.Column("location", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("reminder_sent", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "owner_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("command", sa.String(50), nullable=False),
        sa.Column("response", sa.Text),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "daily_analytics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("enquiries_count", sa.Integer, server_default="0"),
        sa.Column("conversations_count", sa.Integer, server_default="0"),
        sa.Column("bookings_count", sa.Integer, server_default="0"),
        sa.Column("avg_reply_seconds", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("business_id", "date", name="uq_daily_analytics_business_date"),
    )

    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="CASCADE")),
        sa.Column("customer_phone", sa.String(20), nullable=False),
        sa.Column("consent_type", sa.String(50), nullable=False),
        sa.Column("given_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(45)),
        sa.UniqueConstraint("business_id", "customer_phone", "consent_type", name="uq_consent_record"),
    )

    op.create_table(
        "referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referrer_business_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("referred_email", sa.String(255)),
        sa.Column("referral_code", sa.String(20), unique=True, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("free_months_earned", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("referral_code", sa.String(20), unique=True, nullable=False),
        sa.Column("commission_per_customer", sa.Numeric(10, 2), server_default="10.00"),
        sa.Column("customers_referred", sa.Integer, server_default="0"),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "review_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bookings.id", ondelete="CASCADE")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("review_queue")
    op.drop_table("partners")
    op.drop_table("referrals")
    op.drop_table("consent_records")
    op.drop_table("daily_analytics")
    op.drop_table("owner_commands")
    op.drop_table("bookings")
    op.drop_table("conversations")
    op.drop_table("enquiries")
    op.drop_table("subscriptions")
    op.drop_table("businesses")
