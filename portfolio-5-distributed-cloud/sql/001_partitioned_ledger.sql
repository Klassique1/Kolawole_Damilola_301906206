-- Portfolio 5 | Declarative Monthly Range Partitioning for High-Volume Ledger
-- Case Study: NovaPay Fintech Ltd

CREATE TABLE IF NOT EXISTS core.ledger_entries_partitioned (
    entry_id        BIGINT NOT NULL,
    transaction_id  UUID NOT NULL REFERENCES core.transactions (transaction_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    account_id      UUID NOT NULL REFERENCES core.accounts (account_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    direction       core.ledger_direction_enum NOT NULL,
    amount          NUMERIC(19, 4) NOT NULL CHECK (amount > 0),
    balance_after   NUMERIC(19, 4) NOT NULL,
    narration       VARCHAR(255) NOT NULL,
    posted_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (entry_id, posted_at)
) PARTITION BY RANGE (posted_at);

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_05
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-05-01 00:00:00+00') TO ('2026-06-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_06
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_07
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_08
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_09
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_10
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_11
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_2026_12
    PARTITION OF core.ledger_entries_partitioned
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS core.ledger_entries_p_default
    PARTITION OF core.ledger_entries_partitioned DEFAULT;

CREATE INDEX IF NOT EXISTS idx_part_ledger_acct_posted
    ON core.ledger_entries_partitioned (account_id, posted_at DESC, entry_id DESC)
    INCLUDE (direction, amount, balance_after);

INSERT INTO core.ledger_entries_partitioned (
    entry_id, transaction_id, account_id, direction,
    amount, balance_after, narration, posted_at
)
SELECT
    entry_id, transaction_id, account_id, direction,
    amount, balance_after, narration, posted_at
FROM core.ledger_entries
ON CONFLICT (entry_id, posted_at) DO NOTHING;

ANALYZE core.ledger_entries_partitioned;
