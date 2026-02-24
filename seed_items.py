"""Seed all Apple product models into the database."""
import asyncio
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "./data/flipper.db")

# category_id: 1=Смартфоны, 2=Ноутбуки, 3=Наушники, 4=Планшеты

ITEMS = []

# ============================================================
# iPHONE (category_id=1)
# (name, search_query, threshold_price, market_price)
# ============================================================

IPHONES = [
    # iPhone 11
    ("iPhone 11 64GB",   "iPhone 11 64",    11000, 16000),
    ("iPhone 11 128GB",  "iPhone 11 128",   13000, 18000),
    ("iPhone 11 256GB",  "iPhone 11 256",   15000, 21000),
    # iPhone 11 Pro
    ("iPhone 11 Pro 64GB",   "iPhone 11 Pro 64",   13000, 19000),
    ("iPhone 11 Pro 256GB",  "iPhone 11 Pro 256",  16000, 23000),
    ("iPhone 11 Pro 512GB",  "iPhone 11 Pro 512",  18000, 26000),
    # iPhone 11 Pro Max
    ("iPhone 11 Pro Max 64GB",   "iPhone 11 Pro Max 64",   15000, 22000),
    ("iPhone 11 Pro Max 256GB",  "iPhone 11 Pro Max 256",  18000, 26000),
    ("iPhone 11 Pro Max 512GB",  "iPhone 11 Pro Max 512",  21000, 29000),

    # iPhone 12 mini
    ("iPhone 12 mini 64GB",   "iPhone 12 mini 64",   13000, 18000),
    ("iPhone 12 mini 128GB",  "iPhone 12 mini 128",  15000, 21000),
    ("iPhone 12 mini 256GB",  "iPhone 12 mini 256",  17000, 23000),
    # iPhone 12
    ("iPhone 12 64GB",   "iPhone 12 64",   15000, 21000),
    ("iPhone 12 128GB",  "iPhone 12 128",  17000, 24000),
    ("iPhone 12 256GB",  "iPhone 12 256",  20000, 27000),
    # iPhone 12 Pro
    ("iPhone 12 Pro 128GB",  "iPhone 12 Pro 128",  19000, 26000),
    ("iPhone 12 Pro 256GB",  "iPhone 12 Pro 256",  22000, 30000),
    ("iPhone 12 Pro 512GB",  "iPhone 12 Pro 512",  25000, 33000),
    # iPhone 12 Pro Max
    ("iPhone 12 Pro Max 128GB",  "iPhone 12 Pro Max 128",  22000, 30000),
    ("iPhone 12 Pro Max 256GB",  "iPhone 12 Pro Max 256",  25000, 34000),
    ("iPhone 12 Pro Max 512GB",  "iPhone 12 Pro Max 512",  28000, 37000),

    # iPhone 13 mini
    ("iPhone 13 mini 128GB",  "iPhone 13 mini 128",  18000, 25000),
    ("iPhone 13 mini 256GB",  "iPhone 13 mini 256",  21000, 28000),
    ("iPhone 13 mini 512GB",  "iPhone 13 mini 512",  24000, 32000),
    # iPhone 13
    ("iPhone 13 128GB",  "iPhone 13 128",  21000, 29000),
    ("iPhone 13 256GB",  "iPhone 13 256",  24000, 32000),
    ("iPhone 13 512GB",  "iPhone 13 512",  27000, 36000),
    # iPhone 13 Pro
    ("iPhone 13 Pro 128GB",   "iPhone 13 Pro 128",   26000, 35000),
    ("iPhone 13 Pro 256GB",   "iPhone 13 Pro 256",   29000, 39000),
    ("iPhone 13 Pro 512GB",   "iPhone 13 Pro 512",   33000, 43000),
    ("iPhone 13 Pro 1TB",     "iPhone 13 Pro 1TB",   37000, 48000),
    # iPhone 13 Pro Max
    ("iPhone 13 Pro Max 128GB",  "iPhone 13 Pro Max 128",  30000, 40000),
    ("iPhone 13 Pro Max 256GB",  "iPhone 13 Pro Max 256",  33000, 44000),
    ("iPhone 13 Pro Max 512GB",  "iPhone 13 Pro Max 512",  37000, 48000),
    ("iPhone 13 Pro Max 1TB",    "iPhone 13 Pro Max 1TB",  42000, 54000),

    # iPhone 14
    ("iPhone 14 128GB",  "iPhone 14 128",  27000, 36000),
    ("iPhone 14 256GB",  "iPhone 14 256",  30000, 40000),
    ("iPhone 14 512GB",  "iPhone 14 512",  34000, 45000),
    # iPhone 14 Plus
    ("iPhone 14 Plus 128GB",  "iPhone 14 Plus 128",  29000, 39000),
    ("iPhone 14 Plus 256GB",  "iPhone 14 Plus 256",  33000, 43000),
    ("iPhone 14 Plus 512GB",  "iPhone 14 Plus 512",  36000, 47000),
    # iPhone 14 Pro
    ("iPhone 14 Pro 128GB",   "iPhone 14 Pro 128",   34000, 45000),
    ("iPhone 14 Pro 256GB",   "iPhone 14 Pro 256",   38000, 50000),
    ("iPhone 14 Pro 512GB",   "iPhone 14 Pro 512",   43000, 56000),
    ("iPhone 14 Pro 1TB",     "iPhone 14 Pro 1TB",   48000, 62000),
    # iPhone 14 Pro Max
    ("iPhone 14 Pro Max 128GB",  "iPhone 14 Pro Max 128",  39000, 51000),
    ("iPhone 14 Pro Max 256GB",  "iPhone 14 Pro Max 256",  43000, 56000),
    ("iPhone 14 Pro Max 512GB",  "iPhone 14 Pro Max 512",  48000, 62000),
    ("iPhone 14 Pro Max 1TB",    "iPhone 14 Pro Max 1TB",  54000, 69000),

    # iPhone 15
    ("iPhone 15 128GB",  "iPhone 15 128",  37000, 48000),
    ("iPhone 15 256GB",  "iPhone 15 256",  41000, 53000),
    ("iPhone 15 512GB",  "iPhone 15 512",  46000, 59000),
    # iPhone 15 Plus
    ("iPhone 15 Plus 128GB",  "iPhone 15 Plus 128",  41000, 53000),
    ("iPhone 15 Plus 256GB",  "iPhone 15 Plus 256",  45000, 58000),
    ("iPhone 15 Plus 512GB",  "iPhone 15 Plus 512",  49000, 63000),
    # iPhone 15 Pro
    ("iPhone 15 Pro 128GB",   "iPhone 15 Pro 128",   47000, 61000),
    ("iPhone 15 Pro 256GB",   "iPhone 15 Pro 256",   52000, 67000),
    ("iPhone 15 Pro 512GB",   "iPhone 15 Pro 512",   58000, 74000),
    ("iPhone 15 Pro 1TB",     "iPhone 15 Pro 1TB",   65000, 82000),
    # iPhone 15 Pro Max
    ("iPhone 15 Pro Max 256GB",  "iPhone 15 Pro Max 256",  59000, 75000),
    ("iPhone 15 Pro Max 512GB",  "iPhone 15 Pro Max 512",  66000, 83000),
    ("iPhone 15 Pro Max 1TB",    "iPhone 15 Pro Max 1TB",  74000, 92000),

    # iPhone 16
    ("iPhone 16 128GB",  "iPhone 16 128",  47000, 61000),
    ("iPhone 16 256GB",  "iPhone 16 256",  52000, 67000),
    ("iPhone 16 512GB",  "iPhone 16 512",  57000, 73000),
    # iPhone 16 Plus
    ("iPhone 16 Plus 128GB",  "iPhone 16 Plus 128",  52000, 67000),
    ("iPhone 16 Plus 256GB",  "iPhone 16 Plus 256",  57000, 73000),
    ("iPhone 16 Plus 512GB",  "iPhone 16 Plus 512",  62000, 79000),
    # iPhone 16 Pro
    ("iPhone 16 Pro 128GB",   "iPhone 16 Pro 128",   59000, 75000),
    ("iPhone 16 Pro 256GB",   "iPhone 16 Pro 256",   65000, 82000),
    ("iPhone 16 Pro 512GB",   "iPhone 16 Pro 512",   72000, 90000),
    ("iPhone 16 Pro 1TB",     "iPhone 16 Pro 1TB",   80000, 99000),
    # iPhone 16 Pro Max
    ("iPhone 16 Pro Max 256GB",  "iPhone 16 Pro Max 256",  72000, 91000),
    ("iPhone 16 Pro Max 512GB",  "iPhone 16 Pro Max 512",  80000, 100000),
    ("iPhone 16 Pro Max 1TB",    "iPhone 16 Pro Max 1TB",  89000, 111000),

    # iPhone 17
    ("iPhone 17 128GB",  "iPhone 17 128",  58000, 74000),
    ("iPhone 17 256GB",  "iPhone 17 256",  63000, 80000),
    ("iPhone 17 512GB",  "iPhone 17 512",  69000, 87000),
    # iPhone 17 Plus / Air
    ("iPhone 17 Plus 128GB",  "iPhone 17 Plus 128",  63000, 80000),
    ("iPhone 17 Plus 256GB",  "iPhone 17 Plus 256",  68000, 86000),
    ("iPhone 17 Plus 512GB",  "iPhone 17 Plus 512",  74000, 93000),
    # iPhone 17 Pro
    ("iPhone 17 Pro 128GB",   "iPhone 17 Pro 128",   71000, 89000),
    ("iPhone 17 Pro 256GB",   "iPhone 17 Pro 256",   77000, 96000),
    ("iPhone 17 Pro 512GB",   "iPhone 17 Pro 512",   84000, 105000),
    ("iPhone 17 Pro 1TB",     "iPhone 17 Pro 1TB",   92000, 115000),
    # iPhone 17 Pro Max
    ("iPhone 17 Pro Max 256GB",  "iPhone 17 Pro Max 256",  84000, 105000),
    ("iPhone 17 Pro Max 512GB",  "iPhone 17 Pro Max 512",  92000, 115000),
    ("iPhone 17 Pro Max 1TB",    "iPhone 17 Pro Max 1TB",  101000, 126000),
]

