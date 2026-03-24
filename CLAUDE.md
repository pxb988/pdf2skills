# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pdf2skills 将 PDF 文档（专业书籍、操作手册、行业报告、技术规范、教材、标准文件）通过 AI 语义分析，转成一套结构完整、可直接导入 Claude Code 的技能包（Skill Pack）。

采用混合架构：**Claude Code Skill 编排** (`skills/pdf2skills/SKILL.md`) + **Python NLP 计算** (`src/`)。

Pipeline 数据流：
```
PDF → Markdown → Chunks → Density Scores → SKUs → Buckets → Skills → Router
      (Read)    (Agent)   (Python+Agent)   (Agent) (Python)  (Agent)  (Agent)
```

## Build & Test Commands

```bash
# 激活虚拟环境（Python 3.12+）
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"
python -m spacy download en_core_web_sm

# 运行全部测试（77 个）
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_density.py -v

# 运行单个测试方法
python -m pytest tests/test_density.py::TestNLPAnalyzer::test_calc_s_logic_with_connectives -v
```

## Python CLI Subcommands

所有命令须从项目根目录执行：

```bash
python -m src.cli page-count <pdf>              # PDF 页数
python -m src.cli density <chunks_dir> -o <out>  # NLP 密度评分
python -m src.cli calibrate <density.json> <gold.json>  # 权重校准
python -m src.cli similarity <skus_dir> -t 0.5   # SKU 相似度分桶
python -m src.cli parse-pdf <pdf> -o <out_dir>   # 独立 PDF 解析
```

## Architecture

### 双层设计

- **Skill 层** (`skills/pdf2skills/SKILL.md`)：Pipeline 编排入口，被 Claude Code `/pdf2skills` 命令触发。通过 Bash tool 调用 Python CLI，通过 Agent tool 分发 LLM 任务。Prompt 模板在 `skills/pdf2skills/prompts/`。
- **Python 层** (`src/`)：纯计算模块。CLI 入口 `src/cli.py` 分发到各子模块。除 `src/llm/client.py`（用于 LLM PDF 解析）外，不依赖外部 API。

### Skill 编排 — SKILL.md

`skills/pdf2skills/SKILL.md` 是 pipeline 主入口，定义了：
- 触发条件（description 字段匹配用户意图）
- 环境准备（venv + 依赖检查）
- 8 步工作流的完整编排逻辑
- 每步的进度汇报模板

### SubAgent Prompt 模板

7 个 prompt 文件控制 SubAgent 的行为：

| Prompt | 阶段 | 核心逻辑 |
|--------|------|----------|
| `chunking.md` | Step 2 | Onion Peeler 递归分块策略（章→节→段），输出带 frontmatter 的 chunk 文件 |
| `density-calibration.md` | Step 3b | 0–100 知识密度评分（可操作 40% + 深度 30% + 结构 20% + 实例 10%） |
| `sku-extraction.md` | Step 4 | MECE 原则提取 SKU（metadata/context/trigger/core_logic/output/attributes） |
| `knowledge-fusion.md` | Step 5b | applicable_objects 严格同义合并 + domain_tags 宽松近义合并 |
| `skill-generation.md` | Step 6 | SKU 组 → Claude Code Skill（SKILL.md < 500 行 + references/） |
| `router-generation.md` | Step 7 | 生成 index.md 技能导航索引（分类表 + 使用说明） |
| `glossary-extraction.md` | Step 7 | 提取领域术语 → glossary.json（term/definition/category/aliases） |

### SKU 数据模型

SKU（Standardized Knowledge Unit）是 pipeline 核心中间表示，包含 6 个字段：
- `metadata`: uuid、名称、来源引用
- `context`: 适用对象、前置条件、约束
- `trigger`: 触发条件逻辑（IF...THEN 格式）
- `core_logic`: 逻辑类型（Formula/Decision_Tree/Heuristic/Process）+ 执行体 + 变量定义
- `output`: 输出类型（Value/Alert/Action）+ 结果模板
- `custom_attributes`: 领域标签 + 置信度

### 关键模块

