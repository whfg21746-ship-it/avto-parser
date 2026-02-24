"""Seed all Apple product models into the database (new schema)."""
import os
import sqlite3

from parser.model_matcher import extract_storage_from_name, generate_model_pattern

DB_PATH = os.getenv("DATABASE_PATH", "./data/flipper.db")

# search_query_id mapping: 1=iphone, 2=macbook, 3=airpods, 4=ipad, 5=apple watch
# category_id: 1=Смартфоны, 2=Ноутбуки, 3=Наушники, 4=Планшеты

SEARCH_QUERIES = [
    # (category_id, keyword, avito_category_id, price_max)
    (1, "iphone", 84, 150000),
    (2, "macbook", None, 250000),
    (3, "airpods", None, 50000),
    (4, "ipad", None, 150000),
    (1, "apple watch", None, 80000),
]

ITEMS = []

# ============================================================
# iPHONE (search_query_id=1, category_id=1)
# (name, threshold_price, market_price)
# ============================================================

IPHONES = [
    # iPhone 11
    ("iPhone 11 64GB",   11000, 16000),
    ("iPhone 11 128GB",  13000, 18000),
    ("iPhone 11 256GB",  15000, 21000),
    # iPhone 11 Pro
    ("iPhone 11 Pro 64GB",   13000, 19000),
    ("iPhone 11 Pro 256GB",  16000, 23000),
    ("iPhone 11 Pro 512GB",  18000, 26000),
    # iPhone 11 Pro Max
    ("iPhone 11 Pro Max 64GB",   15000, 22000),
    ("iPhone 11 Pro Max 256GB",  18000, 26000),
    ("iPhone 11 Pro Max 512GB",  21000, 29000),

    # iPhone 12 mini
    ("iPhone 12 mini 64GB",   13000, 18000),
    ("iPhone 12 mini 128GB",  15000, 21000),
    ("iPhone 12 mini 256GB",  17000, 23000),
    # iPhone 12
    ("iPhone 12 64GB",   15000, 21000),
    ("iPhone 12 128GB",  17000, 24000),
    ("iPhone 12 256GB",  20000, 27000),
    # iPhone 12 Pro
    ("iPhone 12 Pro 128GB",  19000, 26000),
    ("iPhone 12 Pro 256GB",  22000, 30000),
    ("iPhone 12 Pro 512GB",  25000, 33000),
    # iPhone 12 Pro Max
    ("iPhone 12 Pro Max 128GB",  22000, 30000),
    ("iPhone 12 Pro Max 256GB",  25000, 34000),
    ("iPhone 12 Pro Max 512GB",  28000, 37000),

    # iPhone 13 mini
    ("iPhone 13 mini 128GB",  18000, 25000),
    ("iPhone 13 mini 256GB",  21000, 28000),
    ("iPhone 13 mini 512GB",  24000, 32000),
    # iPhone 13
    ("iPhone 13 128GB",  21000, 29000),
    ("iPhone 13 256GB",  24000, 32000),
    ("iPhone 13 512GB",  27000, 36000),
    # iPhone 13 Pro
    ("iPhone 13 Pro 128GB",   26000, 35000),
    ("iPhone 13 Pro 256GB",   29000, 39000),
    ("iPhone 13 Pro 512GB",   33000, 43000),
    ("iPhone 13 Pro 1TB",     37000, 48000),
    # iPhone 13 Pro Max
    ("iPhone 13 Pro Max 128GB",  30000, 40000),
    ("iPhone 13 Pro Max 256GB",  33000, 44000),
    ("iPhone 13 Pro Max 512GB",  37000, 48000),
    ("iPhone 13 Pro Max 1TB",    42000, 54000),

    # iPhone 14
    ("iPhone 14 128GB",  27000, 36000),
    ("iPhone 14 256GB",  30000, 40000),
    ("iPhone 14 512GB",  34000, 45000),
    # iPhone 14 Plus
    ("iPhone 14 Plus 128GB",  29000, 39000),
    ("iPhone 14 Plus 256GB",  33000, 43000),
    ("iPhone 14 Plus 512GB",  36000, 47000),
    # iPhone 14 Pro
    ("iPhone 14 Pro 128GB",   34000, 45000),
    ("iPhone 14 Pro 256GB",   38000, 50000),
    ("iPhone 14 Pro 512GB",   43000, 56000),
    ("iPhone 14 Pro 1TB",     48000, 62000),
    # iPhone 14 Pro Max
    ("iPhone 14 Pro Max 128GB",  39000, 51000),
    ("iPhone 14 Pro Max 256GB",  43000, 56000),
    ("iPhone 14 Pro Max 512GB",  48000, 62000),
    ("iPhone 14 Pro Max 1TB",    54000, 69000),

    # iPhone 15
    ("iPhone 15 128GB",  37000, 48000),
    ("iPhone 15 256GB",  41000, 53000),
    ("iPhone 15 512GB",  46000, 59000),
    # iPhone 15 Plus
    ("iPhone 15 Plus 128GB",  41000, 53000),
    ("iPhone 15 Plus 256GB",  45000, 58000),
    ("iPhone 15 Plus 512GB",  49000, 63000),
    # iPhone 15 Pro
    ("iPhone 15 Pro 128GB",   47000, 61000),
    ("iPhone 15 Pro 256GB",   52000, 67000),
    ("iPhone 15 Pro 512GB",   58000, 74000),
    ("iPhone 15 Pro 1TB",     65000, 82000),
    # iPhone 15 Pro Max
    ("iPhone 15 Pro Max 256GB",  59000, 75000),
    ("iPhone 15 Pro Max 512GB",  66000, 83000),
    ("iPhone 15 Pro Max 1TB",    74000, 92000),

    # iPhone 16
    ("iPhone 16 128GB",  47000, 61000),
    ("iPhone 16 256GB",  52000, 67000),
    ("iPhone 16 512GB",  57000, 73000),
    # iPhone 16 Plus
    ("iPhone 16 Plus 128GB",  52000, 67000),
    ("iPhone 16 Plus 256GB",  57000, 73000),
    ("iPhone 16 Plus 512GB",  62000, 79000),
    # iPhone 16 Pro
    ("iPhone 16 Pro 128GB",   59000, 75000),
    ("iPhone 16 Pro 256GB",   65000, 82000),
    ("iPhone 16 Pro 512GB",   72000, 90000),
    ("iPhone 16 Pro 1TB",     80000, 99000),
    # iPhone 16 Pro Max
    ("iPhone 16 Pro Max 256GB",  72000, 91000),
    ("iPhone 16 Pro Max 512GB",  80000, 100000),
    ("iPhone 16 Pro Max 1TB",    89000, 111000),

    # iPhone 17
    ("iPhone 17 128GB",  58000, 74000),
    ("iPhone 17 256GB",  63000, 80000),
    ("iPhone 17 512GB",  69000, 87000),
    # iPhone 17 Plus / Air
    ("iPhone 17 Plus 128GB",  63000, 80000),
    ("iPhone 17 Plus 256GB",  68000, 86000),
    ("iPhone 17 Plus 512GB",  74000, 93000),
    # iPhone 17 Pro
    ("iPhone 17 Pro 128GB",   71000, 89000),
    ("iPhone 17 Pro 256GB",   77000, 96000),
    ("iPhone 17 Pro 512GB",   84000, 105000),
    ("iPhone 17 Pro 1TB",     92000, 115000),
    # iPhone 17 Pro Max
    ("iPhone 17 Pro Max 256GB",  84000, 105000),
    ("iPhone 17 Pro Max 512GB",  92000, 115000),
    ("iPhone 17 Pro Max 1TB",    101000, 126000),
]

