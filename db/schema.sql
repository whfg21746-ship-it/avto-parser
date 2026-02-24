CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    avito_category_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    keyword TEXT NOT NULL,
    avito_category_id INTEGER,
    price_max INTEGER,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_query_id INTEGER REFERENCES search_queries(id),
    category_id INTEGER REFERENCES categories(id),
    name TEXT NOT NULL,
    model_pattern TEXT NOT NULL,
    storage_gb INTEGER,
    threshold_price INTEGER NOT NULL,
    market_price INTEGER NOT NULL,
    max_seller_items INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seen_ads (
    ad_id TEXT PRIMARY KEY,
    item_id INTEGER REFERENCES items(id),
    price INTEGER,
    title TEXT,
    url TEXT,
    seller_type TEXT,
    ai_verdict TEXT,
    profit_estimate INTEGER,
    was_alerted BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
