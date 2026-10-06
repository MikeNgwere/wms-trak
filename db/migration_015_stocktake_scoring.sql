-- Stocktake scoring, fraud flag, and responsibility snapshot (builds on migration_014).
ALTER TABLE stocktakes
    ADD COLUMN IF NOT EXISTS score          NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS flagged        BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS expected_count INT,
    ADD COLUMN IF NOT EXISTS present_count  INT,
    ADD COLUMN IF NOT EXISTS missing_count  INT,
    ADD COLUMN IF NOT EXISTS extra_count    INT;

ALTER TABLE stocktake_items
    ADD COLUMN IF NOT EXISTS officer_id    INT REFERENCES users(user_id),
    ADD COLUMN IF NOT EXISTS supervisor_id INT REFERENCES users(user_id),
    ADD COLUMN IF NOT EXISTS manager_id    INT REFERENCES users(user_id),
    ADD COLUMN IF NOT EXISTS category      VARCHAR(40);

-- Fill responsibility for any stocktake items created before this migration.
UPDATE stocktake_items i
SET officer_id = COALESCE(e.captured_by, e.officer_id)
FROM entries e
WHERE e.entry_id = i.entry_id AND i.officer_id IS NULL;

-- Score any stocktakes already closed.
UPDATE stocktakes s SET
    expected_count = c.exp, present_count = c.pres, missing_count = c.exp - c.pres,
    extra_count = c.ext,
    score = CASE WHEN c.exp + c.ext = 0 THEN NULL
                 ELSE ROUND(100.0 * c.pres / (c.exp + c.ext), 2) END
FROM (
    SELECT st.stocktake_id,
           (SELECT COUNT(*) FROM stocktake_items i WHERE i.stocktake_id = st.stocktake_id) AS exp,
           (SELECT COUNT(*) FROM stocktake_items i WHERE i.stocktake_id = st.stocktake_id AND i.found IS TRUE) AS pres,
           (SELECT COUNT(*) FROM stocktake_extras x WHERE x.stocktake_id = st.stocktake_id) AS ext
    FROM stocktakes st WHERE st.status = 'closed'
) c
WHERE s.stocktake_id = c.stocktake_id;
UPDATE stocktakes SET flagged = (score IS NOT NULL AND score < 95) WHERE status = 'closed';
