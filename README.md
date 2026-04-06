# pdf2skills

将 PDF 或 Markdown 文档中的知识，转成一套结构化、可供 AI agent 运行环境集成的技能包（Skill Pack）。

本项目基于 [kitchen-engineer42/pdf2skills](https://github.com/kitchen-engineer42/pdf2skills) 重新设计，采用**Skill 定义层 + Python 运行层**的混合架构：
- **Skill 层**负责长流程编排、Agent 调度和技能生成
- **Python 层**负责密度评分、相似度分桶、配置与状态管理

## 这次发布的更新

本次发布版本为 **v2.1.0**。

- Skill 定义位于 `skills/pdf2skills/`
- 支持把 Markdown 直接放进 `pdf/`，跳过 PDF → Markdown 提取
- Pipeline 新增 **Step 6b：skill-creator 优化**
- 支持 **Custom OpenAI-compatible provider**
- 输出目录与工作区约定更完整

## 与原项目的区别

| 维度 | 原项目 | v2.1.0 |
|------|--------|---------|
| LLM 调用 | SiliconFlow API（需配置） | Agent 调度 + 可选外部 LLM Provider |
| 输入格式 | 主要面向 PDF | PDF + Markdown |
| PDF 解析 | 仅 MinerU API | `auto / claude / mineru / llm / pypdf2` |
| LLM Provider | 仅 SiliconFlow | 8 家可选，含自定义 OpenAI-compatible endpoint |
| Skill 部署 | 需手动调整 | 仓库内提供 `skills/pdf2skills/`，可按目标运行环境安装 |
| 配置管理 | .env 散落各文件 | `PipelineConfig` + 分层 `.env` |
| 测试 | 无 | pytest 测试覆盖核心模块 |
| 断点恢复 | 无 | `.pipeline_state.json` 支持失败续跑 |

## 快速开始

### 1. 安装依赖（Python 3.11+，推荐 3.12）

```bash
git clone https://github.com/pxb988/pdf2skills.git
cd pdf2skills
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 2. 配置工作区

复制根目录的配置模板：

```bash
# 项目级配置
mkdir -p .pdf2skills
cp .env.example .pdf2skills/.env

# 或用户级配置（推荐复用）
mkdir -p ~/.pdf2skills
cp .env.example ~/.pdf2skills/.env
```

最少只需配置一个可用的 LLM Provider；如果不配置，也可使用本地 agent 运行环境提供的默认文档读取能力作为 PDF 读取方案。

示例：

```ini
# 选择 provider
LLM_PROVIDER=custom
CUSTOM_API_KEY=sk-...
CUSTOM_BASE_URL=https://your-openai-compatible-endpoint
CUSTOM_MODEL=gpt-5.4

# PDF 解析器，默认 auto
PDF_PARSER=auto
```

### 可选：安装 skill-creator

如果你希望启用 **Step 6b: skill-creator 优化**，需要额外安装 `skill-creator` skill。若未安装，pdf2skills 仍可完成 skills 生成，只是会跳过优化阶段。

推荐放在用户级目录：

```text
~/.claude/skills/skill-creator/
```

或项目级目录：

```text
<project>/.claude/skills/skill-creator/
```


把待处理文件放进 `pdf/` 目录：

```text
pdf/
├── 某本书.pdf
└── 某个项目说明.md
```

支持两种输入：
- **PDF**：正常执行 PDF → Markdown → 后续流程
- **Markdown**：直接跳过 PDF 提取，进入语义分块

输出默认写入输入文件同级目录下的：

```text
<input_stem>_output/
```

例如：

```text
pdf/你的文件.md
→ pdf/你的文件_output/
```

### 4. CLI 用法

如果环境已经装好，之后每次只要做这几步：

1. 准备一个输入文件，例如：

```text
/absolute/path/to/your-file.pdf
```

或：

```text
/absolute/path/to/your-file.md
```

2. 在项目根目录执行对应命令或集成流程

3. 输出会出现在输入文件同级目录：

```text
/absolute/path/to/your-file_output/
```

### 5. Skill 集成

本仓库内置的 skill 定义位于：

```text
skills/pdf2skills/
```

如果你使用支持该目录约定的 agent/运行环境，可基于该 skill 直接集成；如果你更偏向脚本方式，也可以直接调用 Python CLI。

## Pipeline 工作流

完整流程如下：

```text
PDF / Markdown → Chunks → Density → SKUs → Buckets → Skills → Optimize → Router / Glossary
    (Read)        (Agent) (Py+Agent) (Agent) (Python) (Agent) (skill-creator) (Agent)
```

其中：
- **Markdown 输入**会跳过第一步 PDF 提取
- **Optimize** 阶段由 `skill-creator` 负责 description / trigger 质量优化
- 若未安装 `skill-creator`，可先完成主 pipeline，再单独补跑优化
- **Router / Glossary** 分别生成技能导航和领域术语表

### 8 个阶段

1. **输入读取**
   - PDF：按页读取并合成为 `full.md`
   - Markdown：直接作为 `full.md` 使用
2. **语义分块**
   - 使用 Agent 根据章节与语义边界切块
3. **密度分析**
   - Python 先打分，LLM 再做 calibration
4. **SKU 提取**
   - 从高密度 chunk 中提取结构化知识单元
5. **知识融合**
   - 做相似度分桶、标签和对象归一化
6. **Skill 生成**
   - 每个 bucket 生成一个或多个可供 agent 集成的 skill
7. **Skill 优化**
   - 使用 `skill-creator` 评估并优化 skill description 与触发边界
8. **路由与术语表**
   - 生成 `index.md` 与 `glossary.json`

## 项目结构

```text
pdf2skills/
├── skills/
│   └── pdf2skills/
│       ├── SKILL.md
│       └── prompts/
├── src/
│   ├── cli.py
│   ├── pipeline/
│   ├── nlp/
│   ├── pdf_parser/
│   ├── llm/
│   └── output/
├── tests/
├── pdf/
├── output/
├── .env.example
├── pyproject.toml
└── README.md
```

## 配置说明

配置优先级从高到低：

1. Shell 环境变量
2. `<project>/.pdf2skills/.env`
3. `~/.pdf2skills/.env`

### PDF 解析器

| 值 | 说明 | 需要配置 |
|----|------|----------|
| `auto` | 自动选择最优解析器 | 否 |
| `claude` | 使用运行环境内置文档读取能力 | 否 |
| `mineru` | 使用 MinerU 云 API | `MINERU_API_KEY` |
| `llm` | PyPDF2 提取 + 外部 LLM 重组 Markdown | `LLM_PROVIDER` + API Key |
| `pypdf2` | 纯本地解析 | 否 |

### LLM Provider

支持以下 provider，均走 OpenAI-compatible `/chat/completions`：

| Provider | `LLM_PROVIDER` | 前缀 | 默认模型 |
|----------|----------------|------|----------|
| OpenAI | `openai` | `OPENAI_` | gpt-4o |
| Anthropic | `anthropic` | `ANTHROPIC_` | claude-sonnet-4-20250514 |
| Google | `google` | `GOOGLE_` | gemini-2.0-flash |
| DeepSeek | `deepseek` | `DEEPSEEK_` | deepseek-chat |
| 智谱 GLM | `zhipu` | `ZHIPU_` | glm-4-plus |
| 通义千问 | `qwen` | `QWEN_` | qwen-plus |
| SiliconFlow | `siliconflow` | `SILICONFLOW_` | deepseek-ai/DeepSeek-V3 |
| Custom | `custom` | `CUSTOM_` | 用户指定 |

对自定义 OpenAI-compatible 服务，至少配置：

```ini
LLM_PROVIDER=custom
CUSTOM_API_KEY=sk-...
CUSTOM_BASE_URL=https://your-endpoint
CUSTOM_MODEL=your-model
```

## 命令行接口

所有命令都在项目根目录执行：

```bash
python -m src.cli page-count <pdf>
python -m src.cli density <chunks_dir> -o <out>
python -m src.cli calibrate <density.json> <gold.json>
python -m src.cli similarity <skus_dir> -t 0.5
python -m src.cli parse-pdf <pdf> -o <out_dir>
```

## 示例输出说明

pdf2skills 的默认输出会写到**输入文件同级目录**，用于保存一次完整运行产生的中间产物和最终技能包。

这类输出通常适合用来：
- 验证 pipeline 输出质量
- 演示如何从原子 skill 收敛到场景化 skill 包
- 为后续 router / glossary / trigger 优化提供参考

## 测试

运行全部测试：

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

运行单个测试：

```bash
python -m pytest tests/test_density.py -v
```

## 输出结构

```text
<name>_output/
├── full.md
├── chunks/
│   ├── chunks_index.json
│   └── chunk_*.md
├── density_scores.json
├── gold_scores.json
├── skus/
│   ├── skus_index.json
│   ├── buckets.json
│   └── skus/*.json
├── glossary.json
└── generated_skills/
    ├── index.md
    ├── generation_metadata.json
    └── <skill-name>/
        ├── SKILL.md
        └── references/
```

## 相关文件

- 主 skill：`skills/pdf2skills/SKILL.md`
- SubAgent prompts：`skills/pdf2skills/prompts/`

## 许可证

MIT