for name, threshold, market in IPHONES:
    ITEMS.append((1, 1, name, threshold, market))  # sq_id=1, cat_id=1

# ============================================================
# MacBook (search_query_id=2, category_id=2)
# ============================================================

MACBOOKS = [
    # 2020
    ("MacBook Air M1 2020 8/256GB",   30000, 40000),
    ("MacBook Air M1 2020 8/512GB",   35000, 46000),
    ("MacBook Air M1 2020 16/256GB",  37000, 48000),
    ("MacBook Pro 13 M1 2020 8/256GB",  32000, 43000),
    ("MacBook Pro 13 M1 2020 8/512GB",  37000, 48000),
    ("MacBook Pro 13 M1 2020 16/512GB", 40000, 52000),

    # 2021 Pro 14/16
    ("MacBook Pro 14 M1 Pro 2021 16/512GB",   52000, 67000),
    ("MacBook Pro 14 M1 Pro 2021 16/1TB",   58000, 74000),
    ("MacBook Pro 14 M1 Max 2021 32/1TB",   68000, 86000),
    ("MacBook Pro 16 M1 Pro 2021 16/512GB",   57000, 73000),
    ("MacBook Pro 16 M1 Pro 2021 16/1TB",   63000, 80000),
    ("MacBook Pro 16 M1 Max 2021 32/1TB",   73000, 92000),

    # 2022
    ("MacBook Air M2 2022 8/256GB",   38000, 50000),
    ("MacBook Air M2 2022 8/512GB",   43000, 56000),
    ("MacBook Air M2 2022 16/512GB",  48000, 62000),
    ("MacBook Pro 13 M2 2022 8/256GB",  37000, 48000),
    ("MacBook Pro 13 M2 2022 8/512GB",  42000, 55000),

    # 2023 M2 Pro/Max
    ("MacBook Pro 14 M2 Pro 2023 16/512GB",   62000, 79000),
    ("MacBook Pro 14 M2 Pro 2023 16/1TB",   69000, 87000),
    ("MacBook Pro 14 M2 Max 2023 32/1TB",   82000, 103000),
    ("MacBook Pro 16 M2 Pro 2023 16/512GB",   68000, 86000),
    ("MacBook Pro 16 M2 Pro 2023 16/1TB",   75000, 94000),
    ("MacBook Pro 16 M2 Max 2023 32/1TB",   88000, 110000),

    # 2023-2024 M3
    ("MacBook Air 13 M3 2024 8/256GB",  48000, 62000),
    ("MacBook Air 13 M3 2024 8/512GB",  54000, 69000),
    ("MacBook Air 13 M3 2024 16/512GB", 59000, 75000),
    ("MacBook Air 15 M3 2024 8/256GB",  53000, 68000),
    ("MacBook Air 15 M3 2024 8/512GB",  59000, 75000),
    ("MacBook Air 15 M3 2024 16/512GB", 64000, 81000),
    ("MacBook Pro 14 M3 2023 8/512GB",        56000, 72000),
    ("MacBook Pro 14 M3 Pro 2023 18/512GB",   72000, 91000),
    ("MacBook Pro 14 M3 Pro 2023 18/1TB",   79000, 99000),
    ("MacBook Pro 14 M3 Max 2023 36/1TB",   95000, 119000),
    ("MacBook Pro 16 M3 Pro 2023 18/512GB",   78000, 98000),
    ("MacBook Pro 16 M3 Pro 2023 18/1TB",   85000, 106000),
    ("MacBook Pro 16 M3 Max 2023 36/1TB",   100000, 125000),

    # 2024 M4
    ("MacBook Pro 14 M4 2024 16/512GB",       68000, 86000),
    ("MacBook Pro 14 M4 2024 16/1TB",       75000, 94000),
    ("MacBook Pro 14 M4 Pro 2024 24/512GB",   85000, 106000),
    ("MacBook Pro 14 M4 Pro 2024 24/1TB",   92000, 115000),
    ("MacBook Pro 14 M4 Max 2024 36/1TB",   110000, 137000),
    ("MacBook Pro 16 M4 Pro 2024 24/512GB",   92000, 115000),
    ("MacBook Pro 16 M4 Pro 2024 24/1TB",   99000, 124000),
    ("MacBook Pro 16 M4 Max 2024 36/1TB",   118000, 147000),
]

