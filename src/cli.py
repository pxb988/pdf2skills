"""CLI entry point for pdf2skills Python helpers.

Called by the Claude Code Skill via the Bash tool.
Each subcommand handles one compute-intensive task.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_parse_pdf(args: argparse.Namespace) -> None:
    """Parse PDF to Markdown."""
    from .pipeline.config import load_config

    config = load_config(Path(args.env) if args.env else None)
    pdf_path = Path(args.pdf)
    output_dir = Path(args.output)

    if config.pdf_parser == "mineru" and config.mineru_api_key:
        from .pdf_parser.mineru_parser import MineruParser

        parser = MineruParser(config.mineru_api_key, config.mineru_base_url)
    else:
        from .pdf_parser.claude_parser import ClaudeParser

        parser = ClaudeParser()

    markdown = parser.parse(pdf_path, output_dir)
    print(json.dumps({
        "status": "ok",
        "output": str(output_dir / "full.md"),
        "chars": len(markdown),
    }))


def cmd_density(args: argparse.Namespace) -> None:
    """Compute NLP density scores for chunks."""
    from .nlp.density import DensityAnalyzer

    chunks_dir = Path(args.chunks_dir)
    index_path = chunks_dir / "chunks_index.json"

    if not index_path.exists():
        print(json.dumps({"error": f"chunks_index.json not found in {chunks_dir}"}))
        sys.exit(1)

    index = json.loads(index_path.read_text(encoding="utf-8"))

    # Load chunk contents
    chunks = []
    for i, entry in enumerate(index):
        chunk_file = chunks_dir / entry["file"]
        content = chunk_file.read_text(encoding="utf-8")
        # Strip YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()
        chunks.append({
            "id": entry["id"],
            "title": entry["title"],
            "content": content,
            "parent_path": entry.get("parent_path", []),
            "book_index": entry.get("book_index", i),
        })

    analyzer = DensityAnalyzer()
    scores = analyzer.score_chunks(chunks)

    # Compute initial scores (equal weights)
    analyzer.apply_weights(scores)

    # Select calibration samples
    samples = analyzer.select_calibration_samples(scores, n=int(args.samples))

    # Output results
    output_path = Path(args.output) if args.output else chunks_dir.parent / "density_scores.json"
    results = analyzer.export_results(scores)
    results["calibration_samples"] = [s.chunk_id for s in samples]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "output": str(output_path),
        "total_chunks": len(scores),
        "calibration_sample_ids": [s.chunk_id for s in samples],
    }))


def cmd_calibrate(args: argparse.Namespace) -> None:
    """Apply LLM gold scores and recalibrate weights."""
    from .nlp.density import DensityAnalyzer, ChunkScore

    density_path = Path(args.density_file)
    gold_path = Path(args.gold_scores)

    density_data = json.loads(density_path.read_text(encoding="utf-8"))
    gold_scores = json.loads(gold_path.read_text(encoding="utf-8"))

    # Reconstruct ChunkScores
    scores = []
    for c in density_data["chunks"]:
        scores.append(ChunkScore(
            chunk_id=c["chunk_id"],
            title=c["title"],
            parent_path=c["parent_path"],
            book_index=c["book_index"],
            s_logic=c["s_logic"],
            s_entity=c["s_entity"],
            s_struct=c["s_struct"],
            content_preview=c.get("content_preview", ""),
            token_count=c.get("token_count", 0),
        ))

    analyzer = DensityAnalyzer()
    weights = analyzer.calibrate_weights(scores, gold_scores)
    analyzer.apply_weights(scores)

    results = analyzer.export_results(scores)
    density_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"status": "ok", "weights": weights}))


def cmd_similarity(args: argparse.Namespace) -> None:
    """Compute similarity and bucket SKUs."""
    from .nlp.similarity import find_buckets

    skus_dir = Path(args.skus_dir)
    index_path = skus_dir / "skus_index.json"

    if not index_path.exists():
        print(json.dumps({"error": f"skus_index.json not found in {skus_dir}"}))
        sys.exit(1)

    index = json.loads(index_path.read_text(encoding="utf-8"))

    # Build text representations for each SKU
    texts, ids = [], []
    for entry in index:
        sku_file = skus_dir / "skus" / f"{entry['uuid']}.json"
        if sku_file.exists():
            sku = json.loads(sku_file.read_text(encoding="utf-8"))
            # Create text summary for similarity
            parts = [
                sku.get("metadata", {}).get("name", ""),
                " ".join(sku.get("context", {}).get("applicable_objects", [])),
                " ".join(sku.get("custom_attributes", {}).get("domain_tags", [])),
                sku.get("core_logic", {}).get("execution_body", ""),
            ]
            texts.append(" ".join(parts))
            ids.append(entry["uuid"])

    threshold = float(args.threshold)
    buckets = find_buckets(texts, ids, threshold=threshold)

    output_path = Path(args.output) if args.output else skus_dir / "buckets.json"
    bucket_data = {
        "threshold": threshold,
        "total_skus": len(ids),
        "total_buckets": len(buckets),
        "buckets": [
            {"bucket_id": f"bucket_{i}", "sku_uuids": group}
            for i, group in enumerate(buckets)
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bucket_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "output": str(output_path),
        "total_buckets": len(buckets),
    }))


def cmd_page_count(args: argparse.Namespace) -> None:
    """Get PDF page count."""
    from .pdf_parser.claude_parser import ClaudeParser

    count = ClaudeParser.page_count(Path(args.pdf))
    print(json.dumps({"pages": count}))


def main() -> None:
    parser = argparse.ArgumentParser(prog="pdf2skills", description="pdf2skills Python helpers")
    parser.add_argument("--env", help="Path to .env file")
    sub = parser.add_subparsers(dest="command", required=True)

    # parse-pdf
    p_parse = sub.add_parser("parse-pdf", help="Parse PDF to Markdown")
    p_parse.add_argument("pdf", help="Path to PDF file")
    p_parse.add_argument("-o", "--output", required=True, help="Output directory")

    # density
    p_density = sub.add_parser("density", help="Compute NLP density scores")
    p_density.add_argument("chunks_dir", help="Directory with chunks_index.json")
    p_density.add_argument("-o", "--output", help="Output JSON path")
    p_density.add_argument("-n", "--samples", default="15", help="Number of calibration samples")

    # calibrate
    p_cal = sub.add_parser("calibrate", help="Apply gold scores and recalibrate")
    p_cal.add_argument("density_file", help="Path to density_scores.json")
    p_cal.add_argument("gold_scores", help="Path to gold_scores.json (chunk_id -> score)")

    # similarity
    p_sim = sub.add_parser("similarity", help="Compute SKU similarity and bucket")
    p_sim.add_argument("skus_dir", help="Directory with skus_index.json")
    p_sim.add_argument("-o", "--output", help="Output JSON path")
    p_sim.add_argument("-t", "--threshold", default="0.5", help="Bucket threshold")

    # page-count
    p_pages = sub.add_parser("page-count", help="Get PDF page count")
    p_pages.add_argument("pdf", help="Path to PDF file")

    args = parser.parse_args()
    handlers = {
        "parse-pdf": cmd_parse_pdf,
        "density": cmd_density,
        "calibrate": cmd_calibrate,
        "similarity": cmd_similarity,
        "page-count": cmd_page_count,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
