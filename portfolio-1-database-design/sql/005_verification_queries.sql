-- Portfolio 1 | Schema & Integrity Verification Queries
-- Case Study: NovaPay Fintech Ltd

-- 1. List all tables in core schema with row counts
SELECT
    schemaname,
    relname AS table_name,
    n_live_tup AS estimated_rows
FROM pg_stat_user_tables
WHERE schemaname = 'core'
ORDER BY relname;

-- 2. Verify double-entry trial balance (every transfer/reversal must have net_imbalance = 0)
SELECT
    reference_code,
    transaction_type,
    status,
    total_debits,
    total_credits,
    net_imbalance
FROM core.v_transaction_trial_balance
ORDER BY reference_code;

-- 3. Verify stored account balances match computed sum of immutable ledger entries
SELECT
    account_number,
    account_type_code,
    stored_balance,
    ledger_computed_balance,
    variance
FROM core.v_account_reconciliation
ORDER BY account_number;

-- 4. Inspect enforced integrity constraints (PK, FK, UNIQUE, CHECK)
SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'core'
ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name;