for name, query, threshold, market in IPHONES:
    ITEMS.append((1, name, query, "{}", threshold, market))

# ============================================================
# MacBook (category_id=2)
# ============================================================

MACBOOKS = [
    # 2020
    ("MacBook Air M1 2020 8/256",   "MacBook Air M1 256",   30000, 40000),
    ("MacBook Air M1 2020 8/512",   "MacBook Air M1 512",   35000, 46000),
    ("MacBook Air M1 2020 16/256",  "MacBook Air M1 16GB",  37000, 48000),
    ("MacBook Pro 13 M1 2020 8/256",  "MacBook Pro 13 M1 256",  32000, 43000),
    ("MacBook Pro 13 M1 2020 8/512",  "MacBook Pro 13 M1 512",  37000, 48000),
    ("MacBook Pro 13 M1 2020 16/512", "MacBook Pro 13 M1 16GB", 40000, 52000),

    # 2021 Pro 14/16
    ("MacBook Pro 14 M1 Pro 2021 16/512",   "MacBook Pro 14 M1 Pro 512",   52000, 67000),
    ("MacBook Pro 14 M1 Pro 2021 16/1TB",   "MacBook Pro 14 M1 Pro 1TB",   58000, 74000),
    ("MacBook Pro 14 M1 Max 2021 32/1TB",   "MacBook Pro 14 M1 Max 1TB",   68000, 86000),
    ("MacBook Pro 16 M1 Pro 2021 16/512",   "MacBook Pro 16 M1 Pro 512",   57000, 73000),
    ("MacBook Pro 16 M1 Pro 2021 16/1TB",   "MacBook Pro 16 M1 Pro 1TB",   63000, 80000),
    ("MacBook Pro 16 M1 Max 2021 32/1TB",   "MacBook Pro 16 M1 Max 1TB",   73000, 92000),

    # 2022
    ("MacBook Air M2 2022 8/256",   "MacBook Air M2 256",   38000, 50000),
    ("MacBook Air M2 2022 8/512",   "MacBook Air M2 512",   43000, 56000),
    ("MacBook Air M2 2022 16/512",  "MacBook Air M2 16GB",  48000, 62000),
    ("MacBook Pro 13 M2 2022 8/256",  "MacBook Pro 13 M2 256",  37000, 48000),
    ("MacBook Pro 13 M2 2022 8/512",  "MacBook Pro 13 M2 512",  42000, 55000),

    # 2023 M2 Pro/Max
    ("MacBook Pro 14 M2 Pro 2023 16/512",   "MacBook Pro 14 M2 Pro 512",   62000, 79000),
    ("MacBook Pro 14 M2 Pro 2023 16/1TB",   "MacBook Pro 14 M2 Pro 1TB",   69000, 87000),
    ("MacBook Pro 14 M2 Max 2023 32/1TB",   "MacBook Pro 14 M2 Max 1TB",   82000, 103000),
    ("MacBook Pro 16 M2 Pro 2023 16/512",   "MacBook Pro 16 M2 Pro 512",   68000, 86000),
    ("MacBook Pro 16 M2 Pro 2023 16/1TB",   "MacBook Pro 16 M2 Pro 1TB",   75000, 94000),
    ("MacBook Pro 16 M2 Max 2023 32/1TB",   "MacBook Pro 16 M2 Max 1TB",   88000, 110000),

    # 2023-2024 M3
    ("MacBook Air 13 M3 2024 8/256",  "MacBook Air 13 M3 256",  48000, 62000),
    ("MacBook Air 13 M3 2024 8/512",  "MacBook Air 13 M3 512",  54000, 69000),
    ("MacBook Air 13 M3 2024 16/512", "MacBook Air 13 M3 16GB", 59000, 75000),
    ("MacBook Air 15 M3 2024 8/256",  "MacBook Air 15 M3 256",  53000, 68000),
    ("MacBook Air 15 M3 2024 8/512",  "MacBook Air 15 M3 512",  59000, 75000),
    ("MacBook Air 15 M3 2024 16/512", "MacBook Air 15 M3 16GB", 64000, 81000),
    ("MacBook Pro 14 M3 2023 8/512",        "MacBook Pro 14 M3 512",       56000, 72000),
    ("MacBook Pro 14 M3 Pro 2023 18/512",   "MacBook Pro 14 M3 Pro 512",   72000, 91000),
    ("MacBook Pro 14 M3 Pro 2023 18/1TB",   "MacBook Pro 14 M3 Pro 1TB",   79000, 99000),
    ("MacBook Pro 14 M3 Max 2023 36/1TB",   "MacBook Pro 14 M3 Max 1TB",   95000, 119000),
    ("MacBook Pro 16 M3 Pro 2023 18/512",   "MacBook Pro 16 M3 Pro 512",   78000, 98000),
    ("MacBook Pro 16 M3 Pro 2023 18/1TB",   "MacBook Pro 16 M3 Pro 1TB",   85000, 106000),
    ("MacBook Pro 16 M3 Max 2023 36/1TB",   "MacBook Pro 16 M3 Max 1TB",   100000, 125000),

    # 2024 M4
    ("MacBook Pro 14 M4 2024 16/512",       "MacBook Pro 14 M4 512",       68000, 86000),
    ("MacBook Pro 14 M4 2024 16/1TB",       "MacBook Pro 14 M4 1TB",       75000, 94000),
    ("MacBook Pro 14 M4 Pro 2024 24/512",   "MacBook Pro 14 M4 Pro 512",   85000, 106000),
    ("MacBook Pro 14 M4 Pro 2024 24/1TB",   "MacBook Pro 14 M4 Pro 1TB",   92000, 115000),
    ("MacBook Pro 14 M4 Max 2024 36/1TB",   "MacBook Pro 14 M4 Max 1TB",   110000, 137000),
    ("MacBook Pro 16 M4 Pro 2024 24/512",   "MacBook Pro 16 M4 Pro 512",   92000, 115000),
    ("MacBook Pro 16 M4 Pro 2024 24/1TB",   "MacBook Pro 16 M4 Pro 1TB",   99000, 124000),
    ("MacBook Pro 16 M4 Max 2024 36/1TB",   "MacBook Pro 16 M4 Max 1TB",   118000, 147000),
]

