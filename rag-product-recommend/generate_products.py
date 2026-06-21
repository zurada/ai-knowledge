#!/usr/bin/env python3
import csv, json, re, time, sys, io
from openai import OpenAI

INPUT = "products_checked.csv"
OUTPUT = "products_zurada.csv"
LIMIT = 100
MODEL = "gpt-5.5"

client = OpenAI()


def generate_unique_names(products):
    """Single call — model sees all products at once and must produce unique names."""
    lines = []
    for i, row in enumerate(products):
        cat = row.get("categories", "").strip()
        short = row.get("short_description", "").strip()[:200]
        lines.append(f'{i}. kategoria: {cat} | opis: {short}')

    prompt = (
        "Jesteś copywriterem dla sklepu 'Zurada Shop'. "
        "Dla każdego z poniższych produktów stwórz UNIKALNĄ nazwę handlową zawierającą słowo 'Zurada'. "
        "Format: przymiotnik/rzeczownik + Zurada + opcjonalny rzeczownik, np. 'Błysk Zurada', 'Zurada Moc', 'Kwasny Zurada Odtłuszczacz'. "
        "Każda nazwa MUSI być inna — żadnych powtórzeń. Odpowiedz TYLKO jako JSON: "
        '{\"names\": [\"nazwa0\", \"nazwa1\", ...]}\n\n'
        + "\n".join(lines)
    )

    response = client.chat.completions.create(
        model=MODEL,
        max_completion_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)["names"]


def make_prompt(row):
    categories = row.get("categories", "").strip()
    short_desc = row.get("short_description", "").strip()[:600]
    tech_sheet = row.get("technical_sheet", "").strip()[:300]
    return f"""You are writing product listings for "Zurada Shop", a generic cleaning supplies store.

Product context (use for understanding function only — do NOT copy brand names, do NOT use "eco", "ecoshine", "ECO", or any trademarked terms):
- Category: {categories}
- What it does: {short_desc}
- Technical notes: {tech_sheet}

Create a completely new, generic product listing:
1. PRODUCT_NAME: A catchy Polish brand-style name that always contains the word "Zurada". Format examples: "Kwasny Zurada", "Zurada Błysk", "Eco Zurada Shine", "Zurada Moc". Should sound like a real product name, 2-4 words max.
2. TITLE: 2-6 word generic product name based on function. No brand names. No "ECO" prefix. Must differ significantly from original.
3. SHORT_DESCRIPTION: One sentence, max 120 characters, describing what the product does.
4. DESCRIPTION: 3-4 sentences covering uses, benefits, and how to apply/use it.
Use Polish language for all.
Return ONLY valid JSON, no markdown, no explanation:
{{"product_name": "...", "title": "...", "short_description": "...", "description": "..."}}"""


def parse_result(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def main():
    # Load 100 OK products
    products = []
    with open(INPUT, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("link_status", "").strip() == "OK":
                products.append(row)
                if len(products) >= LIMIT:
                    break

    print(f"Loaded {len(products)} OK products")

    # Build JSONL batch file in memory
    lines = []
    for row in products:
        pid = str(row["product_id"])
        request = {
            "custom_id": pid,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": MODEL,
                "max_completion_tokens": 500,
                "messages": [{"role": "user", "content": make_prompt(row)}],
            },
        }
        lines.append(json.dumps(request, ensure_ascii=False))

    jsonl_bytes = "\n".join(lines).encode("utf-8")

    print(f"Uploading batch file ({len(lines)} requests)...")
    upload = client.files.create(
        file=("batch_input.jsonl", io.BytesIO(jsonl_bytes), "application/jsonl"),
        purpose="batch",
    )

    print(f"Creating batch (file_id={upload.id})...")
    batch = client.batches.create(
        input_file_id=upload.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    batch_id = batch.id
    print(f"Batch ID: {batch_id}")

    # Poll until done
    while True:
        batch = client.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(
            f"  Status: {batch.status} | "
            f"total={counts.total} completed={counts.completed} failed={counts.failed}",
            flush=True,
        )
        if batch.status in ("completed", "failed", "expired", "cancelled"):
            break
        time.sleep(30)

    if batch.status != "completed":
        print(f"Batch ended with status: {batch.status}", file=sys.stderr)
        if batch.error_file_id:
            err_raw = client.files.content(batch.error_file_id).content
            for line in err_raw.decode("utf-8").splitlines()[:5]:
                print(f"  Error sample: {line}", file=sys.stderr)
        sys.exit(1)

    if not batch.output_file_id:
        print("No output file — all requests failed.", file=sys.stderr)
        if batch.error_file_id:
            err_raw = client.files.content(batch.error_file_id).content
            for line in err_raw.decode("utf-8").splitlines()[:5]:
                print(f"  Error: {line}", file=sys.stderr)
        sys.exit(1)

    # Download and parse results
    results_by_id = {}
    raw = client.files.content(batch.output_file_id).content
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        pid = item["custom_id"]
        try:
            text = item["response"]["body"]["choices"][0]["message"]["content"]
            results_by_id[pid] = parse_result(text)
        except Exception as e:
            print(f"  Parse error for {pid}: {e}", file=sys.stderr)

    print(f"Got {len(results_by_id)} successful results")

    # Write output (no URL column)
    out_fields = ["product_id", "product_name", "title", "short_description", "description", "categories"]
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for row in products:
            pid = str(row["product_id"])
            r = results_by_id.get(pid, {})
            writer.writerow({
                "product_id": pid,
                "product_name": r.get("product_name", "Zurada"),
                "title": r.get("title", "Generic Cleaning Product"),
                "short_description": r.get("short_description", ""),
                "description": r.get("description", ""),
                "categories": row.get("categories", ""),
            })

    print(f"Done! Written to {OUTPUT}")


if __name__ == "__main__":
    main()
