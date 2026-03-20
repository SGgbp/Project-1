-- SnapReply v2.0 — Initial Schema
-- Run on Supabase SQL Editor
-- Verify with: SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
-- Expected: 10 tables

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────
-- CORE TABLES
-- ─────────────────────────────────────────────

CREATE TABLE businesses (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email                   VARCHAR(255) UNIQUE NOT NULL,
    password_hash           VARCHAR(255) NOT NULL,
    owner_name              VARCHAR(255) NOT NULL,
    business_name           VARCHAR(255) NOT NULL,
    business_type           VARCHAR(100) NOT NULL,
    plan                    VARCHAR(20) DEFAULT 'starter',  -- starter | growth | pro
    owner_whatsapp          VARCHAR(20) NOT NULL,
    business_whatsapp       VARCHAR(20),
    snapreply_number        VARCHAR(20),
    twilio_number           VARCHAR(20),
    city                    VARCHAR(100),
    custom_greeting         TEXT,
    ai_persona_name         VARCHAR(100) DEFAULT 'Your assistant',
    google_calendar_token   JSONB,
    google_calendar_id      VARCHAR(255),
    google_place_id         VARCHAR(100),
    setup_complete          BOOLEAN DEFAULT false,
    setup_step              INT DEFAULT 0,
    active                  BOOLEAN DEFAULT true,
    paused                  BOOLEAN DEFAULT false,
    last_owner_message      TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscriptions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id             UUID REFERENCES businesses(id) ON DELETE CASCADE,
    stripe_customer_id      VARCHAR(100) UNIQUE NOT NULL,
    stripe_subscription_id  VARCHAR(100) UNIQUE,
    status                  VARCHAR(50) DEFAULT 'trial',  -- trial | active | cancelled | past_due
    plan                    VARCHAR(20) DEFAULT 'starter',
    annual                  BOOLEAN DEFAULT false,
    trial_ends_at           TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    cancelled_at            TIMESTAMPTZ,
    sent_notifications      JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE enquiries (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id         UUID REFERENCES businesses(id) ON DELETE CASCADE,
    customer_phone      VARCHAR(20) NOT NULL,
    customer_name       VARCHAR(255),
    source              VARCHAR(50) DEFAULT 'whatsapp',  -- whatsapp | missed_call | sms
    first_message       TEXT,
    reply_sent          BOOLEAN DEFAULT false,
    seconds_to_reply    INT,
    call_sid            VARCHAR(100),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID REFERENCES businesses(id) ON DELETE CASCADE,
    customer_phone  VARCHAR(20) NOT NULL,
    messages        JSONB DEFAULT '[]',
    status          VARCHAR(20) DEFAULT 'active',  -- active | ended | booked
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bookings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID REFERENCES businesses(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    customer_name   VARCHAR(255),
    customer_phone  VARCHAR(20),
    service_type    VARCHAR(255),
    preferred_date  VARCHAR(100),
    preferred_time  VARCHAR(100),
    location        TEXT,
    notes           TEXT,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending | confirmed | completed | no_show | cancelled
    reminder_sent   BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE owner_commands (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    command     VARCHAR(50) NOT NULL,
    response    TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE daily_analytics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id         UUID REFERENCES businesses(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    enquiries_count     INT DEFAULT 0,
    conversations_count INT DEFAULT 0,
    bookings_count      INT DEFAULT 0,
    avg_reply_seconds   INT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(business_id, date)
);

CREATE TABLE consent_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID REFERENCES businesses(id) ON DELETE CASCADE,
    customer_phone  VARCHAR(20) NOT NULL,
    consent_type    VARCHAR(50) NOT NULL,
    given_at        TIMESTAMPTZ DEFAULT NOW(),
    ip_address      VARCHAR(45),
    UNIQUE(business_id, customer_phone, consent_type)
);

-- ─────────────────────────────────────────────
-- GROWTH / PARTNER TABLES
-- ─────────────────────────────────────────────

CREATE TABLE referrals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referrer_business_id UUID REFERENCES businesses(id) ON DELETE SET NULL,
    referred_email      VARCHAR(255),
    referral_code       VARCHAR(20) UNIQUE NOT NULL,
    status              VARCHAR(20) DEFAULT 'pending',  -- pending | converted | rewarded
    free_months_earned  INT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE partners (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                        VARCHAR(255) NOT NULL,
    type                        VARCHAR(50) NOT NULL,  -- insurance_broker | association | coach | whitelabel
    contact_email               VARCHAR(255),
    referral_code               VARCHAR(20) UNIQUE NOT NULL,
    commission_per_customer     DECIMAL(10,2) DEFAULT 10.00,
    customers_referred          INT DEFAULT 0,
    active                      BOOLEAN DEFAULT true,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────

-- Businesses
CREATE INDEX idx_businesses_email ON businesses(email);
CREATE INDEX idx_businesses_owner_whatsapp ON businesses(owner_whatsapp);
CREATE INDEX idx_businesses_snapreply_number ON businesses(snapreply_number);
CREATE INDEX idx_businesses_twilio_number ON businesses(twilio_number);
CREATE INDEX idx_businesses_plan ON businesses(plan);
CREATE INDEX idx_businesses_active ON businesses(active);

-- Subscriptions
CREATE INDEX idx_subscriptions_business_id ON subscriptions(business_id);
CREATE INDEX idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_trial_ends ON subscriptions(trial_ends_at);

-- Enquiries
CREATE INDEX idx_enquiries_business_id ON enquiries(business_id);
CREATE INDEX idx_enquiries_customer_phone ON enquiries(customer_phone);
CREATE INDEX idx_enquiries_created_at ON enquiries(created_at);
CREATE INDEX idx_enquiries_call_sid ON enquiries(call_sid);

-- Conversations
CREATE INDEX idx_conversations_business_id ON conversations(business_id);
CREATE INDEX idx_conversations_customer_phone ON conversations(customer_phone);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at);
CREATE INDEX idx_conversations_business_customer ON conversations(business_id, customer_phone);
-- GIN index for JSONB message search
CREATE INDEX idx_conversations_messages_gin ON conversations USING GIN(messages);

-- Bookings
CREATE INDEX idx_bookings_business_id ON bookings(business_id);
CREATE INDEX idx_bookings_customer_phone ON bookings(customer_phone);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_preferred_date ON bookings(preferred_date);
CREATE INDEX idx_bookings_reminder_sent ON bookings(reminder_sent);

-- Referrals
CREATE INDEX idx_referrals_referrer ON referrals(referrer_business_id);
CREATE INDEX idx_referrals_code ON referrals(referral_code);
CREATE INDEX idx_referrals_status ON referrals(status);

-- Partners
CREATE INDEX idx_partners_code ON partners(referral_code);
CREATE INDEX idx_partners_active ON partners(active);

-- Analytics
CREATE INDEX idx_analytics_business_date ON daily_analytics(business_id, date);

-- ─────────────────────────────────────────────
-- AUTO-UPDATE TRIGGERS
-- ─────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_businesses_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_bookings_updated_at
    BEFORE UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────
-- VERIFY (run after migration)
-- ─────────────────────────────────────────────
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' ORDER BY table_name;
-- Expected 10 tables:
--   bookings, businesses, consent_records, conversations,
--   daily_analytics, enquiries, owner_commands, partners,
--   referrals, subscriptions
