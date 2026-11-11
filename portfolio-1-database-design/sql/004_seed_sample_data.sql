-- Portfolio 1 | Migration 004: Reference & Verification Sample Seed Data
-- Case Study: NovaPay Fintech Ltd

INSERT INTO core.currencies (currency_code, currency_name, minor_unit, is_active) VALUES
    ('NGN', 'Nigerian Naira', 2, TRUE),
    ('USD', 'US Dollar', 2, TRUE),
    ('GBP', 'British Pound Sterling', 2, TRUE)
ON CONFLICT (currency_code) DO NOTHING;

INSERT INTO core.kyc_tiers (tier_code, tier_name, single_txn_limit, daily_txn_limit, max_wallet_balance, requires_bvn_nin) VALUES
    ('TIER_1', 'Basic Wallet (Phone Verified)',       50000.0000,   300000.0000,   500000.0000, FALSE),
    ('TIER_2', 'Verified Individual (BVN/NIN)',      500000.0000,  2000000.0000,  5000000.0000, TRUE),
    ('TIER_3', 'Premium / Merchant (Full KYC)',    10000000.0000, 50000000.0000,          NULL, TRUE)
ON CONFLICT (tier_code) DO NOTHING;

INSERT INTO core.account_types (account_type_code, display_name, is_customer_facing, allow_negative_balance, monthly_fee_amount) VALUES
    ('SAVINGS_WALLET',   'Customer Savings Wallet',        TRUE,  FALSE, 0.0000),
    ('CURRENT_WALLET',   'Customer Current / Business',    TRUE,  FALSE, 500.0000),
    ('SETTLEMENT_POOL',  'Internal Clearing & Settlement', FALSE, FALSE, 0.0000),
    ('FEE_REVENUE',      'Platform Fee Revenue Account',   FALSE, FALSE, 0.0000),
    ('EXTERNAL_CONTRA',  'External Banking Rail Contra',   FALSE, TRUE,  0.0000)
ON CONFLICT (account_type_code) DO NOTHING;

-- Deterministic seed UUIDs for Portfolio 1 demonstration & verification
DO $$
DECLARE
    v_cust_ada    UUID := '11111111-1111-4111-8111-111111111101';
    v_cust_tunde  UUID := '11111111-1111-4111-8111-111111111102';
    v_cust_amina  UUID := '11111111-1111-4111-8111-111111111103';

    v_acct_contra UUID := '22222222-2222-4222-8222-222222222000';
    v_acct_pool   UUID := '22222222-2222-4222-8222-222222222200';
    v_acct_ada    UUID := '22222222-2222-4222-8222-222222222201';
    v_acct_tunde  UUID := '22222222-2222-4222-8222-222222222202';
    v_acct_amina  UUID := '22222222-2222-4222-8222-222222222203';

    v_txn_pool    UUID := '33333333-3333-4333-8333-333333333300';
    v_txn_dep1    UUID := '33333333-3333-4333-8333-333333333301';
    v_txn_xfer1   UUID := '33333333-3333-4333-8333-333333333302';
    v_txn_xfer2   UUID := '33333333-3333-4333-8333-333333333303';
    v_txn_rev2    UUID := '33333333-3333-4333-8333-333333333304';
