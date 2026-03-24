# pdf2skills v2

将任何 PDF 文档（专业书籍、操作手册、行业报告、技术规范）通过 AI 语义分析，转成一套结构完整、可直接导入 Claude Code 的技能包。

基于 [kitchen-engineer42/pdf2skills](https://github.com/kitchen-engineer42/pdf2skills) 重新设计，采用混合架构：**Claude Code Skill 编排 + Python NLP 辅助计算**。

## 核心改进

| 维度 | 原项目 | v2 |
|------|--------|-----|
| LLM 调用 | SiliconFlow API (需配置 API key) | Claude Code SubAgent (零配置) |
| PDF 解析 | MinerU API only | 可配置：Claude 原生 / MinerU / PyPDF2 |
| API Client | 每个模块重复定义 | 无需 API Client，由 Claude Code 处理 |
| 配置管理 | .env 散落各文件 | 统一 config + .env.example |
| 测试 | 无 | 单元测试 38 个 |

## 快速开始

### 1. 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install spacy jieba numpy scikit-learn PyPDF2 python-dotenv
python -m spacy download en_core_web_sm
```

### 2. 安装 Skill

将 `skills/pdf2skills/` 目录复制到你的 Claude Code skills 目录：

```bash
cp -r skills/pdf2skills ~/.claude/skills/pdf2skills
```

### 3. 使用

在 Claude Code 中调用：

```
/pdf2skills /path/to/your/book.pdf
```

Claude Code 会自动执行完整的 pipeline：
1. 读取 PDF 并转为 Markdown
2. 语义分块
3. NLP 密度分析 + LLM 校准
4. 知识单元（SKU）提取
5. 知识融合与去重
6. 生成 Claude Code Skills
7. 生成路由索引和术语表

## Pipeline 架构

```
PDF → Markdown → Chunks → Density → SKUs → Buckets → Skills → Router
 │       │          │        │        │        │         │        │
 └─ Read ┘    SubAgent   Python   SubAgent  Python   SubAgent  SubAgent
              + Python    + LLM
```

- **SubAgent**: Claude Code 的内置模型完成所有 LLM 推理任务
- **Python**: spaCy/scikit-learn 完成 NLP 计算密集型任务

## 项目结构

```
pdf2skills/
├── skills/pdf2skills/          # Claude Code Skill
│   ├── SKILL.md                # 主入口
│   └── prompts/                # SubAgent prompt 模板
├── src/                        # Python 辅助模块
│   ├── cli.py                  # CLI 入口
│   ├── pipeline/               # 配置 + 状态管理
│   ├── nlp/                    # NLP 密度评分 + 相似度
│   ├── pdf_parser/             # PDF 解析适配器
│   └── output/                 # Skill 格式化输出
├── tests/                      # 单元测试
├── pyproject.toml
└── .env.example                # 可选配置
```

## 配置（可选）

默认零配置即可使用。如需自定义，复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
```

## 单独使用 Python 模块

```bash
# PDF 页数
python -m src.cli page-count book.pdf

# NLP 密度评分
python -m src.cli density chunks_dir/ -o density.json

# 权重校准
python -m src.cli calibrate density.json gold_scores.json

# SKU 相似度分桶
python -m src.cli similarity skus_dir/ -t 0.5
```

## 测试

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## License

MIT