| 模块 | 职责 |
|------|------|
| `src/pipeline/config.py` | 不可变配置 (`PipelineConfig`, frozen dataclass)，多 LLM Provider，分层 .env 加载 |
| `src/pipeline/state.py` | Pipeline 检查点状态，持久化到 `.pipeline_state.json`，支持断点恢复 |
| `src/nlp/density.py` | 三维语义密度评分（s_logic / s_entity / s_struct），LinearRegression 校准 |
| `src/nlp/similarity.py` | TF-IDF 余弦相似度 + 单链聚类分桶 |
| `src/pdf_parser/base.py` | PDF 解析器抽象基类 |
| `src/pdf_parser/claude_parser.py` | Claude Read tool 解析 + PyPDF2 fallback |
| `src/pdf_parser/mineru_parser.py` | MinerU 云 API 解析（需 API key） |
| `src/pdf_parser/llm_parser.py` | LLM API 解析（PyPDF2 提取 + LLM 格式化 Markdown） |
| `src/llm/client.py` | OpenAI 兼容的 LLM Chat Client（支持重试） |
| `src/output/skill_formatter.py` | 生成的 Skill 目录结构打包 |

### 配置系统

**加载优先级**（高 → 低）：

1. Shell 环境变量 / CLI exports
2. `<cwd>/.pdf2skills/.env`（项目级）
3. `~/.pdf2skills/.env`（用户级）

使用 `dotenv_values()` 读取（不污染 `os.environ`），`os.environ` 中已设置的 key 优先覆盖。

### LLM Provider 支持

支持 8 家 Provider（均走 OpenAI 兼容 `/chat/completions` 格式）：

| Provider | 前缀 | 默认模型 |
|----------|------|----------|
| OpenAI | `OPENAI_` | gpt-4o |
| Anthropic | `ANTHROPIC_` | claude-sonnet-4-20250514 |
| Google | `GOOGLE_` | gemini-2.0-flash |
| DeepSeek | `DEEPSEEK_` | deepseek-chat |
| 智谱 GLM | `ZHIPU_` | glm-4-plus |
| 通义千问 | `QWEN_` | qwen-plus |
| SiliconFlow | `SILICONFLOW_` | deepseek-ai/DeepSeek-V3 |
| Custom | `CUSTOM_` | (用户指定) |

每个 Provider 通过三个环境变量配置：`{PREFIX}API_KEY`、`{PREFIX}MODEL`、`{PREFIX}BASE_URL`。通过 `LLM_PROVIDER` 选择活跃 provider。

### PDF 解析器

`PDF_PARSER` 支持 5 种值：

| 值 | 说明 |
|----|------|
| `auto` (默认) | 自动检测：MinerU key 已配 → mineru；LLM provider 已配 → llm；否则 → claude |
| `claude` | Claude Code Read tool + PyPDF2 fallback（零配置） |
| `mineru` | MinerU 云 API（需 `MINERU_API_KEY`） |
| `llm` | PyPDF2 提取原始文本 → LLM API 转结构化 Markdown |
| `pypdf2` | 纯本地 PyPDF2（无 LLM，质量最低） |

### Pipeline 8 阶段

定义在 `src/pipeline/state.py`：

```
pdf_parse → chunking → density → sku_extract → fusion → skill_gen → router → glossary
```

每阶段幂等，失败后可从断点重跑。`PipelineState` 通过 output 目录中的 `.pipeline_state.json` 跟踪进度。

### NLP 密度模型

三维度评分（均 0–100）：
- **s_logic**：逻辑连接词密度（if / then / because / however …）
- **s_entity**：实体密度（NER + 数字 + 货币 + LaTeX）
- **s_struct**：结构化密度（列表 + 表格 + 代码块 + 标题）

通过 LLM gold score 校准权重（`LinearRegression(positive=True)`）：`final_score = w_logic × s_logic + w_entity × s_entity + w_struct × s_struct`

## Key Conventions

- `PipelineConfig` 是 frozen dataclass，配置值不可变
- Python 模块不依赖外部 LLM API（除 `src/llm/client.py`），Pipeline 推理由 Skill 层的 SubAgent 完成
- 支持中英文双语（NLP 自动检测语言，中文用 jieba，英文用 spaCy）
- SKU（Standardized Knowledge Unit）是知识的原子单元，最终通过分桶合并生成 Skill
- `_reference/` 目录是原项目代码（在 .gitignore 中），仅供参考
