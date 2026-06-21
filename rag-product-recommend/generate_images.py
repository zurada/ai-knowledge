#!/usr/bin/env python3
"""
Generates product images via Gemini 2.5 Flash Image (gemini-2.5-flash-image)
for each product in products_zurada.csv, in each product add a label on its container / package containing the product name and Zurada logo, produces shop/products.json with fake
prices, and saves images to shop/images/.
"""
import csv, json, os, time, random
from google import genai
from google.genai import types

INPUT = "products_zurada.csv"
IMAGES_DIR = "shop/images"
OUTPUT_JSON = "shop/products.json"
MODEL = "gemini-2.5-flash-image"

client = genai.Client(vertexai=True, api_key=os.environ["GEMINI_API_KEY"])

PRICE_SEEDS = {
    "chemia-samochodowa": (29, 89),
    "mycie-samochodow": (19, 59),
    "przemysl-farmaceutyczny": (80, 250),
    "przemysl-kosmetyczny": (60, 180),
    "horeca": (40, 140),
    "ekologiczne": (25, 75),
    "dozowniki": (35, 120),
    "default": (15, 65),
}


def fake_price(row):
    cats = row.get("categories", "")
    rng = random.Random(int(row["product_id"]) * 31337)
    for key, (lo, hi) in PRICE_SEEDS.items():
        if key in cats:
            base = rng.randint(lo * 100, hi * 100) / 100
            break
    else:
        base = rng.randint(1500, 6500) / 100
    # round to .99
    return round(base - 0.01, 2)


def image_prompt(row):
    title = row.get("title", "")
    product_name = row.get("product_name", "Zurada")
    short = row.get("short_description", "")[:120]
    cats = row.get("categories", "")
    context = "automotive" if "samochodow" in cats else "commercial cleaning"
    return (
        f"Professional product photograph of a {context} cleaning product bottle or container. "
        f"The packaging has a clean label printed on it. "
        f"The label clearly shows the brand name 'ZURADA' in large bold letters at the top, "
        f"and the product name '{product_name}' in smaller text below it. "
        f"The label also shows '{title}'. "
        f"The label has a green and white color scheme matching a professional cleaning brand. "
        f"{short}. "
        f"White studio background, soft box lighting, sharp focus, "
        f"commercial product photography style."
    )


def generate_image(row):
    pid = row["product_id"]
    out_path = os.path.join(IMAGES_DIR, f"{pid}.jpg")
    if os.path.exists(out_path):
        print(f"  [{pid}] already exists, skipping")
        return True

    prompt = image_prompt(row)
    for attempt in range(8):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            img_bytes = None
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    img_bytes = part.inline_data.data
                    break
            if not img_bytes:
                raise ValueError("No image in response")
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            print(f"  [{pid}] OK — {len(img_bytes)//1024}KB")
            return True
        except Exception as e:
            is_429 = "429" in str(e) or "quota" in str(e).lower() or "rate" in str(e).lower()
            wait = (60 if is_429 else 10) * (attempt + 1)
            print(f"  [{pid}] attempt {attempt+1}/8 failed ({'rate limit' if is_429 else 'error'}): {e}")
            print(f"  [{pid}] waiting {wait}s...")
            time.sleep(wait)
    return False


def main():
    with open(INPUT, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} products")
    os.makedirs(IMAGES_DIR, exist_ok=True)

    products = []
    for i, row in enumerate(rows, 1):
        pid = row["product_id"]
        print(f"[{i:>3}/{len(rows)}] {row['product_name']}")
        success = generate_image(row)
        products.append({
            "id": int(pid),
            "product_name": row["product_name"],
            "title": row["title"],
            "short_description": row["short_description"],
            "description": row["description"],
            "categories": [c.strip() for c in row["categories"].split(",")],
            "price": fake_price(row),
            "image": f"images/{pid}.jpg" if success else None,
        })
        time.sleep(15)  # 4 req/min to stay well under quota

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {OUTPUT_JSON} written with {len(products)} products.")


if __name__ == "__main__":
    main()