for name, threshold, market in MACBOOKS:
    ITEMS.append((2, 2, name, threshold, market))  # sq_id=2, cat_id=2

# ============================================================
# AirPods (search_query_id=3, category_id=3)
# ============================================================

AIRPODS = [
    ("AirPods 2",                  3000, 5000),
    ("AirPods 3",                  5000, 8000),
    ("AirPods 3 Lightning",        4500, 7000),
    ("AirPods Pro",                5000, 8000),
    ("AirPods Pro 2 USB-C",        8000, 12000),
    ("AirPods 4",                  7000, 10000),
    ("AirPods 4 ANC",              9000, 13000),
    ("AirPods Max",                22000, 31000),
    ("AirPods Max 2 USB-C",        32000, 43000),
]

for name, threshold, market in AIRPODS:
    ITEMS.append((3, 3, name, threshold, market))  # sq_id=3, cat_id=3

# ============================================================
# iPad (search_query_id=4, category_id=4)
# ============================================================

IPADS = [
    # iPad base
    ("iPad 8 2020 32GB Wi-Fi",    10000, 15000),
    ("iPad 8 2020 128GB Wi-Fi",   13000, 18000),
    ("iPad 9 2021 64GB Wi-Fi",    13000, 18000),
    ("iPad 9 2021 256GB Wi-Fi",   17000, 23000),
    ("iPad 10 2022 64GB Wi-Fi",   18000, 25000),
    ("iPad 10 2022 256GB Wi-Fi",  23000, 31000),

    # iPad mini
    ("iPad mini 6 2021 64GB Wi-Fi",   20000, 28000),
    ("iPad mini 6 2021 256GB Wi-Fi",  25000, 34000),
    ("iPad mini 7 2024 128GB Wi-Fi",  28000, 37000),
    ("iPad mini 7 2024 256GB Wi-Fi",  33000, 43000),
    ("iPad mini 7 2024 512GB Wi-Fi",  38000, 49000),

    # iPad Air
    ("iPad Air 4 2020 64GB Wi-Fi",    18000, 25000),
    ("iPad Air 4 2020 256GB Wi-Fi",   22000, 30000),
    ("iPad Air 5 M1 2022 64GB Wi-Fi",   24000, 33000),
    ("iPad Air 5 M1 2022 256GB Wi-Fi",  29000, 39000),
    ("iPad Air 11 M2 2024 128GB Wi-Fi", 33000, 43000),
    ("iPad Air 11 M2 2024 256GB Wi-Fi", 38000, 49000),
    ("iPad Air 11 M2 2024 512GB Wi-Fi", 44000, 56000),
    ("iPad Air 11 M2 2024 1TB Wi-Fi",   52000, 66000),
    ("iPad Air 13 M2 2024 128GB Wi-Fi", 40000, 52000),
    ("iPad Air 13 M2 2024 256GB Wi-Fi", 46000, 59000),
    ("iPad Air 13 M2 2024 512GB Wi-Fi", 52000, 66000),
    ("iPad Air 13 M2 2024 1TB Wi-Fi",   60000, 76000),

    # iPad Pro
    ("iPad Pro 11 M1 2021 128GB Wi-Fi",  28000, 37000),
    ("iPad Pro 11 M1 2021 256GB Wi-Fi",  32000, 42000),
    ("iPad Pro 11 M1 2021 512GB Wi-Fi",  37000, 48000),
    ("iPad Pro 11 M1 2021 1TB Wi-Fi",    43000, 56000),
    ("iPad Pro 12.9 M1 2021 128GB Wi-Fi", 35000, 46000),
    ("iPad Pro 12.9 M1 2021 256GB Wi-Fi", 40000, 52000),
    ("iPad Pro 12.9 M1 2021 512GB Wi-Fi", 46000, 59000),
    ("iPad Pro 12.9 M1 2021 1TB Wi-Fi",   53000, 68000),
    ("iPad Pro 11 M2 2022 128GB Wi-Fi",  35000, 46000),
    ("iPad Pro 11 M2 2022 256GB Wi-Fi",  40000, 52000),
    ("iPad Pro 11 M2 2022 512GB Wi-Fi",  46000, 59000),
    ("iPad Pro 11 M2 2022 1TB Wi-Fi",    53000, 68000),
    ("iPad Pro 12.9 M2 2022 128GB Wi-Fi", 43000, 56000),
    ("iPad Pro 12.9 M2 2022 256GB Wi-Fi", 48000, 62000),
    ("iPad Pro 12.9 M2 2022 512GB Wi-Fi", 55000, 70000),
    ("iPad Pro 12.9 M2 2022 1TB Wi-Fi",   63000, 80000),
    # M4 2024
    ("iPad Pro 11 M4 2024 256GB Wi-Fi",  48000, 62000),
    ("iPad Pro 11 M4 2024 512GB Wi-Fi",  55000, 70000),
    ("iPad Pro 11 M4 2024 1TB Wi-Fi",    65000, 82000),
    ("iPad Pro 13 M4 2024 256GB Wi-Fi",  58000, 74000),
    ("iPad Pro 13 M4 2024 512GB Wi-Fi",  66000, 83000),
    ("iPad Pro 13 M4 2024 1TB Wi-Fi",    77000, 97000),
]

