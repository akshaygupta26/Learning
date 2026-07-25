-- Pokémon card price database — schema
--
-- IMPORTANT GRAIN NOTE
-- TCGCSV mirrors TCGplayer at the *product x printing* level, NOT the SKU
-- level. There is no NM/LP/MP/HP breakdown in the feed — condition-level
-- pricing requires the real TCGplayer API, which is closed to new applicants.
--
-- Consequence: prices here are effectively Near Mint. Condition is a property
-- of things you *buy* and *see listed*, never of the reference price feed.
-- Condition discounts are modeled in pokedb/fees.py.

PRAGMA foreign_keys = ON;


-- ---------------------------------------------------------------------------
-- Catalog
-- ---------------------------------------------------------------------------

-- A "set" is a TCGplayer group.
CREATE TABLE IF NOT EXISTS sets (
    group_id        INTEGER PRIMARY KEY,
    abbreviation    TEXT,
    name            TEXT    NOT NULL,
    era             TEXT,              -- ME / SV / SWSH, assigned by config.py
    published_on    TEXT,
    is_supplemental INTEGER NOT NULL DEFAULT 0,
    modified_on     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sets_era ON sets(era);


-- Products span both singles and sealed. `is_single` splits them: TCGCSV
-- singles carry a "Number" field in extendedData, sealed product does not.
CREATE TABLE IF NOT EXISTS products (
    product_id  INTEGER PRIMARY KEY,
    group_id    INTEGER NOT NULL REFERENCES sets(group_id),
    name        TEXT    NOT NULL,
    clean_name  TEXT,
    is_single   INTEGER NOT NULL DEFAULT 0,
    number      TEXT,                  -- NULL for sealed
    rarity      TEXT,
    card_type   TEXT,
    hp          TEXT,
    image_url   TEXT,
    url         TEXT,
    modified_on TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_group  ON products(group_id);
CREATE INDEX IF NOT EXISTS idx_products_single ON products(is_single);
CREATE INDEX IF NOT EXISTS idx_products_name   ON products(clean_name);


-- ---------------------------------------------------------------------------
-- Price facts
-- ---------------------------------------------------------------------------

-- Grain: product x printing x day x source.
-- Re-running an ingest on the same day overwrites that day's row rather than
-- duplicating it, which is what makes the daily job safely idempotent.
CREATE TABLE IF NOT EXISTS price_snapshots (
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    sub_type_name    TEXT    NOT NULL,   -- Normal / Holofoil / Reverse Holofoil
    as_of_date       TEXT    NOT NULL,   -- YYYY-MM-DD (UTC)
    source           TEXT    NOT NULL DEFAULT 'tcgcsv',
    low_price        REAL,
    mid_price        REAL,
    high_price       REAL,
    market_price     REAL,
    direct_low_price REAL,
    PRIMARY KEY (product_id, sub_type_name, as_of_date, source)
);

CREATE INDEX IF NOT EXISTS idx_snap_date ON price_snapshots(as_of_date);


-- Graded prices (Phase 5, PokemonPriceTracker). Separate table because the
-- grain differs: graded pricing is per card x grader x grade, and comes from
-- realized eBay sales rather than active-listing aggregates.
CREATE TABLE IF NOT EXISTS graded_prices (
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    grader      TEXT    NOT NULL,       -- PSA / CGC / BGS
    grade       REAL    NOT NULL,
    as_of_date  TEXT    NOT NULL,
    sale_price  REAL,
    sample_size INTEGER,
    source      TEXT    NOT NULL DEFAULT 'ppt',
    PRIMARY KEY (product_id, grader, grade, as_of_date, source)
);


-- Active eBay listings (Phase 3). Asking prices, NOT sales — eBay's sold-comp
-- API is Limited Release and closed to individual developers.
CREATE TABLE IF NOT EXISTS ebay_listings (
    listing_id       TEXT PRIMARY KEY,
    product_id       INTEGER REFERENCES products(product_id),
    raw_title        TEXT NOT NULL,
    price            REAL,
    shipping_cost    REAL,
    condition_parsed TEXT,
    grade_parsed     TEXT,
    seller           TEXT,
    listing_type     TEXT,
    end_time         TEXT,
    observed_at      TEXT NOT NULL,
    match_confidence REAL              -- title parsing is lossy; keep the score
);

CREATE INDEX IF NOT EXISTS idx_listings_product ON ebay_listings(product_id);


-- ---------------------------------------------------------------------------
-- Trading (Phase 6)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS watchlist (
    product_id       INTEGER PRIMARY KEY REFERENCES products(product_id),
    target_buy_price REAL,
    notes            TEXT,
    added_at         TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS inventory (
    lot_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id                INTEGER NOT NULL REFERENCES products(product_id),
    sub_type_name             TEXT,
    condition                 TEXT,    -- what you actually received
    acquired_date             TEXT NOT NULL,
    acquired_price            REAL NOT NULL,
    acquired_fees             REAL NOT NULL DEFAULT 0,
    acquired_venue            TEXT,
    status                    TEXT NOT NULL DEFAULT 'held',  -- held/listed/sold
    -- Recorded at purchase time so the model can be graded later. This column
    -- is the whole point of Notebook 3.
    predicted_net_at_purchase REAL,
    predicted_fvf_rate        REAL,
    notes                     TEXT
);


CREATE TABLE IF NOT EXISTS sales (
    sale_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id           INTEGER NOT NULL REFERENCES inventory(lot_id),
    sold_date        TEXT NOT NULL,
    venue            TEXT NOT NULL,
    gross_price      REAL NOT NULL,
    platform_fee     REAL NOT NULL DEFAULT 0,
    payment_fee      REAL NOT NULL DEFAULT 0,
    shipping_cost    REAL NOT NULL DEFAULT 0,
    shipping_charged REAL NOT NULL DEFAULT 0,
    supplies_cost    REAL NOT NULL DEFAULT 0,
    net_proceeds     REAL NOT NULL
);


-- ---------------------------------------------------------------------------
-- Observability
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    status            TEXT NOT NULL DEFAULT 'running',
    sets_seen         INTEGER DEFAULT 0,
    products_upserted INTEGER DEFAULT 0,
    prices_written    INTEGER DEFAULT 0,
    requests_made     INTEGER DEFAULT 0,
    error             TEXT
);


-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- Most recent snapshot per product x printing.
CREATE VIEW IF NOT EXISTS v_latest_prices AS
SELECT p.product_id,
       p.name,
       p.number,
       p.rarity,
       s.abbreviation AS set_abbr,
       s.name         AS set_name,
       s.era,
       ps.sub_type_name,
       ps.as_of_date,
       ps.market_price,
       ps.low_price,
       ps.mid_price,
       ps.high_price
FROM price_snapshots ps
JOIN products p ON p.product_id = ps.product_id
JOIN sets     s ON s.group_id   = p.group_id
WHERE ps.as_of_date = (
    SELECT MAX(as_of_date)
    FROM price_snapshots x
    WHERE x.product_id    = ps.product_id
      AND x.sub_type_name = ps.sub_type_name
);


-- Tradeable universe: singles with a real market price. Sealed excluded.
CREATE VIEW IF NOT EXISTS v_tradeable AS
SELECT *
FROM v_latest_prices
WHERE market_price IS NOT NULL
  AND market_price > 0
  AND product_id IN (SELECT product_id FROM products WHERE is_single = 1);


-- Realized and unrealized P&L, with predicted-vs-actual error.
-- The `net_error` column is what Notebook 3 analyses.
CREATE VIEW IF NOT EXISTS v_pnl AS
SELECT i.lot_id,
       i.product_id,
       p.name AS product_name,
       i.status,
       i.acquired_date,
       i.acquired_price + i.acquired_fees AS cost_basis,
       i.predicted_net_at_purchase,
       sa.sold_date,
       sa.gross_price,
       sa.net_proceeds,
       sa.net_proceeds - (i.acquired_price + i.acquired_fees) AS realized_pnl,
       sa.net_proceeds - i.predicted_net_at_purchase          AS net_error
FROM inventory i
JOIN products p ON p.product_id = i.product_id
LEFT JOIN sales sa ON sa.lot_id = i.lot_id;
