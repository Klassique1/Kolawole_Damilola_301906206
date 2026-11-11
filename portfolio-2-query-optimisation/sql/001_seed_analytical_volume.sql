-- Portfolio 2 | Step 1: High-Volume Analytical & Operational Workload Seed
-- Case Study: NovaPay Fintech Ltd
-- Generates 2,000 synthetic customers/wallets + 100,000 transactions + ~196,000 balanced ledger entries.

DO $$
DECLARE
    v_existing_txns BIGINT;
    v_acct_contra   UUID := '22222222-2222-4222-8222-222222222000';
    v_initial_float NUMERIC(19, 4) := 5000000.0000;
BEGIN
    SELECT COUNT(*) INTO v_existing_txns FROM core.transactions;
    IF v_existing_txns >= 50000 THEN
        RAISE NOTICE 'Analytical volume already seeded (% transactions present). Skipping.', v_existing_txns;
        RETURN;
    END IF;

    -- 1. Create 2,000 synthetic customers
    INSERT INTO core.customers (full_name, email, phone_number, kyc_tier_code, status, created_at)
    SELECT
        'Benchmark Customer ' || LPAD(g::text, 4, '0'),
        'bench_cust_' || LPAD(g::text, 4, '0') || '@novapay-demo.ng',
        '+234809' || LPAD(g::text, 7, '0'),
        CASE
            WHEN g % 10 = 0 THEN 'TIER_3'
            WHEN g % 3  = 0 THEN 'TIER_2'
            ELSE 'TIER_1'
        END,
        'ACTIVE',
        now() - ((180 - (g % 180)) || ' days')::interval
    FROM generate_series(1, 2000) AS g
    ON CONFLICT (email) DO NOTHING;

    -- 2. Create 2,000 synthetic wallets (4000000001 .. 4000002000)
    INSERT INTO core.accounts (account_number, customer_id, account_type_code, currency_code, balance, available_balance, version, created_at)
    SELECT
        ('4000' || LPAD(g::text, 6, '0'))::char(10),
        c.customer_id,
        CASE WHEN g % 4 = 0 THEN 'CURRENT_WALLET' ELSE 'SAVINGS_WALLET' END,
        'NGN',
        0.0000,
        0.0000,
        1,
        c.created_at
    FROM generate_series(1, 2000) AS g
    JOIN core.customers c
      ON c.email = 'bench_cust_' || LPAD(g::text, 4, '0') || '@novapay-demo.ng'
    ON CONFLICT (account_number) DO NOTHING;

    -- Materialize ordered account array for fast deterministic pair lookups
    CREATE TEMP TABLE tmp_bench_wallets ON COMMIT DROP AS
    SELECT
        ROW_NUMBER() OVER (ORDER BY account_number)::int AS idx,
        account_id,
        customer_id,
        account_number
    FROM core.accounts
    WHERE account_number LIKE '4000%'
    ORDER BY account_number;

    -- 3. Insert 2,000 initial funding deposits (EXTERNAL_CONTRA -> wallet_i)
    INSERT INTO core.transactions (
        reference_code,
        idempotency_key,
        transaction_type,
        source_account_id,
        destination_account_id,
        currency_code,
        amount,
        fee_amount,
        status,
        narration,
        initiated_by_customer_id,
        created_at,
        completed_at
    )
    SELECT
        'NP-BDEP-' || LPAD(w.idx::text, 6, '0'),
        'idem-bdep-' || LPAD(w.idx::text, 6, '0'),
        'DEPOSIT',
        v_acct_contra,
        w.account_id,
        'NGN',
        v_initial_float,
        0.0000,
        'COMPLETED',
        'Benchmark opening wallet deposit',
        w.customer_id,
        now() - INTERVAL '180 days' + (w.idx || ' minutes')::interval,
        now() - INTERVAL '180 days' + (w.idx || ' minutes')::interval
    FROM tmp_bench_wallets w;

    -- 4. Insert 98,000 realistic P2P transfers spanning the last 180 days
    -- ~95% COMPLETED, ~3% FAILED, ~2% PENDING (realistic partial-index skew)
    INSERT INTO core.transactions (
        reference_code,
        idempotency_key,
        transaction_type,
        source_account_id,
        destination_account_id,
        currency_code,
        amount,
        fee_amount,
        status,
        narration,
        failure_reason,
        initiated_by_customer_id,
        created_at,
        completed_at
    )
    SELECT
        'NP-BTXN-' || LPAD(s::text, 6, '0'),
        'idem-btxn-' || LPAD(s::text, 6, '0'),
        'TRANSFER',
        src.account_id,
        dst.account_id,
        'NGN',
        (
            CASE
                WHEN s % 53 = 0 THEN 260000 + ((s % 20) * 10000)
                ELSE 500 + ((s % 45) * 100)
            END
        )::numeric(19, 4),
        10.0000,
        CASE
            WHEN s % 100 IN (95, 96, 97) THEN 'FAILED'::core.transaction_status_enum
            WHEN s % 100 IN (98, 99)     THEN 'PENDING'::core.transaction_status_enum
            ELSE 'COMPLETED'::core.transaction_status_enum
        END,
        'Benchmark P2P transfer #' || s,
        CASE
            WHEN s % 100 IN (95, 96, 97) THEN 'Upstream NIP switch timeout'
            ELSE NULL
        END,
        src.customer_id,
        now() - ((179.0 - (s::numeric / 98000.0 * 179.0)) || ' days')::interval,
        CASE
            WHEN s % 100 IN (95, 96, 97, 98, 99) THEN NULL
            ELSE now() - ((179.0 - (s::numeric / 98000.0 * 179.0)) || ' days')::interval + INTERVAL '2 seconds'
        END
    FROM generate_series(1, 98000) AS s
    JOIN tmp_bench_wallets src ON src.idx = ((s - 1) % 2000) + 1
    JOIN tmp_bench_wallets dst ON dst.idx = ((s - 1 + 1 + (s % 19)) % 2000) + 1;

    -- 5. Post immutable double-entry ledger lines for COMPLETED benchmark transactions
    CREATE TEMP TABLE tmp_new_postings ON COMMIT DROP AS
    SELECT
        t.transaction_id,
        t.source_account_id AS account_id,
        'DEBIT'::core.ledger_direction_enum AS direction,
        t.amount,
        t.narration,
        COALESCE(t.completed_at, t.created_at) AS posted_at
    FROM core.transactions t
    WHERE (t.reference_code LIKE 'NP-BDEP-%' OR t.reference_code LIKE 'NP-BTXN-%')
      AND t.status = 'COMPLETED'
    UNION ALL
    SELECT
        t.transaction_id,
        t.destination_account_id AS account_id,
        'CREDIT'::core.ledger_direction_enum AS direction,
        t.amount,
        t.narration,
        COALESCE(t.completed_at, t.created_at) AS posted_at
    FROM core.transactions t
    WHERE (t.reference_code LIKE 'NP-BDEP-%' OR t.reference_code LIKE 'NP-BTXN-%')
      AND t.status = 'COMPLETED';

    -- Compute exact running balance_after per account starting from existing account balance
    INSERT INTO core.ledger_entries (
        transaction_id,
        account_id,
        direction,
        amount,
        balance_after,
        narration,
        posted_at
    )
    SELECT
        p.transaction_id,
        p.account_id,
        p.direction,
        p.amount,
        a.balance + SUM(
            CASE WHEN p.direction = 'CREDIT' THEN p.amount ELSE -p.amount END
        ) OVER (
            PARTITION BY p.account_id
            ORDER BY p.posted_at, p.transaction_id, p.direction
        ) AS balance_after,
        p.narration,
        p.posted_at
    FROM tmp_new_postings p
    JOIN core.accounts a ON a.account_id = p.account_id;

    -- 6. Synchronize stored account balances for benchmark-seeded wallets
    UPDATE core.accounts a
    SET
        balance = rec.ledger_computed_balance,
        available_balance = rec.ledger_computed_balance,
        version = a.version + 1
    FROM (
        SELECT
            account_id,
            SUM(CASE WHEN direction = 'CREDIT' THEN amount ELSE -amount END) AS ledger_computed_balance
        FROM core.ledger_entries
        GROUP BY account_id
    ) rec
    WHERE a.account_id = rec.account_id
      AND EXISTS (SELECT 1 FROM tmp_new_postings tp WHERE tp.account_id = a.account_id)
      AND a.balance IS DISTINCT FROM rec.ledger_computed_balance;
END
$$;
