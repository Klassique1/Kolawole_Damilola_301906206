-- Portfolio 1 | Migration 001: Schema, Extensions, Custom Types & Reference Tables
-- Case Study: NovaPay Fintech Ltd

CREATE SCHEMA IF NOT EXISTS core;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'customer_status_enum' AND n.nspname = 'core'
    ) THEN
        CREATE TYPE core.customer_status_enum AS ENUM ('ACTIVE', 'SUSPENDED', 'CLOSED');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'account_status_enum' AND n.nspname = 'core'
    ) THEN
        CREATE TYPE core.account_status_enum AS ENUM ('ACTIVE', 'FROZEN', 'CLOSED');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'transaction_type_enum' AND n.nspname = 'core'
    ) THEN
        CREATE TYPE core.transaction_type_enum AS ENUM (
            'TRANSFER',
            'DEPOSIT',
            'WITHDRAWAL',
            'REVERSAL',
            'FEE'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'transaction_status_enum' AND n.nspname = 'core'
    ) THEN
        CREATE TYPE core.transaction_status_enum AS ENUM (
            'PENDING',
            'COMPLETED',
            'FAILED',
            'REVERSED'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'ledger_direction_enum' AND n.nspname = 'core'
    ) THEN
        CREATE TYPE core.ledger_direction_enum AS ENUM ('DEBIT', 'CREDIT');
    END IF;
END
$$;

-- Reference Table: ISO 4217 Currencies
CREATE TABLE IF NOT EXISTS core.currencies (
    currency_code   CHAR(3) PRIMARY KEY CHECK (currency_code ~ '^[A-Z]{3}$'),
    currency_name   VARCHAR(64) NOT NULL,
    minor_unit      SMALLINT NOT NULL DEFAULT 2 CHECK (minor_unit BETWEEN 0 AND 4),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Reference Table: Tiered KYC Limits (Normalised out of customers to achieve 3NF)
CREATE TABLE IF NOT EXISTS core.kyc_tiers (
    tier_code               VARCHAR(16) PRIMARY KEY,
    tier_name               VARCHAR(64) NOT NULL UNIQUE,
    single_txn_limit        NUMERIC(19, 4) NOT NULL CHECK (single_txn_limit > 0),
    daily_txn_limit         NUMERIC(19, 4) NOT NULL CHECK (daily_txn_limit >= single_txn_limit),
    max_wallet_balance      NUMERIC(19, 4) CHECK (max_wallet_balance IS NULL OR max_wallet_balance >= daily_txn_limit),
    requires_bvn_nin        BOOLEAN NOT NULL DEFAULT TRUE
);

-- Reference Table: Account Product Types
CREATE TABLE IF NOT EXISTS core.account_types (
    account_type_code       VARCHAR(24) PRIMARY KEY,
    display_name            VARCHAR(64) NOT NULL UNIQUE,
    is_customer_facing      BOOLEAN NOT NULL DEFAULT TRUE,
    allow_negative_balance  BOOLEAN NOT NULL DEFAULT FALSE,
    monthly_fee_amount      NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (monthly_fee_amount >= 0)
);