for name, threshold, market in IPADS:
    ITEMS.append((4, 4, name, threshold, market))  # sq_id=4, cat_id=4


def main():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    # Clear existing data (but keep categories and settings)
    cursor.execute("DELETE FROM seen_ads")
    cursor.execute("DELETE FROM items")
    cursor.execute("DELETE FROM search_queries")
    db.commit()

    # Insert search queries
    for cat_id, keyword, avito_cat_id, price_max in SEARCH_QUERIES:
        cursor.execute(
            "INSERT INTO search_queries (category_id, keyword, avito_category_id, price_max) "
            "VALUES (?, ?, ?, ?)",
            (cat_id, keyword, avito_cat_id, price_max),
        )
    db.commit()

    # Insert items with auto-generated patterns
    count = 0
    for sq_id, cat_id, name, threshold, market in ITEMS:
        pattern = generate_model_pattern(name)
        storage = extract_storage_from_name(name)
        cursor.execute(
            "INSERT INTO items (search_query_id, category_id, name, model_pattern, "
            "storage_gb, threshold_price, market_price, max_seller_items, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sq_id, cat_id, name, pattern, storage, threshold, market, 10, 1),
        )
        count += 1

    db.commit()
    db.close()

    print(f"Seeded {len(SEARCH_QUERIES)} search queries and {count} items:")
    iphones = sum(1 for i in ITEMS if i[0] == 1)
    macs = sum(1 for i in ITEMS if i[0] == 2)
    airpods_count = sum(1 for i in ITEMS if i[0] == 3)
    ipads_count = sum(1 for i in ITEMS if i[0] == 4)
    print(f"  iPhone: {iphones}")
    print(f"  MacBook: {macs}")
    print(f"  AirPods: {airpods_count}")
    print(f"  iPad: {ipads_count}")


if __name__ == "__main__":
    main()
