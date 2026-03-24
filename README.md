# pdf2skills v2

将任何 PDF 文档（专业书籍、操作手册、行业报告、技术规范、教材、标准文件）通过 AI 语义分析，转成一套结构完整、可直接导入 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 的技能包（Skill Pack）。

基于 [kitchen-engineer42/pdf2skills](https://github.com/kitchen-engineer42/pdf2skills) 重新设计，采用混合架构：**Claude Code Skill 编排 + Python NLP 辅助计算**。

## 与原项目的区别

| 维度 | 原项目 | v2 |
|------|--------|-----|
| LLM 调用 | SiliconFlow API (需配置) | Claude Code SubAgent (零配置) |
| PDF 解析 | 仅 MinerU API | 5 种可选：auto / claude / mineru / llm / pypdf2 |
| LLM Provider | 仅 SiliconFlow | 8 家可选，含自定义 OpenAI 兼容端点 |
| 配置管理 | .env 散落各文件 | 统一 frozen dataclass + 分层 .env（项目级 / 用户级） |
| 测试 | 无 | 77 个单元测试 |
| 断点恢复 | 无 | Pipeline 状态持久化，失败后可续跑 |

## 快速开始

### 1. 安装 Python 依赖

```bash
git clone <this-repo> && cd pdf2skills
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 2. 安装 Skill 到 Claude Code

```bash
# 方式一：项目级（仅当前项目可用）
mkdir -p .claude/skills
cp -r skills/pdf2skills .claude/skills/pdf2skills

# 方式二：用户级（所有项目可用）
cp -r skills/pdf2skills ~/.claude/skills/pdf2skills
```

### 3. 使用

在 Claude Code 中调用：

```
/pdf2skills /path/to/your/book.pdf
```

Claude Code 会自动执行完整的 8 阶段 pipeline：

1. **PDF 解析** — 读取 PDF 并转为 Markdown
2. **语义分块** — 按语义边界拆分为自包含的知识块
3. **密度分析** — NLP 三维评分 + LLM 校准，识别高价值内容
4. **SKU 提取** — 从高密度块中提取结构化知识单元
5. **知识融合** — TF-IDF 相似度去重 + 标签归一化
6. **Skill 生成** — 将 SKU 组转为 Claude Code Skill 格式
7. **路由索引** — 生成技能导航入口
8. **术语表** — 提取领域专业术语

## Pipeline 架构

```
PDF → Markdown → Chunks → Density → SKUs → Buckets → Skills → Router
 │       │          │        │        │        │         │        │
 └─ Read ┘    SubAgent   Python   SubAgent  Python   SubAgent  SubAgent
              + Python    + LLM
```

- **SubAgent**: Claude Code 内置模型完成所有 LLM 推理（零外部 API 配置）
- **Python**: spaCy / scikit-learn 完成 NLP 计算密集型任务（密度评分、相似度分桶）

## Skill 编排层详解

### SKILL.md — Pipeline 主入口

`skills/pdf2skills/SKILL.md` 是整个 pipeline 的编排中心，通过 Claude Code 的 `/pdf2skills` 命令触发。它定义了：

- **触发条件**：用户提供 PDF 路径并表达"转技能"意图时自动匹配（支持多种自然语言表述）
- **环境准备**：自动检测 Python 虚拟环境和依赖
- **8 步工作流**：每一步调用 Python CLI（Bash tool）或分发 SubAgent（Agent tool），按顺序编排
- **进度汇报**：每步完成后向用户反馈进度
- **错误恢复**：每阶段幂等，通过输出目录结构判断已完成的阶段

### prompts/ — SubAgent 指令模板

pipeline 中所有 LLM 推理任务都通过 SubAgent 执行，每个 SubAgent 接收对应的 prompt 模板作为指令。共 7 个 prompt 文件：

| Prompt 文件 | Pipeline 阶段 | SubAgent 职责 |
|-------------|--------------|---------------|
| `chunking.md` | Step 2: 语义分块 | 按 Onion Peeler 策略（章节→小节→段落）递归拆分 Markdown 为自包含 chunk，每个 chunk < 30K token。输出带 YAML frontmatter 的 `chunk_*.md` + `chunks_index.json` |
| `density-calibration.md` | Step 3b: 密度校准 | 对校准样本 chunk 进行 0–100 知识密度评分。评分维度：可操作知识(40%) + 技术深度(30%) + 逻辑结构(20%) + 实例(10%)。输出 `gold_scores.json` |
| `sku-extraction.md` | Step 4: SKU 提取 | 从高密度 chunk 中提取 SKU（标准化知识单元）。每个 SKU 包含 metadata / context / trigger / core_logic / output / custom_attributes 六个字段。遵循 MECE 原则，一个概念一个 SKU |
| `knowledge-fusion.md` | Step 5b: 知识融合 | 跨 SKU 归一化 `applicable_objects`（严格同义合并）和 `domain_tags`（宽松近义合并），生成映射表并原地更新 SKU 文件 |
| `skill-generation.md` | Step 6: Skill 生成 | 将同桶 SKU 组转为 Claude Code Skill 格式。每个 Skill 包含 SKILL.md（< 500 行）+ 可选 references/ 目录。description 字段决定触发时机 |
| `router-generation.md` | Step 7: 路由生成 | 读取所有生成的 Skill，创建 `index.md` 导航索引（按类别分组的技能表 + 使用说明） |
| `glossary-extraction.md` | Step 7: 术语表 | 从 SKU 中提取领域术语（名称、定义、类别、别名、关联技能），输出 `glossary.json` |

### 核心数据模型

#### SKU（Standardized Knowledge Unit）

SKU 是 pipeline 的核心中间表示，结构如下：

```json
{
  "metadata": {
    "uuid": "sku_chunk_001_01",
    "name": "描述性知识单元名称",
    "source_ref": { "chunk_id": "chunk_001", "snippet": "..." }
  },
  "context": {
    "applicable_objects": ["适用对象"],
    "prerequisites": ["前置条件"],
    "constraints": ["约束限制"]
  },
  "trigger": {
    "condition_logic": "IF (条件A) AND (条件B) THEN 应用"
  },
  "core_logic": {
    "logic_type": "Formula | Decision_Tree | Heuristic | Process",
    "execution_body": "具体的公式、流程或决策逻辑",
    "variables": [{ "name": "var1", "type": "float", "description": "..." }]
  },
  "output": {
    "output_type": "Value | Alert | Action",
    "result_template": "结果解读模板"
  },
  "custom_attributes": {
    "domain_tags": ["领域标签"],
    "confidence": "high | medium | low"
  }
}
```

#### 生成的 Skill 格式

每个生成的 Skill 遵循 Claude Code Skill 标准格式：

```
skill-name/
├── SKILL.md         # 主文件（< 500 行）
│   ├── YAML frontmatter（name + description）
│   ├── When to Use（触发场景）
│   ├── Procedure（操作步骤）
│   └── Key Rules（关键规则/公式）
└── references/      # 可选详细参考
    └── details.md
```

## 项目结构

```
pdf2skills/
├── skills/pdf2skills/              # Claude Code Skill（编排层）
│   ├── SKILL.md                    #   Pipeline 主入口
│   └── prompts/                    #   SubAgent prompt 模板
│       ├── chunking.md             #     语义分块指令
│       ├── density-calibration.md  #     密度校准指令
│       ├── sku-extraction.md       #     知识单元提取指令
│       ├── knowledge-fusion.md     #     知识融合指令
│       ├── skill-generation.md     #     Skill 生成指令
│       ├── router-generation.md    #     路由生成指令
│       └── glossary-extraction.md  #     术语表提取指令
├── src/                            # Python 计算层
│   ├── cli.py                      #   CLI 入口（5 个子命令）
│   ├── pipeline/                   #   配置 + 状态管理
│   │   ├── config.py               #     PipelineConfig（frozen dataclass）
│   │   └── state.py                #     PipelineState（断点恢复）
│   ├── nlp/                        #   NLP 计算模块
│   │   ├── density.py              #     三维语义密度评分
│   │   └── similarity.py           #     TF-IDF 余弦相似度 + 聚类
│   ├── pdf_parser/                 #   PDF 解析适配器
│   │   ├── base.py                 #     抽象基类
│   │   ├── claude_parser.py        #     Claude Read tool 解析
│   │   ├── mineru_parser.py        #     MinerU 云 API 解析
│   │   └── llm_parser.py           #     LLM API 解析
│   ├── llm/                        #   LLM 客户端
│   │   └── client.py               #     OpenAI 兼容 Chat Client
│   └── output/                     #   输出格式化
│       └── skill_formatter.py      #     Skill 目录结构打包
├── tests/                          # 77 个单元测试
│   ├── test_pipeline.py            #   配置 + 状态测试（31 个）
│   ├── test_density.py             #   密度评分测试
│   ├── test_similarity.py          #   相似度测试
│   ├── test_llm_client.py          #   LLM 客户端测试（10 个）
│   └── test_llm_parser.py          #   LLM 解析器测试（6 个）
├── pyproject.toml                  # 构建配置 + 依赖
├── CLAUDE.md                       # Claude Code 项目指南
└── .pdf2skills/.env                # 项目级环境配置（在 .gitignore 中）
```

## 配置（可选）

默认**零配置**即可使用（PDF 通过 Claude Code Read tool 读取）。如需使用外部 LLM 或 MinerU 解析 PDF，可进行如下配置：

### 配置文件位置

| 位置 | 优先级 | 适用范围 |
|------|--------|----------|
| Shell 环境变量 | 最高 | 当前会话 |
| `<项目>/.pdf2skills/.env` | 中 | 当前项目 |
| `~/.pdf2skills/.env` | 最低 | 所有项目 |

### PDF 解析器选择

通过 `PDF_PARSER` 环境变量控制：

| 值 | 说明 | 需要配置 |
|----|------|----------|
| `auto` (默认) | 自动选择最优解析器 | — |
| `claude` | Claude Code Read tool（零配置） | — |
| `mineru` | MinerU 云 API（高质量） | `MINERU_API_KEY` |
| `llm` | PyPDF2 提取 + LLM 格式化 | `LLM_PROVIDER` + API Key |
| `pypdf2` | 纯本地 PyPDF2（无 LLM） | — |

`auto` 模式按优先级自动选择：MinerU（已配 key）→ LLM（已配 provider）→ Claude（fallback）。

### LLM Provider 配置

支持 8 家 Provider，均走 OpenAI 兼容 `/chat/completions` 格式：

| Provider | `LLM_PROVIDER` 值 | 环境变量前缀 | 默认模型 |
|----------|-------------------|-------------|----------|
| OpenAI | `openai` | `OPENAI_` | gpt-4o |
| Anthropic | `anthropic` | `ANTHROPIC_` | claude-sonnet-4-20250514 |
| Google Gemini | `google` | `GOOGLE_` | gemini-2.0-flash |
| DeepSeek | `deepseek` | `DEEPSEEK_` | deepseek-chat |
| 智谱 GLM | `zhipu` | `ZHIPU_` | glm-4-plus |
| 通义千问 | `qwen` | `QWEN_` | qwen-plus |
| SiliconFlow | `siliconflow` | `SILICONFLOW_` | deepseek-ai/DeepSeek-V3 |
| 自定义 | `custom` | `CUSTOM_` | (用户指定) |

每个 Provider 配置 3 个环境变量：

```bash
# 示例：使用 DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_MODEL=deepseek-chat          # 可选，有默认值
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1  # 可选，有默认值

# 示例：使用自定义 OpenAI 兼容端点
LLM_PROVIDER=custom
CUSTOM_API_KEY=sk-your-key
CUSTOM_MODEL=your-model-name
CUSTOM_BASE_URL=https://your-api.example.com/v1
```

### 配置示例

```bash
# 创建项目级配置
mkdir -p .pdf2skills
cat > .pdf2skills/.env << 'EOF'
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
PDF_PARSER=auto
EOF
```

## 输出结构

pipeline 执行后生成如下目录：

```
{pdf_name}_output/
├── full.md                           # 提取的完整 Markdown
├── chunks/                           # 语义分块
│   ├── chunks_index.json
│   └── chunk_*.md
├── density_scores.json               # NLP 密度分析结果
├── gold_scores.json                  # LLM 校准评分
├── skus/                             # 结构化知识单元
│   ├── skus_index.json
│   ├── buckets.json
│   └── skus/*.json
├── glossary.json                     # 领域术语表
└── generated_skills/                 # 可安装的 Skill 包
    ├── index.md                      # 技能导航索引
    ├── generation_metadata.json
    └── {skill-name}/
        ├── SKILL.md                  # Skill 入口文件
        └── references/              # 参考资料
```

## 单独使用 Python 模块

Python CLI 可独立于 Skill 层使用：

```bash
source .venv/bin/activate

# PDF 页数
python -m src.cli page-count book.pdf

# NLP 密度评分
python -m src.cli density chunks_dir/ -o density.json

# 权重校准
python -m src.cli calibrate density.json gold_scores.json

# SKU 相似度分桶
python -m src.cli similarity skus_dir/ -t 0.5

# PDF 解析（自动检测解析器）
python -m src.cli parse-pdf book.pdf -o output_dir/
```

## 测试

```bash
source .venv/bin/activate
python -m pytest tests/ -v        # 全部 77 个测试
python -m pytest tests/ -v -k density  # 仅密度相关测试
```

## 技术栈

- **Python 3.12+** — 核心运行时
- **spaCy** (en_core_web_sm) — 英文 NLP（NER、词性标注）
- **jieba** — 中文分词
- **scikit-learn** — TF-IDF 向量化 + 余弦相似度 + 线性回归
- **PyPDF2** — PDF 文本提取
- **python-dotenv** — 分层 .env 配置加载
- **requests** — LLM API HTTP 调用
- **pytest** — 测试框架

## License

MIT
