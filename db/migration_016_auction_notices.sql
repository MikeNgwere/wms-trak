-- E-auction notices with Gazette tracking (s.39(3): at least one month's Gazette notice before sale).
CREATE TABLE IF NOT EXISTS auction_notices (
    notice_id        SERIAL PRIMARY KEY,
    entry_id         INT NOT NULL REFERENCES entries(entry_id),
    gazette_date     DATE NOT NULL,
    gazette_reference VARCHAR(120),
    auction_date     DATE NOT NULL,
    auction_platform VARCHAR(200),
    created_by       INT REFERENCES users(user_id),
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT auction_after_gazette CHECK (auction_date >= gazette_date)
);
CREATE INDEX IF NOT EXISTS idx_auction_notices_entry ON auction_notices(entry_id);
