#!/usr/bin/env python3
"""Rebuilds shop/products.json from products_zurada.csv + existing images."""
import csv, json, os, random

INPUT = "products_zurada.csv"
IMAGES_DIR = "shop/images"
OUTPUT_JSON = "shop/products.json"

PRICE_SEEDS = {
    "chemia-samochodowa": (29, 89),
    "mycie-samochodow": (19, 59),
    "przemysl-farmaceutyczny": (80, 250),
    "przemysl-kosmetyczny": (60, 180),
    "horeca": (40, 140),
    "ekologiczne": (25, 75),
    "dozowniki": (35, 120),
}

def fake_price(row):
    cats = row.get("categories", "")
    rng = random.Random(int(row["product_id"]) * 31337)
    for key, (lo, hi) in PRICE_SEEDS.items():
        if key in cats:
            return round(rng.randint(lo * 100, hi * 100) / 100 - 0.01, 2)
    return round(rng.randint(1500, 6500) / 100 - 0.01, 2)

with open(INPUT, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

products = []
missing = []
for row in rows:
    pid = row["product_id"]
    img_path = os.path.join(IMAGES_DIR, f"{pid}.jpg")
    has_image = os.path.exists(img_path)
    if not has_image:
        missing.append(pid)
    products.append({
        "id": int(pid),
        "product_name": row["product_name"],
        "title": row["title"],
        "short_description": row["short_description"],
        "description": row.get("content_encoded") or row.get("short_description", ""),
        "categories": [c.strip() for c in row["categories"].split(",")],
        "price": fake_price(row),
        "image": f"images/{pid}.jpg" if has_image else None,
    })

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Written {len(products)} products to {OUTPUT_JSON}")
if missing:
    print(f"Missing images for product IDs: {', '.join(missing)}")
else:
    print("All images present!")
