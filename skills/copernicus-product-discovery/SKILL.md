---
name: copernicus-product-discovery
description: Use this skill to find the most suitable Copernicus Service product metadata records for a user's natural-language need, such as climate reanalysis, marine forecasts, land cover, atmosphere composition, flood/fire emergency mapping, variables, area, time range, resolution, or product type. It searches this repository's outputs and reranks candidates with cross-encoder/ettin-reranker-17m-v1.
---

# Copernicus Product Discovery

## Purpose

Find Copernicus products that best match a user's data need. Use the repository's local metadata under `outputs/` as the source of truth, not memory.

The default workflow is retrieve-then-rerank:

1. Build compact product documents from the metadata tables.
2. Retrieve a candidate set with fast lexical matching.
3. Rerank candidates with `cross-encoder/ettin-reranker-17m-v1`.
4. Return concise recommendations with service, title, id/code, why it fits, relevant variables/coverage/timing, and URL when available.

## Quick Start

From the repository root:

```bash
uv run skills/copernicus-product-discovery/scripts/discover_products.py \
  "daily sea surface temperature forecast for the Mediterranean" \
  --top-k 5
```

Use `uv` for all execution. The helper script declares its own dependencies with inline script metadata, so do not use bare `python` or `pip` unless the user explicitly asks.

If `uv` is not installed, stop and ask the user before installing it. Do not silently run an installer. Recommended install command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The first run resolves Python dependencies and downloads the Hugging Face model. If network access is unavailable, explain that reranking could not be executed and rerun with `--no-rerank` for lexical candidates.

## Ranking Guidance

Use Ettin scores as relevance scores for ordering, not calibrated probabilities. Larger scores are better.

Choose the retrieval mode before running:

- Use the default reranker path for open-ended natural-language discovery, mixed constraints, or when the user asks for the "best", "most suitable", or "recommended" product.
- Use `--no-rerank` for exact product titles, product ids/codes, explicit service-filtered lookups, or simple keyword checks where lexical matching is enough.
- If the first reranked run fails because model weights cannot be downloaded, rerun with `--no-rerank` and state that the result is lexical-only.

Prefer a smaller but precise recommendation set:

- `--top-k 3` for a direct user question.
- `--top-k 5` when the user likely needs alternatives across services.
- `--candidate-k 80` by default; raise to 150 for broad or ambiguous questions.
- `--batch-size 128` is the default reranker batch size; raise it only when benchmarking shows a local speedup without memory pressure.
- Use `--services marine climate atmosphere land emergency` to constrain only when the user explicitly names a service or the task clearly implies it.

Ask one clarifying question only when the top results expose a real ambiguity that changes the product choice, for example forecast vs historical/reanalysis, Europe vs global, or marine vs land hydrology.

## Output Expectations

Do not dump raw JSON unless requested. Present results as ranked recommendations:

- Product title and service.
- Product id/code when present.
- Match rationale grounded in metadata fields.
- Coverage details found in the record: variables, spatial coverage, temporal coverage, resolution, product type.
- URL/access link when present.
- Any caveat, such as "activity record, not a standing product catalog entry."

## Helper Script

Use `scripts/discover_products.py` for deterministic discovery. It reads these tables when present:

- `outputs/csv/copernicus_*.csv`
- fallback: `outputs/parquet/copernicus_*.parquet`

The script supports:

```bash
uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY
uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY --json
uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY --services marine climate
uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY --candidate-k 150 --top-k 8
uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY --device cpu
uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY --batch-size 256
```

## Model Notes

`cross-encoder/ettin-reranker-17m-v1` is a Sentence Transformers CrossEncoder for text ranking. It scores `(query, document)` pairs and supports long text inputs. This skill uses the 17M model because it is the leanest Ettin reranker while still providing cross-encoder ranking quality.

By default the helper uses `--device auto`: CUDA if available, then Apple MPS if available, then CPU. Override with `--device cpu`, `--device cuda`, or `--device mps` only for benchmarking or troubleshooting.
