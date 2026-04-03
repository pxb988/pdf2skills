---
name: pdf2skills
description: Convert any PDF or Markdown document (professional books, operation manuals, industry reports, technical specifications, textbooks, standards documents) into a complete set of structured Claude Code Skills through AI semantic analysis. The output is a ready-to-install skill pack that can be directly invoked in Claude Code. Use this skill whenever the user wants to extract knowledge from a PDF or Markdown document and turn it into reusable skills, even if they don't say "pdf2skills" explicitly. Trigger for phrases like "convert this book to skills", "extract skills from PDF", "turn this manual into something Claude can use", "make skills from this document", "I have a PDF or Markdown file I want to learn from", or any request involving a PDF/Markdown path combined with intent to create callable knowledge. Also trigger when the user provides a PDF or Markdown file and asks to "break it down", "structure the knowledge", or "make it actionable".
---

# PDF / Markdown to Skills Pipeline

Transform PDF or Markdown documents into structured, callable Claude Code Skills through a multi-stage pipeline that combines Python NLP computation with AI semantic analysis.

## How It Works

The pipeline reads a PDF, breaks it into semantically coherent chunks, identifies high-value knowledge regions, extracts structured knowledge units, deduplicates them, and converts them into Claude Code Skill format.

```
PDF → Markdown → Chunks → Density → SKUs → Buckets → Skills → Optimize → Router
      (Read)    (Agent)  (Py+Agent) (Agent) (Python) (Agent)  (skill-creator) (Agent)
  ↑
  └─ Markdown input skips this step
```

## Before You Start

The Python helpers need a few dependencies. Check if they're installed, and if not, set them up. Python 3.11+ is supported, and 3.12 is recommended:

```bash
cd {project_root}
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install spacy jieba numpy scikit-learn PyPDF2 python-dotenv requests anthropic 2>/dev/null
python -m spacy download en_core_web_sm 2>/dev/null
```

`{project_root}` is the directory containing this skill's `src/` folder (find it by locating `src/cli.py`).

### Configuration (Optional)

PDF parsing defaults to Claude Code's Read tool (zero config). For better quality on complex PDFs, configure an external LLM provider:

1. Copy `.env.example` to `.pdf2skills/.env` in the project root (or `~/.pdf2skills/.env` for user-level).
2. Set `LLM_PROVIDER` to your provider (e.g., `deepseek`, `openai`, `qwen`).
3. Set the corresponding `{PROVIDER}_API_KEY`.
4. The pipeline will auto-detect and use the LLM for PDF→Markdown conversion.

Supported providers: OpenAI, Anthropic, Google, DeepSeek, 智谱 GLM, Qwen, SiliconFlow, or any OpenAI-compatible endpoint (use `custom`).

## Execution Workflow

Throughout execution, keep the user informed of progress — this is a long-running pipeline. Report which step you're on and what percentage of the work is done.

### Step 1: Setup and Input Reading

1. Confirm the input path with the user. Resolve it to an absolute path.
2. Locate the project root (the directory containing `src/cli.py`). All `python -m src.cli` commands must run from this directory.
3. Create the output directory next to the input file: `{input_stem}_output/`
4. **If the input is a Markdown file (`.md`):**
   - Copy or symlink it to `{output_dir}/full.md` (or treat it directly as `full.md`).
   - Tell the user: "Markdown input detected — skipping PDF extraction, proceeding to chunking."
   - Skip to Step 2.
5. **If the input is a PDF:**
   - Get the page count:
     ```bash
     cd {project_root} && source .venv/bin/activate && python -m src.cli page-count "{pdf_path}"
     ```
   - Read the PDF page by page using the Read tool with the `pages` parameter (max 20 pages per call). Combine all content into a single Markdown document.
   - Write the result to `{output_dir}/full.md`.
   - Tell the user: "PDF read complete — {N} pages extracted."

### Step 2: Semantic Chunking

Read the prompt template at `{project_root}/.claude/skills/pdf2skills/prompts/chunking.md`, then dispatch an Agent to perform the chunking.

Provide the Agent with:
- The full Markdown content (or path to `full.md`)
- The output directory `{output_dir}/chunks/`
- Target: each chunk under 30,000 tokens, self-contained and coherent

Expected output: `{output_dir}/chunks/chunks_index.json` + individual `chunk_*.md` files.

Tell the user: "Chunking complete — {N} chunks created."

### Step 3: Density Analysis

This step identifies which chunks contain the most actionable, high-value knowledge.

**3a. NLP scoring** (Python — fast, local):
```bash
cd {project_root} && source .venv/bin/activate && python -m src.cli density "{output_dir}/chunks" -o "{output_dir}/density_scores.json"
```
The output includes `calibration_sample_ids` — a list of chunk IDs selected for LLM calibration.

**3b. LLM calibration** (Agent):
Read `{project_root}/.claude/skills/pdf2skills/prompts/density-calibration.md`. Dispatch an Agent to score each calibration sample chunk (0–100). Write scores to `{output_dir}/gold_scores.json` as `{"chunk_id": score, ...}`.

**3c. Apply calibration** (Python):
```bash
cd {project_root} && source .venv/bin/activate && python -m src.cli calibrate "{output_dir}/density_scores.json" "{output_dir}/gold_scores.json"
```

Tell the user: "Density analysis complete — weights calibrated."

