-- Stocktake / reconciliation: physical count of a warehouse against the system list.
CREATE TABLE IF NOT EXISTS stocktakes (
    stocktake_id  SERIAL PRIMARY KEY,
    warehouse_id  INT NOT NULL REFERENCES warehouses(warehouse_id),
    port_code     VARCHAR(20),
    started_by    INT REFERENCES users(user_id),
    started_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_by     INT REFERENCES users(user_id),
    closed_at     TIMESTAMP,
    status        VARCHAR(10) NOT NULL DEFAULT 'open',   -- open | closed
    notes         TEXT
);

-- One row per entry the system expected to find in the warehouse when the count started.
CREATE TABLE IF NOT EXISTS stocktake_items (
    item_id       SERIAL PRIMARY KEY,
    stocktake_id  INT NOT NULL REFERENCES stocktakes(stocktake_id) ON DELETE CASCADE,
    entry_id      INT NOT NULL REFERENCES entries(entry_id),
    found         BOOLEAN,                                -- NULL = not yet counted
    counted_by    INT REFERENCES users(user_id),
    counted_at    TIMESTAMP,
    UNIQUE (stocktake_id, entry_id)
);

-- Goods physically found that the system does not list in this warehouse.
CREATE TABLE IF NOT EXISTS stocktake_extras (
    extra_id      SERIAL PRIMARY KEY,
    stocktake_id  INT NOT NULL REFERENCES stocktakes(stocktake_id) ON DELETE CASCADE,
    description   TEXT NOT NULL,
    quantity_text VARCHAR(100),
    noted_by      INT REFERENCES users(user_id),
    noted_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Only one open stocktake per warehouse at a time.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_stocktake_per_warehouse
    ON stocktakes (warehouse_id) WHERE status = 'open';
