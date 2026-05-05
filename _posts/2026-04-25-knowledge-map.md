---
title: "Knowledge Map"
date: 2026-04-25
---
# Knowledge Map

## The Data: 7 Largest Polish Companies

In this workshop we work on the financial statements of the 7 largest companies listed on the Warsaw Stock Exchange (GPW):

| Company | Sector |
|---|---|
| Orlen | Fuel / Energy |
| PKO Bank Polski | Banking |
| PGE | Energy |
| PZU | Insurance |
| KGHM | Copper / Raw Materials |
| Tauron | Energy |
| Enea | Energy |

Each of these companies publishes annual financial reports running several hundred pages long. For an analyst, that's a gold mine of knowledge. For an engineer — a technical challenge.

## The Full Pipeline

```
PDF (hundreds of pages)
   ↓ parsing (llama-parse)
Markdown (long, flowing)
   ↓ segmentation by structure
Chunks + tables
   ↓ table extraction
tables_raw.parquet  ← THIS IS WHERE WE START
```

## The Business Questions

Why does any of this matter? Because a real analyst needs to ask questions like:

- What are the main revenue streams, and what drives their volatility?
- What does the capital structure look like — how much equity versus debt?
- How have profitability ratios trended over the last few years?
- Does the company carry significant long-term liabilities?
- How does the company manage currency risk?

Without a Knowledge Map, answering any of these means opening a PDF, scrolling, hunting for the right table, cross-referencing another table — hours of manual work per company, per question.

What we're building is a system that takes a question, asks the Knowledge Map, and returns a precise answer with a source reference. No scrolling. No guessing.

## Write-Time Processing

Instead of doing expensive work on every query, we enrich the data with metadata once — upfront, properly.

**Per document:**

| Field | Description |
|---|---|
| `entity_name` | Company name |
| `entity_type` | Legal form (S.A., sp. z o.o., ...) |
| `period_start` / `period_end` | Reporting period |
| `document_category` | Type of report |
| `value_multiplier` | Scale of figures (thousands / millions PLN) |

**Per table:**

| Field | Description |
|---|---|
| `title` | Table name |
| `description` | What the table contains |
| `tags` | Topic labels for filtering |
| `questions` | List of questions this table can answer |
| `conclusions` | Key takeaways extracted from the data |
| `applications` | Practical use cases for an analyst |

This is the heart of the Knowledge Map approach: the heavy lifting happens at write time, so query time is fast and precise.
