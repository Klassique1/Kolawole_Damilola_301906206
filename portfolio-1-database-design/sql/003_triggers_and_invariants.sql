-- Portfolio 1 | Migration 003: Triggers, Immutability Guards & Reconciliation Views
-- Case Study: NovaPay Fintech Ltd

-- 1. Automatic updated_at maintenance
CREATE OR REPLACE FUNCTION core.fn_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_customers_updated_at ON core.customers;
CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON core.customers
FOR EACH ROW
EXECUTE FUNCTION core.fn_set_updated_at();

DROP TRIGGER IF EXISTS trg_accounts_updated_at ON core.accounts;
CREATE TRIGGER trg_accounts_updated_at
BEFORE UPDATE ON core.accounts
FOR EACH ROW
EXECUTE FUNCTION core.fn_set_updated_at();

-- 2. Enforce append-only immutability on ledger_entries (financial audit invariant)
CREATE OR REPLACE FUNCTION core.fn_prevent_ledger_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'core.ledger_entries is append-only; % operations are prohibited', TG_OP
        USING ERRCODE = '42501';
END;
$$;

DROP TRIGGER IF EXISTS trg_ledger_immutable ON core.ledger_entries;
CREATE TRIGGER trg_ledger_immutable
BEFORE UPDATE OR DELETE ON core.ledger_entries
FOR EACH ROW
EXECUTE FUNCTION core.fn_prevent_ledger_mutation();

-- 3. Automatic customer KYC tier audit trail
CREATE OR REPLACE FUNCTION core.fn_audit_customer_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO core.audit_logs (entity_name, entity_id, action, old_state, new_state)
        VALUES ('customers', NEW.customer_id::text, 'INSERT', NULL, to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.kyc_tier_code IS DISTINCT FROM NEW.kyc_tier_code
           OR OLD.status IS DISTINCT FROM NEW.status THEN
            INSERT INTO core.audit_logs (entity_name, entity_id, action, old_state, new_state)
            VALUES ('customers', NEW.customer_id::text, 'STATUS_CHANGE', to_jsonb(OLD), to_jsonb(NEW));
        END IF;
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_customers_audit ON core.customers;
CREATE TRIGGER trg_customers_audit
AFTER INSERT OR UPDATE ON core.customers
FOR EACH ROW
EXECUTE FUNCTION core.fn_audit_customer_changes();

-- 4. Trial Balance View (verifies Debits = Credits across every transaction)
CREATE OR REPLACE VIEW core.v_transaction_trial_balance AS
SELECT
    t.transaction_id,
    t.reference_code,
    t.transaction_type,
    t.status,
    COALESCE(SUM(CASE WHEN l.direction = 'DEBIT'  THEN l.amount ELSE 0 END), 0) AS total_debits,
    COALESCE(SUM(CASE WHEN l.direction = 'CREDIT' THEN l.amount ELSE 0 END), 0) AS total_credits,
    (
        COALESCE(SUM(CASE WHEN l.direction = 'DEBIT'  THEN l.amount ELSE 0 END), 0)
        - COALESCE(SUM(CASE WHEN l.direction = 'CREDIT' THEN l.amount ELSE 0 END), 0)
    ) AS net_imbalance
FROM core.transactions t
LEFT JOIN core.ledger_entries l ON l.transaction_id = t.transaction_id
GROUP BY t.transaction_id, t.reference_code, t.transaction_type, t.status;

-- 5. Account Ledger Reconciliation View (compares stored balance vs. posted journal sum)
CREATE OR REPLACE VIEW core.v_account_reconciliation AS
SELECT
    a.account_id,
    a.account_number,
    a.account_type_code,
    a.balance AS stored_balance,
    COALESCE(
        SUM(
            CASE
                WHEN l.direction = 'CREDIT' THEN l.amount
                WHEN l.direction = 'DEBIT'  THEN -l.amount
                ELSE 0
            END
        ),
        0.0000
    ) AS ledger_computed_balance,
    (
        a.balance - COALESCE(
            SUM(
                CASE
                    WHEN l.direction = 'CREDIT' THEN l.amount
                    WHEN l.direction = 'DEBIT'  THEN -l.amount
                    ELSE 0
                END
            ),
            0.0000
        )
    ) AS variance
FROM core.accounts a
LEFT JOIN core.ledger_entries l ON l.account_id = a.account_id
GROUP BY a.account_id, a.account_number, a.account_type_code, a.balance;