for name, query, threshold, market in MACBOOKS:
    ITEMS.append((2, name, query, "{}", threshold, market))

# ============================================================
# AirPods (category_id=3)
# ============================================================

AIRPODS = [
    ("AirPods 2",                  "AirPods 2",           3000, 5000),
    ("AirPods 3",                  "AirPods 3",           5000, 8000),
    ("AirPods 3 Lightning",        "AirPods 3 Lightning", 4500, 7000),
    ("AirPods Pro",                "AirPods Pro",         5000, 8000),
    ("AirPods Pro 2 USB-C",        "AirPods Pro 2",       8000, 12000),
    ("AirPods 4",                  "AirPods 4",           7000, 10000),
    ("AirPods 4 ANC",              "AirPods 4 ANC",       9000, 13000),
    ("AirPods Max",                "AirPods Max",         22000, 31000),
    ("AirPods Max 2 USB-C",        "AirPods Max 2",       32000, 43000),
]

for name, query, threshold, market in AIRPODS:
    ITEMS.append((3, name, query, "{}", threshold, market))

# ============================================================
# iPad (category_id=4)
# ============================================================

IPADS = [
    # iPad base
    ("iPad 8 2020 32GB Wi-Fi",    "iPad 8 32",    10000, 15000),
    ("iPad 8 2020 128GB Wi-Fi",   "iPad 8 128",   13000, 18000),
    ("iPad 9 2021 64GB Wi-Fi",    "iPad 9 64",    13000, 18000),
    ("iPad 9 2021 256GB Wi-Fi",   "iPad 9 256",   17000, 23000),
    ("iPad 10 2022 64GB Wi-Fi",   "iPad 10 64",   18000, 25000),
    ("iPad 10 2022 256GB Wi-Fi",  "iPad 10 256",  23000, 31000),

    # iPad mini
    ("iPad mini 6 2021 64GB Wi-Fi",   "iPad mini 6 64",   20000, 28000),
    ("iPad mini 6 2021 256GB Wi-Fi",  "iPad mini 6 256",  25000, 34000),
    ("iPad mini 7 2024 128GB Wi-Fi",  "iPad mini 7 128",  28000, 37000),
    ("iPad mini 7 2024 256GB Wi-Fi",  "iPad mini 7 256",  33000, 43000),
    ("iPad mini 7 2024 512GB Wi-Fi",  "iPad mini 7 512",  38000, 49000),

    # iPad Air
    ("iPad Air 4 2020 64GB Wi-Fi",    "iPad Air 4 64",    18000, 25000),
    ("iPad Air 4 2020 256GB Wi-Fi",   "iPad Air 4 256",   22000, 30000),
    ("iPad Air 5 M1 2022 64GB Wi-Fi",   "iPad Air 5 64",    24000, 33000),
    ("iPad Air 5 M1 2022 256GB Wi-Fi",  "iPad Air 5 256",   29000, 39000),
    ("iPad Air 11 M2 2024 128GB Wi-Fi", "iPad Air 11 M2 128",  33000, 43000),
    ("iPad Air 11 M2 2024 256GB Wi-Fi", "iPad Air 11 M2 256",  38000, 49000),
    ("iPad Air 11 M2 2024 512GB Wi-Fi", "iPad Air 11 M2 512",  44000, 56000),
    ("iPad Air 11 M2 2024 1TB Wi-Fi",   "iPad Air 11 M2 1TB",  52000, 66000),
    ("iPad Air 13 M2 2024 128GB Wi-Fi", "iPad Air 13 M2 128",  40000, 52000),
    ("iPad Air 13 M2 2024 256GB Wi-Fi", "iPad Air 13 M2 256",  46000, 59000),
    ("iPad Air 13 M2 2024 512GB Wi-Fi", "iPad Air 13 M2 512",  52000, 66000),
    ("iPad Air 13 M2 2024 1TB Wi-Fi",   "iPad Air 13 M2 1TB",  60000, 76000),

    # iPad Pro
    ("iPad Pro 11 M1 2021 128GB Wi-Fi",  "iPad Pro 11 M1 128",  28000, 37000),
    ("iPad Pro 11 M1 2021 256GB Wi-Fi",  "iPad Pro 11 M1 256",  32000, 42000),
    ("iPad Pro 11 M1 2021 512GB Wi-Fi",  "iPad Pro 11 M1 512",  37000, 48000),
    ("iPad Pro 11 M1 2021 1TB Wi-Fi",    "iPad Pro 11 M1 1TB",  43000, 56000),
    ("iPad Pro 12.9 M1 2021 128GB Wi-Fi", "iPad Pro 12.9 M1 128", 35000, 46000),
    ("iPad Pro 12.9 M1 2021 256GB Wi-Fi", "iPad Pro 12.9 M1 256", 40000, 52000),
    ("iPad Pro 12.9 M1 2021 512GB Wi-Fi", "iPad Pro 12.9 M1 512", 46000, 59000),
    ("iPad Pro 12.9 M1 2021 1TB Wi-Fi",   "iPad Pro 12.9 M1 1TB", 53000, 68000),
    ("iPad Pro 11 M2 2022 128GB Wi-Fi",  "iPad Pro 11 M2 128",  35000, 46000),
    ("iPad Pro 11 M2 2022 256GB Wi-Fi",  "iPad Pro 11 M2 256",  40000, 52000),
    ("iPad Pro 11 M2 2022 512GB Wi-Fi",  "iPad Pro 11 M2 512",  46000, 59000),
    ("iPad Pro 11 M2 2022 1TB Wi-Fi",    "iPad Pro 11 M2 1TB",  53000, 68000),
    ("iPad Pro 12.9 M2 2022 128GB Wi-Fi", "iPad Pro 12.9 M2 128", 43000, 56000),
    ("iPad Pro 12.9 M2 2022 256GB Wi-Fi", "iPad Pro 12.9 M2 256", 48000, 62000),
    ("iPad Pro 12.9 M2 2022 512GB Wi-Fi", "iPad Pro 12.9 M2 512", 55000, 70000),
    ("iPad Pro 12.9 M2 2022 1TB Wi-Fi",   "iPad Pro 12.9 M2 1TB", 63000, 80000),
    # M4 2024
    ("iPad Pro 11 M4 2024 256GB Wi-Fi",  "iPad Pro 11 M4 256",  48000, 62000),
    ("iPad Pro 11 M4 2024 512GB Wi-Fi",  "iPad Pro 11 M4 512",  55000, 70000),
    ("iPad Pro 11 M4 2024 1TB Wi-Fi",    "iPad Pro 11 M4 1TB",  65000, 82000),
    ("iPad Pro 13 M4 2024 256GB Wi-Fi",  "iPad Pro 13 M4 256",  58000, 74000),
    ("iPad Pro 13 M4 2024 512GB Wi-Fi",  "iPad Pro 13 M4 512",  66000, 83000),
    ("iPad Pro 13 M4 2024 1TB Wi-Fi",    "iPad Pro 13 M4 1TB",  77000, 97000),
]

for name, query, threshold, market in IPADS:
    ITEMS.append((4, name, query, "{}", threshold, market))


def main():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    # Clear existing items (but keep categories)
    cursor.execute("DELETE FROM seen_ads")
    cursor.execute("DELETE FROM items")
    db.commit()

    count = 0
    for cat_id, name, query, params, threshold, market in ITEMS:
        cursor.execute(
            "INSERT INTO items (category_id, name, search_query, avito_params, "
            "threshold_price, market_price, max_seller_items, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cat_id, name, query, params, threshold, market, 10, 1),
        )
        count += 1

    db.commit()
    db.close()

    print(f"Seeded {count} items:")
    iphones = sum(1 for i in ITEMS if i[0] == 1)
    macs = sum(1 for i in ITEMS if i[0] == 2)
    airpods = sum(1 for i in ITEMS if i[0] == 3)
    ipads = sum(1 for i in ITEMS if i[0] == 4)
    print(f"  iPhone: {iphones}")
    print(f"  MacBook: {macs}")
    print(f"  AirPods: {airpods}")
    print(f"  iPad: {ipads}")


if __name__ == "__main__":
    main()
