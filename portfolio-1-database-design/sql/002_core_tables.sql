-- Portfolio 1 | Migration 002: Core Transactional & Ledger Tables (3NF/BCNF)
-- Case Study: NovaPay Fintech Ltd

-- 1. Customers
CREATE TABLE IF NOT EXISTS core.customers (
    customer_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(120) NOT NULL CHECK (length(trim(full_name)) >= 2),
    email           VARCHAR(255) NOT NULL UNIQUE CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    phone_number    VARCHAR(20)  NOT NULL UNIQUE CHECK (phone_number ~ '^\+[1-9][0-9]{7,14}$'),
    kyc_tier_code   VARCHAR(16)  NOT NULL REFERENCES core.kyc_tiers (tier_code) ON UPDATE RESTRICT ON DELETE RESTRICT,
    status          core.customer_status_enum NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Financial Accounts (Customer Wallets + Internal Clearing/Fee Accounts)
CREATE TABLE IF NOT EXISTS core.accounts (
    account_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_number      CHAR(10) NOT NULL UNIQUE CHECK (account_number ~ '^[0-9]{10}$'),
    customer_id         UUID REFERENCES core.customers (customer_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    account_type_code   VARCHAR(24) NOT NULL REFERENCES core.account_types (account_type_code) ON UPDATE RESTRICT ON DELETE RESTRICT,
    currency_code       CHAR(3) NOT NULL REFERENCES core.currencies (currency_code) ON UPDATE RESTRICT ON DELETE RESTRICT,
    balance             NUMERIC(19, 4) NOT NULL DEFAULT 0.0000 CHECK (balance >= 0 OR account_type_code = 'EXTERNAL_CONTRA'),
    available_balance   NUMERIC(19, 4) NOT NULL DEFAULT 0.0000 CHECK ((available_balance >= 0 OR account_type_code = 'EXTERNAL_CONTRA') AND available_balance <= balance),
    status              core.account_status_enum NOT NULL DEFAULT 'ACTIVE',
    version             BIGINT NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Financial Transactions (Transfers, Deposits, Withdrawals, Reversals)
CREATE TABLE IF NOT EXISTS core.transactions (
    transaction_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_code          VARCHAR(40) NOT NULL UNIQUE,
    idempotency_key         VARCHAR(64) NOT NULL UNIQUE,
    transaction_type        core.transaction_type_enum NOT NULL,
    source_account_id       UUID REFERENCES core.accounts (account_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    destination_account_id  UUID REFERENCES core.accounts (account_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    currency_code           CHAR(3) NOT NULL REFERENCES core.currencies (currency_code) ON UPDATE RESTRICT ON DELETE RESTRICT,
    amount                  NUMERIC(19, 4) NOT NULL CHECK (amount > 0),
    fee_amount              NUMERIC(19, 4) NOT NULL DEFAULT 0.0000 CHECK (fee_amount >= 0),
    status                  core.transaction_status_enum NOT NULL DEFAULT 'PENDING',
    reversed_transaction_id UUID UNIQUE REFERENCES core.transactions (transaction_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    narration               VARCHAR(255) NOT NULL,
    failure_reason          VARCHAR(255),
    initiated_by_customer_id UUID REFERENCES core.customers (customer_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at            TIMESTAMPTZ,

    CONSTRAINT chk_txn_accounts_by_type CHECK (
        (transaction_type = 'TRANSFER'   AND source_account_id IS NOT NULL AND destination_account_id IS NOT NULL AND source_account_id <> destination_account_id)
        OR (transaction_type = 'DEPOSIT'    AND destination_account_id IS NOT NULL AND (source_account_id IS NULL OR source_account_id <> destination_account_id))
        OR (transaction_type = 'WITHDRAWAL' AND source_account_id IS NOT NULL AND (destination_account_id IS NULL OR destination_account_id <> source_account_id))
        OR (transaction_type = 'REVERSAL'   AND source_account_id IS NOT NULL AND destination_account_id IS NOT NULL AND reversed_transaction_id IS NOT NULL)
        OR (transaction_type = 'FEE'        AND source_account_id IS NOT NULL AND destination_account_id IS NOT NULL)
    ),
    CONSTRAINT chk_txn_completed_ts CHECK (
        (status = 'COMPLETED' AND completed_at IS NOT NULL)
        OR (status <> 'COMPLETED')
    )
);

-- 4. Immutable Double-Entry Ledger Entries
CREATE TABLE IF NOT EXISTS core.ledger_entries (
    entry_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  UUID NOT NULL REFERENCES core.transactions (transaction_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    account_id      UUID NOT NULL REFERENCES core.accounts (account_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    direction       core.ledger_direction_enum NOT NULL,
    amount          NUMERIC(19, 4) NOT NULL CHECK (amount > 0),
    balance_after   NUMERIC(19, 4) NOT NULL,
    narration       VARCHAR(255) NOT NULL,
    posted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Prevent duplicate debit or duplicate credit for the same account within one transaction
    CONSTRAINT uq_ledger_txn_acct_dir UNIQUE (transaction_id, account_id, direction)
);

-- 5. Compliance & Audit Log (Relational audit trail for account/KYC mutations)
CREATE TABLE IF NOT EXISTS core.audit_logs (
    audit_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_name     VARCHAR(64) NOT NULL,
    entity_id       TEXT NOT NULL,
    action          VARCHAR(32) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'STATUS_CHANGE', 'REVERSAL')),
    old_state       JSONB,
    new_state       JSONB NOT NULL,
    actor           VARCHAR(64) NOT NULL DEFAULT current_user,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