### Step 4: SKU Extraction

SKUs (Standardized Knowledge Units) are the atomic building blocks — each one captures a single piece of actionable knowledge with its context, trigger conditions, and logic.

Read `{project_root}/.claude/skills/pdf2skills/prompts/sku-extraction.md`. Dispatch Agent(s) to extract SKUs from high-density chunks (top 80% by `final_score` in `density_scores.json`).

For books with many chunks, dispatch multiple Agents in parallel — one per group of 5–8 chunks. Each Agent writes SKU JSON files to `{output_dir}/skus/skus/` and appends to `{output_dir}/skus/skus_index.json`.

Tell the user: "Extracted {N} knowledge units."

### Step 5: Knowledge Fusion

This step deduplicates and normalizes the extracted knowledge.

**5a. Similarity bucketing** (Python):
```bash
cd {project_root} && source .venv/bin/activate && python -m src.cli similarity "{output_dir}/skus" -t 0.5
```

**5b. Tag normalization** (Agent):
Read `{project_root}/.claude/skills/pdf2skills/prompts/knowledge-fusion.md`. Dispatch an Agent to normalize `applicable_objects` and `domain_tags` across all SKUs, then update the SKU files in place.

Tell the user: "Knowledge fusion complete — {N} buckets formed."

### Step 6: Skill Generation

Read `{project_root}/.claude/skills/pdf2skills/prompts/skill-generation.md`. For each bucket in `{output_dir}/skus/buckets.json`, dispatch an Agent to convert the SKUs into Claude Code Skills.

- Process one bucket at a time (or parallel for independent buckets)
- For buckets with >15 SKUs, split into batches
- Each skill gets its own directory under `{output_dir}/generated_skills/`
- Format: `{skill-name}/SKILL.md` + optional `{skill-name}/references/`

Tell the user: "Generated {N} skills from {M} knowledge units."

### Step 6b: Skill Quality Optimization (skill-creator, optional)

If `skill-creator` is not installed at either `~/.claude/skills/skill-creator/` or `{project_root}/.claude/skills/skill-creator/`, tell the user: "skill-creator not found — skipping optional optimization step." Then continue directly to Step 7.

For each generated skill in `{output_dir}/generated_skills/`, dispatch an Agent to run the skill-creator optimization loop:

1. **Locate skill-creator**: Find it at `~/.claude/skills/skill-creator/` or the project's `.claude/skills/skill-creator/`.
2. **Choose the actual path**: If the project-level path exists, use it; otherwise use the user-level path.
3. **Generate evals**: Based on the skill's name, description, and SKILL.md content, generate a `evals.json` test set (10–20 cases: ~60% should_trigger, ~40% should not) and write it to `{skill_dir}/evals.json`.
4. **Run description optimization loop**:
   ```bash
   cd {skill_creator_root} && python -m scripts.run_loop \
     --skill "{skill_dir}/SKILL.md" \
     --evals "{skill_dir}/evals.json" \
     --max-iterations 3 \
     --num-workers 4
   ```
5. **Generate review report**:
   ```bash
   cd {skill_creator_root} && python eval-viewer/generate_review.py \
     "{skill_dir}/evals.json" -o "{skill_dir}/eval_report.html"
   ```
6. Write the optimized description back to `{skill_dir}/SKILL.md` frontmatter.

Process skills in parallel (one Agent per skill) for efficiency.

Tell the user: "Skill optimization complete — descriptions refined for {N} skills."

### Step 7: Router and Glossary

Dispatch two Agents in parallel:

1. **Router** — Read `{project_root}/.claude/skills/pdf2skills/prompts/router-generation.md`. Generate `{output_dir}/generated_skills/index.md` as a navigation index for all skills.

2. **Glossary** — Read `{project_root}/.claude/skills/pdf2skills/prompts/glossary-extraction.md`. Generate `{output_dir}/glossary.json` with domain terminology extracted from SKUs.

### Step 8: Deliver Results

Tell the user what was created and how to use it:

1. **Location**: "Your skills are in `{output_dir}/generated_skills/`"
2. **Install**: "Copy skill folders to `~/.claude/skills/` or your project's `.claude/skills/`"
3. **Use**: "Invoke any skill with `/{skill-name}` in Claude Code"
4. **Browse**: "Open `index.md` to see all available skills and their descriptions"

## Output Structure

```
{pdf_stem}_output/
├── full.md                           # Extracted Markdown
├── chunks/                           # Semantic chunks
│   ├── chunks_index.json
│   └── chunk_*.md
├── density_scores.json               # NLP density analysis
├── gold_scores.json                  # LLM calibration scores
├── skus/                             # Structured knowledge units
│   ├── skus_index.json
│   ├── buckets.json
│   └── skus/*.json
├── glossary.json                     # Domain terminology
└── generated_skills/                 # Ready-to-install Skills
    ├── index.md
    ├── generation_metadata.json
    └── {skill-name}/
        ├── SKILL.md
        └── references/
```

## Error Recovery

Each stage is idempotent — if something fails, re-run from that stage without losing earlier work. The pipeline state is persisted in `{output_dir}/.pipeline_state.json`, and the output directory contents provide additional checkpoints for inspection and recovery.

For very large PDFs (>100 pages), suggest splitting into parts first. The Read tool handles max 20 pages per call, so a 200-page book needs 10 read operations.
