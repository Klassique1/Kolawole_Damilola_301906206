-- Portfolio 3 | Standalone SQL Demonstration: COMMIT, SAVEPOINT & ROLLBACK
-- Case Study: NovaPay Fintech Ltd

-- Example 1: Atomic P2P Transfer with COMMIT
-- Debits Adaeze (3010000001) and Credits Tunde (3010000002) for 5,000.00 NGN
BEGIN;

DO $$
DECLARE
    v_src_id     UUID;
    v_dst_id     UUID;
    v_src_bal    NUMERIC(19, 4);
    v_dst_bal    NUMERIC(19, 4);
    v_amount     NUMERIC(19, 4) := 5000.0000;
    v_txn_id     UUID := gen_random_uuid();
    v_ref        TEXT := 'NP-P3-COMMIT-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');
BEGIN
    -- Deterministic ordered locking prevents deadlocks across concurrent sessions
    SELECT account_id INTO v_src_id FROM core.accounts WHERE account_number = '3010000001';
    SELECT account_id INTO v_dst_id FROM core.accounts WHERE account_number = '3010000002';

    PERFORM 1 FROM core.accounts
    WHERE account_id IN (v_src_id, v_dst_id)
    ORDER BY account_id ASC
    FOR UPDATE;

    SELECT balance INTO v_src_bal FROM core.accounts WHERE account_id = v_src_id;
    SELECT balance INTO v_dst_bal FROM core.accounts WHERE account_id = v_dst_id;

    IF v_src_bal < v_amount THEN
        RAISE EXCEPTION 'Insufficient balance on source wallet (%)', v_src_bal;
    END IF;

    UPDATE core.accounts
    SET balance = balance - v_amount,
        available_balance = available_balance - v_amount,
        version = version + 1
    WHERE account_id = v_src_id;

    UPDATE core.accounts
    SET balance = balance + v_amount,
        available_balance = available_balance + v_amount,
        version = version + 1
    WHERE account_id = v_dst_id;

    INSERT INTO core.transactions (
        transaction_id, reference_code, idempotency_key, transaction_type,
        source_account_id, destination_account_id, currency_code, amount,
        status, narration, completed_at
    ) VALUES (
        v_txn_id, v_ref, 'idem-' || v_ref, 'TRANSFER',
        v_src_id, v_dst_id, 'NGN', v_amount,
        'COMPLETED', 'Portfolio 3 atomic COMMIT transfer', now()
    );

    INSERT INTO core.ledger_entries (transaction_id, account_id, direction, amount, balance_after, narration)
    VALUES
        (v_txn_id, v_src_id, 'DEBIT',  v_amount, v_src_bal - v_amount, 'Atomic debit'),
        (v_txn_id, v_dst_id, 'CREDIT', v_amount, v_dst_bal + v_amount, 'Atomic credit');
END
$$;

COMMIT;


-- Example 2: Failed Transfer with ROLLBACK (Atomicity Guarantee)
-- Demonstrates that debiting below zero or rolling back mid-transaction leaves zero partial changes.
BEGIN;

UPDATE core.accounts
SET balance = balance + 25000.0000,
    available_balance = available_balance + 25000.0000
WHERE account_number = '3010000002';

SAVEPOINT sp_after_credit;

-- Attempting to debit Amina (3010000003, balance = 0) would violate accounts_check (balance >= 0).
-- Application catches the insufficient balance condition and rolls back the entire unit of work:
ROLLBACK TO SAVEPOINT sp_after_credit;
ROLLBACK;