BEGIN
    IF EXISTS (SELECT 1 FROM core.customers WHERE customer_id = v_cust_ada) THEN
        RETURN;
    END IF;

    INSERT INTO core.customers (customer_id, full_name, email, phone_number, kyc_tier_code, status) VALUES
        (v_cust_ada,   'Adaeze Okafor', 'adaeze.okafor@novapay-demo.ng', '+2348011112201', 'TIER_2', 'ACTIVE'),
        (v_cust_tunde, 'Tunde Balogun', 'tunde.balogun@novapay-demo.ng', '+2348011112202', 'TIER_3', 'ACTIVE'),
        (v_cust_amina, 'Amina Yusuf',   'amina.yusuf@novapay-demo.ng',   '+2348011112203', 'TIER_1', 'ACTIVE');

    -- System contra/clearing accounts + customer wallets (closed-loop sum = 0.0000)
    INSERT INTO core.accounts (account_id, account_number, customer_id, account_type_code, currency_code, balance, available_balance, version) VALUES
        (v_acct_contra, '9000000000', NULL,         'EXTERNAL_CONTRA', 'NGN', -10000000.0000, -10000000.0000, 1),
        (v_acct_pool,   '9000000001', NULL,         'SETTLEMENT_POOL', 'NGN',   9500000.0000,   9500000.0000, 1),
        (v_acct_ada,    '3010000001', v_cust_ada,   'SAVINGS_WALLET',  'NGN',    350000.0000,    350000.0000, 2),
        (v_acct_tunde,  '3010000002', v_cust_tunde, 'CURRENT_WALLET',  'NGN',    150000.0000,    150000.0000, 1),
        (v_acct_amina,  '3010000003', v_cust_amina, 'SAVINGS_WALLET',  'NGN',         0.0000,         0.0000, 2);

    -- Initial settlement float capitalisation (balanced against External Banking Rail Contra)
    INSERT INTO core.transactions (transaction_id, reference_code, idempotency_key, transaction_type, source_account_id, destination_account_id, currency_code, amount, status, narration, completed_at) VALUES
        (v_txn_pool, 'NP-INIT-0001', 'idem-init-0001', 'DEPOSIT', v_acct_contra, v_acct_pool, 'NGN', 10000000.0000, 'COMPLETED', 'Initial clearing pool capitalisation', now() - INTERVAL '3 days');

    INSERT INTO core.ledger_entries (transaction_id, account_id, direction, amount, balance_after, narration, posted_at) VALUES
        (v_txn_pool, v_acct_contra, 'DEBIT',  10000000.0000, -10000000.0000, 'External rail funding to clearing pool', now() - INTERVAL '3 days'),
        (v_txn_pool, v_acct_pool,   'CREDIT', 10000000.0000,  10000000.0000, 'Clearing pool opening float',            now() - INTERVAL '3 days');

    -- Adaeze funds wallet from external bank clearing pool (500,000 NGN)
    INSERT INTO core.transactions (transaction_id, reference_code, idempotency_key, transaction_type, source_account_id, destination_account_id, currency_code, amount, status, narration, initiated_by_customer_id, completed_at) VALUES
        (v_txn_dep1, 'NP-TXN-1001', 'idem-dep-1001', 'TRANSFER', v_acct_pool, v_acct_ada, 'NGN', 500000.0000, 'COMPLETED', 'Inward bank deposit to Adaeze wallet', v_cust_ada, now() - INTERVAL '2 days');

    INSERT INTO core.ledger_entries (transaction_id, account_id, direction, amount, balance_after, narration, posted_at) VALUES
        (v_txn_dep1, v_acct_pool, 'DEBIT',  500000.0000, 9500000.0000, 'Outward float funding to 3010000001', now() - INTERVAL '2 days'),
        (v_txn_dep1, v_acct_ada,  'CREDIT', 500000.0000,  500000.0000, 'Wallet funding via clearing pool',    now() - INTERVAL '2 days');

    -- Adaeze transfers 150,000 NGN to Tunde
    INSERT INTO core.transactions (transaction_id, reference_code, idempotency_key, transaction_type, source_account_id, destination_account_id, currency_code, amount, status, narration, initiated_by_customer_id, completed_at) VALUES
        (v_txn_xfer1, 'NP-TXN-1002', 'idem-xfer-1002', 'TRANSFER', v_acct_ada, v_acct_tunde, 'NGN', 150000.0000, 'COMPLETED', 'Invoice settlement to Tunde', v_cust_ada, now() - INTERVAL '1 day');

    INSERT INTO core.ledger_entries (transaction_id, account_id, direction, amount, balance_after, narration, posted_at) VALUES
        (v_txn_xfer1, v_acct_ada,   'DEBIT',  150000.0000, 350000.0000, 'P2P transfer to 3010000002',   now() - INTERVAL '1 day'),
        (v_txn_xfer1, v_acct_tunde, 'CREDIT', 150000.0000, 150000.0000, 'P2P transfer from 3010000001', now() - INTERVAL '1 day');

    -- Adaeze transfers 25,000 NGN to Amina, later marked REVERSED by reversal transaction
    INSERT INTO core.transactions (transaction_id, reference_code, idempotency_key, transaction_type, source_account_id, destination_account_id, currency_code, amount, status, narration, initiated_by_customer_id, completed_at) VALUES
        (v_txn_xfer2, 'NP-TXN-1003', 'idem-xfer-1003', 'TRANSFER', v_acct_ada, v_acct_amina, 'NGN', 25000.0000, 'REVERSED', 'Disputed payment (later reversed)', v_cust_ada, now() - INTERVAL '12 hours');

    INSERT INTO core.ledger_entries (transaction_id, account_id, direction, amount, balance_after, narration, posted_at) VALUES
        (v_txn_xfer2, v_acct_ada,   'DEBIT',  25000.0000, 325000.0000, 'Transfer to 3010000003',   now() - INTERVAL '12 hours'),
        (v_txn_xfer2, v_acct_amina, 'CREDIT', 25000.0000,  25000.0000, 'Transfer from 3010000001', now() - INTERVAL '12 hours');

    INSERT INTO core.transactions (transaction_id, reference_code, idempotency_key, transaction_type, source_account_id, destination_account_id, currency_code, amount, status, reversed_transaction_id, narration, completed_at) VALUES
        (v_txn_rev2, 'NP-REV-1003', 'idem-rev-1003', 'REVERSAL', v_acct_amina, v_acct_ada, 'NGN', 25000.0000, 'COMPLETED', v_txn_xfer2, 'Reversal of disputed NP-TXN-1003', now() - INTERVAL '6 hours');

    INSERT INTO core.ledger_entries (transaction_id, account_id, direction, amount, balance_after, narration, posted_at) VALUES
        (v_txn_rev2, v_acct_amina, 'DEBIT',  25000.0000,      0.0000, 'Reversal debit for NP-TXN-1003',  now() - INTERVAL '6 hours'),
        (v_txn_rev2, v_acct_ada,   'CREDIT', 25000.0000, 350000.0000, 'Reversal credit for NP-TXN-1003', now() - INTERVAL '6 hours');
END
$$;
