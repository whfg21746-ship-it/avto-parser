#!/usr/bin/env python3
"""Standalone script to discover Avito API parameters for product models.

Usage:
    python tools/discover_params.py                  # Discover for all predefined models
    python tools/discover_params.py --db             # Discover for all items in database
    python tools/discover_params.py --query "iPhone 15 Pro"  # Single model
    python tools/discover_params.py --db --update    # Discover and update DB

Output is saved to data/discovered_params.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from parser.param_discovery import ParamDiscovery  # noqa: E402
from parser.proxy_manager import ProxyManager  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("discover_params")

DEFAULT_MODELS = [
    "iPhone 11",
    "iPhone 11 Pro",
    "iPhone 11 Pro Max",
    "iPhone 12",
    "iPhone 12 Pro",
    "iPhone 12 Pro Max",
    "iPhone 13",
    "iPhone 13 Pro",
    "iPhone 13 Pro Max",
    "iPhone 14",
    "iPhone 14 Plus",
    "iPhone 14 Pro",
    "iPhone 14 Pro Max",
    "iPhone 15",
    "iPhone 15 Plus",
    "iPhone 15 Pro",
    "iPhone 15 Pro Max",
    "iPhone 16",
    "iPhone 16 Plus",
    "iPhone 16 Pro",
    "iPhone 16 Pro Max",
    "MacBook Air M1",
    "MacBook Air M2",
    "MacBook Air M3",
    "MacBook Pro 14 M1",
    "MacBook Pro 14 M2",
    "MacBook Pro 14 M3",
    "MacBook Pro 16 M1",
    "MacBook Pro 16 M2",
    "MacBook Pro 16 M3",
    "AirPods 2",
    "AirPods 3",
    "AirPods Pro",
    "AirPods Pro 2",
    "AirPods Max",
    "iPad Air M1",
    "iPad Air M2",
    "iPad Pro 11 M1",
    "iPad Pro 11 M2",
    "iPad Pro 12.9 M1",
    "iPad Pro 12.9 M2",
    "Apple Watch Series 7",
    "Apple Watch Series 8",
    "Apple Watch Series 9",
    "Apple Watch Ultra",
    "Apple Watch Ultra 2",
]

OUTPUT_PATH = Path("data/discovered_params.json")


def _print_result(model: str, result: dict) -> None:
    cat = result.get("category_id", "?")
    params_count = len(result.get("params", {}))
    via = result.get("discovered_via", "?")
    verified = result.get("verified", False)
    error = result.get("error")

    if error:
        print(f"  FAIL  {model}: {error}")
    else:
        v_mark = "OK" if verified else "UNVERIFIED"
        print(f"  [{v_mark}] {model}: categoryId={cat}, {params_count} params (via {via})")


async def progress_cb(current: int, total: int, model: str, result: dict) -> None:
    pct = current * 100 // total
    _print_result(model, result)
    if current % 10 == 0 or current == total:
        print(f"  --- Progress: {current}/{total} ({pct}%) ---")


async def discover_from_db(discovery: ParamDiscovery, update: bool) -> dict:
    """Discover params for all items in the database."""
    import aiosqlite

    db_path = config.DATABASE_PATH
    if not os.path.exists(db_path):
        logger.error("Database not found: %s", db_path)
        return {}

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT i.id, i.name, i.search_query, i.avito_params, "
            "c.avito_category_id "
            "FROM items i LEFT JOIN categories c ON i.category_id = c.id "
            "ORDER BY i.name"
        )
        rows = await cursor.fetchall()

    models = []
    item_map = {}  # model_name -> list of item rows
    for row in rows:
        row = dict(row)
        name = row["search_query"] or row["name"]
        if name not in item_map:
            item_map[name] = []
            models.append(name)
        item_map[name].append(row)

    print(f"\nDiscovering params for {len(models)} unique models from database...\n")
    results = await discovery.discover_batch(models, delay=3.0, progress_callback=progress_cb)

    if update:
        print("\nUpdating database...")
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            updated = 0
            for model_name, result in results.items():
                if result.get("error") or not result.get("category_id"):
                    continue

                params_json = json.dumps(result.get("params", {}))
                category_id = result["category_id"]

                for item_row in item_map.get(model_name, []):
                    await db.execute(
                        "UPDATE items SET avito_params = ? WHERE id = ?",
                        (params_json, item_row["id"]),
                    )
                    # Also update category's avito_category_id if different
                    if item_row.get("avito_category_id") != category_id:
                        await db.execute(
                            "UPDATE categories SET avito_category_id = ? "
                            "WHERE id = (SELECT category_id FROM items WHERE id = ?)",
                            (category_id, item_row["id"]),
                        )
                    updated += 1

            await db.commit()
            print(f"Updated {updated} items in database.")

    return results


async def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Avito API parameters")
    parser.add_argument(
        "--query", "-q",
        help="Discover params for a single model name",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="Discover params for all items in the database",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update database with discovered params (requires --db)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay between requests in seconds (default: 3)",
    )
    args = parser.parse_args()

    # Load proxies
    proxy_manager = ProxyManager(config.PROXY_LIST)

    # Also try loading proxies from DB
    if not proxy_manager.has_proxies:
        try:
            import aiosqlite
            db_path = config.DATABASE_PATH
            if os.path.exists(db_path):
                async with aiosqlite.connect(db_path) as db:
                    cursor = await db.execute(
                        "SELECT value FROM settings WHERE key = 'proxy_list'"
                    )
                    row = await cursor.fetchone()
                    if row and row[0]:
                        proxies = json.loads(row[0])
                        if proxies:
                            proxy_manager = ProxyManager(proxies)
                            print(f"Loaded {len(proxies)} proxies from database")
        except Exception:
            pass

    discovery = ParamDiscovery(proxy_manager)

    try:
        if args.query:
            # Single model
            print(f"\nDiscovering params for: {args.query}\n")
            result = await discovery.discover_and_verify(args.query)
            _print_result(args.query, result)

            # Print detailed info
            print(f"\n  Category ID: {result.get('category_id')}")
            print(f"  Params: {json.dumps(result.get('params', {}), indent=2)}")
            print(f"  Method: {result.get('discovered_via')}")
            print(f"  Verified: {result.get('verified')}")

            results = {args.query: result}

        elif args.db:
            results = await discover_from_db(discovery, args.update)

        else:
            # Default models list
            print(f"\nDiscovering params for {len(DEFAULT_MODELS)} default models...\n")
            results = await discovery.discover_batch(
                DEFAULT_MODELS, delay=args.delay, progress_callback=progress_cb
            )

        # Save results (without raw_response to keep file manageable)
        clean_results = {}
        for model, result in results.items():
            clean = {k: v for k, v in result.items() if k != "raw_response"}
            clean_results[model] = clean

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
            "discovered": sum(
                1 for r in results.values()
                if r.get("category_id") and not r.get("error")
            ),
            "verified": sum(1 for r in results.values() if r.get("verified")),
            "failed": sum(1 for r in results.values() if r.get("error")),
            "results": clean_results,
        }

        OUTPUT_PATH.write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nResults saved to {OUTPUT_PATH}")

        # Summary
        print(f"\n{'='*50}")
        print(f"SUMMARY:")
        print(f"  Total models:  {output_data['total']}")
        print(f"  Discovered:    {output_data['discovered']}")
        print(f"  Verified:      {output_data['verified']}")
        print(f"  Failed:        {output_data['failed']}")
        print(f"{'='*50}")

    finally:
        await discovery.close()


if __name__ == "__main__":
    asyncio.run(main())
