-- Portfolio 2 | Step 3: Production Indexing Strategy
-- Case Study: NovaPay Fintech Ltd

-- 1. Covering Composite Index for paginated wallet statements (Index-Only Scan + zero sort)
CREATE INDEX IF NOT EXISTS idx_ledger_account_posted_desc
    ON core.ledger_entries (account_id, posted_at DESC, entry_id DESC)
    INCLUDE (direction, amount, balance_after, narration);

-- 2. Partial Composite Index for high-value non-completed exception monitoring
--    Indexes only ~5% of rows (FAILED/PENDING), minimizing write amplification and index size
CREATE INDEX IF NOT EXISTS idx_txn_non_completed_recent
    ON core.transactions (created_at DESC, amount)
    WHERE status IN ('FAILED', 'PENDING');

-- 3. Covering Index for daily completed settlement & revenue summary aggregations
CREATE INDEX IF NOT EXISTS idx_txn_status_created_cover
    ON core.transactions (status, created_at)
    INCLUDE (transaction_type, amount, fee_amount);

-- 4. Functional Index for case-insensitive customer login/KYC email lookup
CREATE INDEX IF NOT EXISTS idx_customers_lower_email
    ON core.customers (lower(email));

-- 5. Foreign-key B-Tree Index on accounts(customer_id) (PostgreSQL does not auto-index FKs)
CREATE INDEX IF NOT EXISTS idx_accounts_customer_id
    ON core.accounts (customer_id)
    WHERE customer_id IS NOT NULL;
