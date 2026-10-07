-- Warehouse / pound transfer requests (Officer requests -> Supervisor -> Manager; goods move on Manager approval).
CREATE TABLE IF NOT EXISTS transfer_requests (
    transfer_id        SERIAL PRIMARY KEY,
    entry_id           INT NOT NULL REFERENCES entries(entry_id),
    from_warehouse_id  INT NOT NULL REFERENCES warehouses(warehouse_id),
    to_warehouse_id    INT NOT NULL REFERENCES warehouses(warehouse_id),
    reason             TEXT NOT NULL,
    requested_by       INT REFERENCES users(user_id),
    requested_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    supervisor_status  VARCHAR(20) NOT NULL DEFAULT 'pending',
    supervisor_by      INT REFERENCES users(user_id),
    supervisor_at      TIMESTAMP,
    supervisor_notes   TEXT,
    manager_status     VARCHAR(20) NOT NULL DEFAULT 'pending',
    manager_by         INT REFERENCES users(user_id),
    manager_at         TIMESTAMP,
    manager_notes      TEXT,
    status             VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    moved_at           TIMESTAMP,
    CONSTRAINT transfer_different_places CHECK (from_warehouse_id <> to_warehouse_id)
);
CREATE INDEX IF NOT EXISTS idx_transfer_entry ON transfer_requests(entry_id);
-- only one open request per entry
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_transfer_per_entry
    ON transfer_requests(entry_id) WHERE status = 'pending';
