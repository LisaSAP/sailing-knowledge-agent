#!/usr/bin/env python3
"""
build_kg.py — Build the sailing theory KG from source documents.

Always wipes existing data and rebuilds from scratch.

  PDF mode (default):
    python ingestion/build_kg.py
    python ingestion/build_kg.py --ontology knowledge/ontology.owl

  JSONL mode:
    python ingestion/build_kg.py --jsonl path/to/file1.jsonl path/to/file2.jsonl
    python ingestion/build_kg.py --jsonl path/to/*.jsonl --ontology knowledge/ontology.owl
"""
import asyncio, argparse, json, pathlib, os
from dotenv import load_dotenv

HERE = pathlib.Path(__file__).resolve().parent   # knowledgegraph/
ROOT = HERE.parent                               # sailing-knowledge-agent/
load_dotenv(ROOT / ".env", override=True)

for _var in ("LLM_MODEL", "LLM_ENDPOINT", "LLM_API_KEY",
             "EMBEDDING_MODEL", "EMBEDDING_PROVIDER",
             "EMBEDDING_ENDPOINT", "EMBEDDING_API_KEY", "EMBEDDING_DIMENSIONS",
             "EMBEDDING_BATCH_SIZE", "EMBEDDING_MAX_CONCURRENT_DATA_POINTS",
             "EMBEDDING_RATE_LIMIT_ENABLED", "EMBEDDING_RATE_LIMIT_REQUESTS", "EMBEDDING_RATE_LIMIT_INTERVAL",
             "LLM_RATE_LIMIT_ENABLED", "LLM_RATE_LIMIT_REQUESTS", "LLM_RATE_LIMIT_INTERVAL",
             "RAISE_INCREMENTAL_LOADING_ERRORS"):
    _val = os.environ.get(_var)
    if _val:
        os.environ[_var] = _val

import cognee
import cognee.shared.rate_limiting as _rl
from cognee.tasks.ingestion.data_item import DataItem
from cognee.modules.ontology.ontology_config import Config
from cognee.modules.ontology.rdf_xml.RDFLibOntologyResolver import RDFLibOntologyResolver
from cognee.modules.ontology.matching_strategies import FuzzyMatchingStrategy
from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import create_embedding_engine

def _int_env(key: str, default: int) -> int:
    v = os.environ.get(key, "")
    return int(v) if v.isdigit() else default

_batch_size = _int_env("EMBEDDING_BATCH_SIZE", 16)
_max_concurrent = _int_env("EMBEDDING_MAX_CONCURRENT_DATA_POINTS", 4)

# Push throttle values into the cached EmbeddingConfig object.
cognee.config.set_embedding_config({
    "embedding_batch_size": _batch_size,
    "embedding_max_concurrent_data_points": _max_concurrent,
    "embedding_rate_limit_enabled": os.environ.get("EMBEDDING_RATE_LIMIT_ENABLED", "false").lower() == "true",
    "embedding_rate_limit_requests": _int_env("EMBEDDING_RATE_LIMIT_REQUESTS", 100),
    "embedding_rate_limit_interval": _int_env("EMBEDDING_RATE_LIMIT_INTERVAL", 60),
})
# create_embedding_engine is also lru_cache'd — clear it so the next call
# picks up the new batch_size from the config we just mutated.
create_embedding_engine.cache_clear()
_rl._embedding_rate_limiter = None  # force rebuild with updated config
print(f"Embedding throttle: batch_size={_batch_size}, max_concurrent={_max_concurrent}")

SOURCES = HERE / "source"
SAILING_PROMPT = (HERE / "sailing_graph_prompt.md").read_text(encoding="utf-8")


def _data_items_from_jsonl(jsonl_paths: list[pathlib.Path]) -> list[DataItem]:
    """Build one DataItem per JSONL chunk, preserving pages/heading as external_metadata."""
    out = []
    for jsonl_path in jsonl_paths:
        stem = jsonl_path.stem
        chunk_count = 0
        with open(jsonl_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                heading = obj.get("heading") or ""
                text = obj.get("text") or ""
                block = f"{heading}\n{text}".strip() if heading else text.strip()
                if not block:
                    continue
                out.append(DataItem(
                    data=block,
                    label=f"{stem}_chunk_{i:04d}",
                    external_metadata={
                        "pages":   obj.get("pages") or [],
                        "heading": heading or None,
                        "source":  stem,
                        "chunk":   obj.get("chunk", i),
                    },
                ))
                chunk_count += 1
        print(f"  + {jsonl_path.name} → {chunk_count} chunks")
    return out


async def main(ontology_path: pathlib.Path | None, jsonl_paths: list[pathlib.Path]):
    print("Pruning existing data...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    if jsonl_paths:
        print(f"JSONL mode — converting {len(jsonl_paths)} file(s)...")
        items = _data_items_from_jsonl(jsonl_paths)
        print(f"\nIngesting {len(items)} chunks...")
        await cognee.add(items)
    else:
        source_paths = sorted([
            p.resolve() for p in SOURCES.glob("**/*")
            if p.suffix.lower() in {".pdf", ".txt", ".md"}
        ])
        if not source_paths:
            raise SystemExit(f"No documents found in {SOURCES}")
        print("PDF mode — scanning sources/...")
        for p in source_paths:
            print(f"  + {p.name}")
        print(f"\nIngesting {len(source_paths)} file(s)...")
        await cognee.add([str(p) for p in source_paths])

    if ontology_path:
        ontology_path = ontology_path.resolve()
        print(f"Cognifying with ontology: {ontology_path}")
        config: Config = {
            "ontology_config": {
                "ontology_resolver": RDFLibOntologyResolver(
                    ontology_file=str(ontology_path),
                    matching_strategy=FuzzyMatchingStrategy(cutoff=0.6),
                ),
                 "ontology_mode": "strict"
            }
        }
        await cognee.cognify(custom_prompt=SAILING_PROMPT, config=config)
    else:
        print("Cognifying without ontology (free extraction)...")
        await cognee.cognify(custom_prompt=SAILING_PROMPT)

    html_path = HERE / "output" / "graph.html"
    html_path.parent.mkdir(exist_ok=True)
    print(f"\nVisualizing graph → {html_path}")
    await cognee.visualize_graph(destination_file_path=str(html_path))

    print(f"\nDone. Open knowledgegraph/output/graph.html to inspect the KG.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the sailing theory KG.")
    parser.add_argument(
        "--ontology", type=pathlib.Path, default=None,
        help="Path to ontology.owl to ground extraction (optional)"
    )
    parser.add_argument(
        "--jsonl", type=pathlib.Path, nargs="+", default=None,
        help="Pre-chunked JSONL files to ingest instead of PDFs from sources/"
    )
    args = parser.parse_args()
    asyncio.run(main(args.ontology, args.jsonl or []))
