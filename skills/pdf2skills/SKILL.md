---
name: pdf2skills
description: Convert any PDF document (books, manuals, reports, specs) into structured Claude Code Skills via AI semantic analysis. Use when the user wants to transform a PDF into callable skill packs. TRIGGER when user says "convert PDF to skills", "extract skills from book", "pdf2skills", or provides a PDF path with intent to create skills.
---

# PDF to Skills Pipeline

Convert PDF documents into structured, callable Claude Code Skills through a multi-stage AI pipeline.

## Prerequisites

Python dependencies must be installed:
```bash
pip install spacy jieba numpy scikit-learn PyPDF2
python -m spacy download en_core_web_sm
```

## Pipeline Overview

```
PDF → Markdown → Chunks → Density Scores → SKUs → Buckets → Skills → Router
```

## Execution Workflow

### Step 1: Setup and PDF Parsing

1. Get the PDF file path from the user
2. Create output directory: `{pdf_name}_output/`
3. Determine page count:
   ```bash
   python -m src.cli page-count "{pdf_path}"
   ```
4. Read the PDF using the Read tool (max 20 pages per call):
   - For each page range, use `Read` with the `pages` parameter
   - Combine all page content into structured Markdown
5. Write the combined Markdown to `{output_dir}/full.md`

### Step 2: Semantic Chunking

Dispatch a SubAgent with the chunking prompt:
- Read `skills/pdf2skills/prompts/chunking.md` for the full prompt
- Input: the full Markdown content
- Output: `chunks_index.json` + individual chunk files in `{output_dir}/chunks/`

The SubAgent analyzes document structure (headers, topics, logical boundaries) and outputs chunking anchor points. Each chunk should be:
- Self-contained and coherent
- Under 30,000 tokens
- Preserving the document's logical hierarchy

### Step 3: Density Analysis

1. Run NLP density scoring (Python):
   ```bash
   python -m src.cli density "{output_dir}/chunks" -o "{output_dir}/density_scores.json"
   ```
   This computes three NLP features per chunk: S_logic, S_entity, S_struct.
   It also selects calibration samples.

2. Dispatch a SubAgent for LLM calibration:
   - Read `skills/pdf2skills/prompts/density-calibration.md` for the prompt
   - The SubAgent scores sampled chunks (0-100 gold score)
   - Write gold scores to `{output_dir}/gold_scores.json`

3. Apply calibration (Python):
   ```bash
   python -m src.cli calibrate "{output_dir}/density_scores.json" "{output_dir}/gold_scores.json"
   ```

### Step 4: SKU Extraction

Dispatch SubAgent(s) with the SKU extraction prompt:
- Read `skills/pdf2skills/prompts/sku-extraction.md` for the full prompt
- Process high-density chunks (top 80% by final_score)
- For large books, dispatch multiple SubAgents in parallel (one per chunk group)
- Output: individual SKU JSON files in `{output_dir}/skus/skus/` + `skus_index.json`

### Step 5: Knowledge Fusion

1. Compute similarity and bucket SKUs (Python):
   ```bash
   python -m src.cli similarity "{output_dir}/skus" -t 0.5
   ```

2. Dispatch SubAgent for tag normalization:
   - Read `skills/pdf2skills/prompts/knowledge-fusion.md` for the prompt
   - Normalize applicable_objects and domain_tags across all SKUs
   - Update SKU files with normalized tags

### Step 6: Skill Generation

Dispatch SubAgent(s) with the skill generation prompt:
- Read `skills/pdf2skills/prompts/skill-generation.md` for the full prompt
- Process one bucket at a time
- For large buckets (>15 SKUs), split into batches
- Output: skill directories under `{output_dir}/generated_skills/`
- Each skill has: `SKILL.md` + optional `references/` folder

### Step 7: Router Generation

Dispatch SubAgent with the router generation prompt:
- Read `skills/pdf2skills/prompts/router-generation.md` for the prompt
- Input: all generated skill metadata
- Output: `{output_dir}/generated_skills/index.md`

### Step 8: Glossary Extraction

Dispatch SubAgent with the glossary extraction prompt:
- Read `skills/pdf2skills/prompts/glossary-extraction.md` for the prompt
- Input: all SKU files
- Output: `{output_dir}/glossary.json`

## Output Structure

```
{pdf_name}_output/
├── full.md                          # Extracted Markdown
├── chunks/                          # Chunked documents
│   ├── chunks_index.json
│   └── chunk_*.md
├── density_scores.json              # Semantic density analysis
├── skus/                            # Knowledge units
│   ├── skus_index.json
│   ├── buckets.json
│   └── skus/
│       └── {uuid}.json
└── generated_skills/                # Final Claude Code Skills
    ├── index.md                     # Skill navigation router
    ├── generation_metadata.json
    └── {skill-name}/
        ├── SKILL.md
        └── references/
            └── details.md
```

## Post-Pipeline

After generation, inform the user:
1. Skills are in `{output_dir}/generated_skills/`
2. To install: copy skill folders to `~/.claude/skills/` or project `.claude/skills/`
3. Each skill can be invoked via `/{skill-name}` in Claude Code

## Error Recovery

- If any stage fails, note which stage failed
- Re-run from the failed stage (earlier stages are idempotent)
- For large PDFs (>100 pages), recommend splitting with PyPDF2 first
