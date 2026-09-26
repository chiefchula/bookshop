"""
Import zabach_items.csv into the bookshop database.

Usage:
    export FLASK_APP=app.py
    python scripts/seed_items.py zabach_items.csv

Behaviour:
- Creates categories if missing
- Creates items with is_catalogued=True, is_stocked=False, quantity=0
- If an item with the same title+category exists, updates price/brand/unit
  but does NOT touch quantity
- Prints a summary at the end
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app
from models import db, Item, Category


def get_or_create_category(name: str, cache: dict) -> Category:
    key = name.strip().upper()
    if key in cache:
        return cache[key]
    cat = Category.query.filter(func_upper(Category.name) == key).first()
    if not cat:
        cat = Category(name=name.strip())
        db.session.add(cat)
        db.session.flush()
    cache[key] = cat
    return cat


def func_upper(col):
    from sqlalchemy import func
    return func.upper(col)


def main(csv_path: str):
    created_items = 0
    updated_items = 0
    skipped = 0

    cat_cache: dict = {}

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for lineno, row in enumerate(reader, start=2):
            title = (row.get('title') or '').strip()
            category_name = (row.get('category') or '').strip()
            brand = (row.get('brand') or '').strip() or None
            unit = (row.get('unit') or 'EACH').strip().upper()
            try:
                price = float(row.get('price') or 0)
            except ValueError:
                print(f"Line {lineno}: bad price {row.get('price')!r} — skipping")
                skipped += 1
                continue

            if not title or not category_name:
                skipped += 1
                continue

            category = get_or_create_category(category_name, cat_cache)

            # Match by title + category (case-insensitive title)
            existing = (Item.query
                        .filter(func_upper(Item.title) == title.upper(),
                                Item.category_id == category.id)
                        .first())

            if existing:
                existing.brand = brand
                existing.unit = unit
                existing.price = price
                existing.is_catalogued = True
                updated_items += 1
            else:
                item = Item(
                    title=title,
                    category_id=category.id,
                    brand=brand,
                    unit=unit,
                    price=price,
                    cost_price=0,
                    quantity=0,
                    reorder_level=5,
                    is_catalogued=True,
                    is_stocked=False,
                )
                db.session.add(item)
                created_items += 1

        db.session.commit()

    print(f"Done. Created: {created_items}, Updated: {updated_items}, Skipped: {skipped}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_items.py <csv_path>")
        sys.exit(1)
    with app.app_context():
        main(sys.argv[1])