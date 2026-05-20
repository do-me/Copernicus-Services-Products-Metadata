#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "pyarrow",
#   "sentence-transformers",
#   "torch",
# ]
# ///
"""Discover Copernicus products with lexical retrieval plus Ettin reranking."""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf.runtime_version")

import pandas as pd


MODEL_NAME = "cross-encoder/ettin-reranker-17m-v1"
DEFAULT_CANDIDATE_K = 80
DEFAULT_TOP_K = 5
DEFAULT_BATCH_SIZE = 128
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "data",
    "dataset",
    "for",
    "from",
    "in",
    "into",
    "is",
    "need",
    "of",
    "on",
    "or",
    "product",
    "products",
    "the",
    "to",
    "with",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find Copernicus products matching a natural-language query.",
    )
    parser.add_argument("query", help="Natural-language data need")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    parser.add_argument(
        "--services",
        nargs="+",
        choices=[
            "atmosphere",
            "climate",
            "emergency",
            "emergency_activities_since_2012",
            "land",
            "marine",
        ],
        help="Optional service/table filter",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON records")
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Return lexical candidates without loading the Ettin reranker",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda", "mps"],
        help="Reranker backend. auto prefers CUDA, then Apple MPS, then CPU.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="CrossEncoder reranker batch size. Larger can improve throughput on GPU/MPS.",
    )
    return parser.parse_args()


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return str(value).strip()
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return ""
    return re.sub(r"\s+", " ", text)


def parse_literal(value: Any) -> Any:
    text = clean_value(value)
    if not text:
        return ""
    if text[0] not in "[{(":
        return text
    try:
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return text


def compact(value: Any, max_items: int = 12) -> str:
    value = parse_literal(value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, val in value.items():
            rendered = compact(val, max_items=4)
            if rendered:
                parts.append(f"{key}: {rendered}")
            if len(parts) >= max_items:
                break
        return "; ".join(parts)
    if isinstance(value, (list, tuple, set)):
        parts = [compact(item, max_items=4) for item in list(value)[:max_items]]
        return ", ".join(part for part in parts if part)
    return clean_value(value)


def first_nonempty(row: pd.Series, names: list[str]) -> str:
    for name in names:
        if name in row:
            value = clean_value(row.get(name))
            if value:
                return value
    return ""


def extract_link(row: pd.Series) -> str:
    direct = first_nonempty(row, ["url", "getURL", "@id", "omiFigureUrl", "thumbnailUrl"])
    if direct.startswith("http"):
        return direct
    links = parse_literal(row.get("links", ""))
    if isinstance(links, list):
        for rel in ("self", "root", "parent"):
            for item in links:
                if isinstance(item, dict) and item.get("rel") == rel:
                    href = clean_value(item.get("href"))
                    if href.startswith("http"):
                        return href
        for item in links:
            if isinstance(item, dict):
                href = clean_value(item.get("href"))
                if href.startswith("http"):
                    return href
    return direct


def service_from_path(path: Path) -> str:
    stem = path.stem.removeprefix("copernicus_")
    return stem


def load_tables(root: Path) -> list[tuple[str, pd.DataFrame]]:
    parquet_files = sorted((root / "outputs" / "parquet").glob("copernicus_*.parquet"))
    csv_files = sorted((root / "outputs" / "csv").glob("copernicus_*.csv"))
    files = csv_files or parquet_files
    if not files:
        raise FileNotFoundError("No outputs/parquet or outputs/csv metadata files found.")

    tables = []
    for path in files:
        service = service_from_path(path)
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        df = df.astype(object)
        tables.append((service, df.where(pd.notna(df), "")))
    return tables


def record_from_row(service: str, row: pd.Series, index: Any) -> dict[str, Any]:
    title = first_nonempty(row, ["title", "Title", "name", "id", "code", "catalogue"])
    product_id = first_nonempty(row, ["id", "UID", "getId", "code", "catalogue"])
    description = first_nonempty(
        row,
        ["description", "Description", "search_snippet", "past_items_search_text"],
    )
    variables = first_nonempty(row, ["mainVariables", "Subject", "keywords"])
    spatial = first_nonempty(
        row,
        [
            "areas",
            "taxonomy_use_case_spatial_coverage",
            "stacOrCswBbox",
            "extent",
            "centroid",
            "countries",
            "location",
        ],
    )
    temporal = first_nonempty(
        row,
        [
            "stacOrCswTbox",
            "tempExtentBegin",
            "tempExtentEnd",
            "tempResolutions",
            "activationTime",
            "lastUpdate",
            "Date",
            "EffectiveDate",
            "extent",
        ],
    )
    product_type = first_nonempty(
        row,
        ["processingLevel", "type", "Type", "portal_type", "category", "drmPhase"],
    )
    resolution = first_nonempty(row, ["geoResolution", "vertLevels", "numLayers"])
    license_value = first_nonempty(row, ["license"])
    provider = first_nonempty(row, ["providers", "Creator", "sources", "catalogue"])
    url = extract_link(row)

    facets = {
        "variables": compact(variables),
        "spatial": compact(spatial),
        "temporal": compact(temporal),
        "product_type": compact(product_type),
        "resolution": compact(resolution),
        "provider": compact(provider),
        "license": compact(license_value),
        "url": url,
    }
    document_parts = [
        f"Service: {service}",
        f"Title: {title}",
        f"ID: {product_id}",
        f"Description: {description}",
    ]
    document_parts.extend(
        f"{key.replace('_', ' ').title()}: {value}"
        for key, value in facets.items()
        if value and key != "url"
    )
    return {
        "service": service,
        "title": title,
        "id": product_id,
        "description": description,
        "url": url,
        "facets": facets,
        "source_row": clean_value(index),
        "document": "\n".join(part for part in document_parts if part.strip()),
    }


def build_records(tables: list[tuple[str, pd.DataFrame]], services: set[str] | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for service, df in tables:
        if services and service not in services:
            continue
        for index, row in df.iterrows():
            record = record_from_row(service, row, index)
            if record["title"] or record["description"]:
                records.append(record)
    return records


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_+-]{1,}", text.lower())
        if token not in STOPWORDS
    ]


