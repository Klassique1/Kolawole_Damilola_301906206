-- Portfolio 2 | Drop optimisation indexes to capture clean baseline execution plans
-- Case Study: NovaPay Fintech Ltd

DROP INDEX IF EXISTS core.idx_ledger_account_posted_desc;
DROP INDEX IF EXISTS core.idx_txn_non_completed_recent;
DROP INDEX IF EXISTS core.idx_txn_status_created_cover;
DROP INDEX IF EXISTS core.idx_customers_lower_email;
DROP INDEX IF EXISTS core.idx_accounts_customer_id;