def lexical_candidates(query: str, records: list[dict[str, Any]], candidate_k: int) -> list[dict[str, Any]]:
    query_terms = tokenize(query)
    if not query_terms:
        return records[:candidate_k]

    doc_terms = [Counter(tokenize(record["document"])) for record in records]
    doc_freq = Counter()
    for terms in doc_terms:
        doc_freq.update(terms.keys())

    total_docs = max(1, len(records))
    query_counter = Counter(query_terms)
    scored = []
    for record, terms in zip(records, doc_terms):
        score = 0.0
        length_norm = math.sqrt(sum(terms.values())) or 1.0
        for term, q_count in query_counter.items():
            if term not in terms:
                continue
            idf = math.log((1 + total_docs) / (1 + doc_freq[term])) + 1.0
            score += q_count * terms[term] * idf / length_norm
        title = record["title"].lower()
        score += sum(1.5 for term in query_counter if term in title)
        if score > 0:
            scored.append((score, record))

    if not scored:
        return records[:candidate_k]
    scored.sort(key=lambda item: item[0], reverse=True)
    candidates = []
    for lexical_score, record in scored[:candidate_k]:
        enriched = dict(record)
        enriched["lexical_score"] = lexical_score
        candidates.append(enriched)
    return candidates


def select_device(requested: str) -> str:
    import torch

    if requested != "auto":
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Requested --device cuda, but CUDA is not available.")
        if requested == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("Requested --device mps, but Apple MPS is not available.")
        return requested

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int,
    requested_device: str,
    batch_size: int,
) -> list[dict[str, Any]]:
    try:
        # Text-only CrossEncoder use does not need torchvision. Some local
        # torchvision builds segfault on import, so keep Transformers off it.
        sys.modules.setdefault("torchvision", None)
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Install with: "
            "uv run skills/copernicus-product-discovery/scripts/discover_products.py QUERY"
        ) from exc

    device = select_device(requested_device)
    model = CrossEncoder(MODEL_NAME, device=device)
    ranked = model.rank(
        query,
        [candidate["document"] for candidate in candidates],
        top_k=min(top_k, len(candidates)),
        batch_size=batch_size,
        return_documents=False,
    )
    results = []
    for item in ranked:
        candidate = dict(candidates[int(item["corpus_id"])])
        candidate["rerank_score"] = float(item["score"])
        candidate["rerank_device"] = device
        results.append(candidate)
    return results


def display_record(record: dict[str, Any], rank: int) -> str:
    facets = record["facets"]
    lines = [
        f"{rank}. {record['title']} [{record['service']}]",
    ]
    if record["id"]:
        lines.append(f"   id: {record['id']}")
    if "rerank_score" in record:
        lines.append(f"   ettin_score: {record['rerank_score']:.4f}")
        if record.get("rerank_device"):
            lines.append(f"   rerank_device: {record['rerank_device']}")
    elif "lexical_score" in record:
        lines.append(f"   lexical_score: {record['lexical_score']:.4f}")
    for key in ["variables", "spatial", "temporal", "product_type", "resolution", "provider", "license"]:
        value = facets.get(key)
        if value:
            lines.append(f"   {key}: {value[:450]}")
    if record["url"]:
        lines.append(f"   url: {record['url']}")
    if record["description"]:
        lines.append(f"   why: {record['description'][:700]}")
    return "\n".join(lines)


def slim_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": record["service"],
        "title": record["title"],
        "id": record["id"],
        "url": record["url"],
        "rerank_score": record.get("rerank_score"),
        "rerank_device": record.get("rerank_device"),
        "lexical_score": record.get("lexical_score"),
        "facets": record["facets"],
        "description": record["description"],
        "source_row": record["source_row"],
    }


def main() -> int:
    args = parse_args()
    tables = load_tables(repo_root())
    records = build_records(tables, set(args.services) if args.services else None)
    if not records:
        print("No product records matched the selected services.", file=sys.stderr)
        return 1

    candidates = lexical_candidates(args.query, records, max(args.top_k, args.candidate_k))
    if args.no_rerank:
        results = candidates[: args.top_k]
    else:
        results = rerank(args.query, candidates, args.top_k, args.device, args.batch_size)

    if args.json:
        print(json.dumps([slim_record(record) for record in results], indent=2, ensure_ascii=False))
    else:
        print(f"Query: {args.query}")
        print(f"Records searched: {len(records)} | Candidates reranked: {len(candidates)}")
        print()
        for rank, record in enumerate(results, start=1):
            print(display_record(record, rank))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
