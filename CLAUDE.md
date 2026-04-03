# CLAUDE.md

This file provides project-specific guidance to Claude Code when working in this repository.

## Project Snapshot

pdf2skills 将 PDF 或 Markdown 文档转成可直接导入 Claude Code 的技能包。

项目当前由两层组成：
- **Skill 编排层**：`.claude/skills/pdf2skills/`
- **Python 计算层**：`src/`

## Canonical Entry Points

协作时优先看这些文件：

1. `README.md`
   - 用户安装、配置、运行方式
2. `.claude/skills/pdf2skills/SKILL.md`
   - `/pdf2skills` 的主编排逻辑
3. `pyproject.toml`
   - 版本、Python 要求、依赖、console script
4. `src/cli.py`
   - Python CLI 入口
5. `src/pipeline/config.py` / `src/pipeline/state.py`
   - 配置加载与断点恢复的事实实现

如果 README、SKILL.md、CLAUDE.md 三者冲突，以 **代码与 `pyproject.toml`** 为准，并同步修正文档。

## Collaboration Rules

### 何时改哪个文件

- **改 `README.md`**：用户安装、配置、使用方式
- **改 `SKILL.md`**：`/pdf2skills` 流程、Agent 步骤、进度提示、可选优化步骤
- **改 `src/`**：CLI、配置、parser、density、similarity、state、output formatting
- **改 `CLAUDE.md`**：项目级协作规则、入口、边界、输出约定

### 修改时的同步检查

- 改 **输入/输出约定**：同时检查 `README.md`、`SKILL.md`、`src/pipeline/state.py`
- 改 **配置项**：同时检查 `README.md`、`CLAUDE.md`、`src/pipeline/config.py`
- 改 **Python 版本 / 依赖 / 版本号**：以 `pyproject.toml` 为准，并同步文档

## Execution Contract

### 支持的输入
- `.pdf`
- `.md`

其中 Markdown 会跳过 PDF 提取，直接进入 chunking。

### 默认输出位置

输出目录位于**输入文件同级目录**，命名为：

```text
<input_stem>_output/
```

最常检查的输出：
- `full.md`
- `chunks/chunks_index.json`
- `density_scores.json`
- `skus/skus_index.json`
- `skus/buckets.json`
- `generated_skills/index.md`
- `generated_skills/<skill-name>/SKILL.md`
- `.pipeline_state.json`

## Configuration Checklist

以 `pyproject.toml` 为准：
- Python 要求：`>=3.11`
- 本地开发推荐：`3.12`

常用安装方式：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

配置优先级：
1. Shell 环境变量
2. `<project>/.pdf2skills/.env`
3. `~/.pdf2skills/.env`

重点配置：
- `PDF_PARSER`
- `LLM_PROVIDER`
- `CUSTOM_API_KEY`
- `CUSTOM_BASE_URL`
- `CUSTOM_MODEL`

完整示例优先参考 `README.md` 与 `src/pipeline/config.py`。

## Optional skill-creator Step

Step 6b `skill-creator` 优化是**可选步骤**。

安装位置可以是：
- `~/.claude/skills/skill-creator/`
- `<project>/.claude/skills/skill-creator/`

协作约定：
- 未安装时应跳过优化步骤，不阻塞主流程
- 只有在需求聚焦 description、触发边界或 eval 质量时，才重点处理这一步

## Safe Commands to Reference

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
python -m pytest tests/ -v
python -m pytest tests/test_density.py -v
python -m src.cli page-count <pdf>
python -m src.cli density <chunks_dir> -o <out>
python -m src.cli calibrate <density.json> <gold.json>
python -m src.cli similarity <skus_dir> -t 0.5
python -m src.cli parse-pdf <pdf> -o <out_dir>
```

## What Not to Put Here

不要把这些内容大段复制进 `CLAUDE.md`：
- README 的完整快速开始
- SKILL.md 的完整 8 步执行细节
- prompt 文件内容
- 易过时的硬编码数字（测试总数、样例 skill 数、chunk 数等）

`CLAUDE.md` 的目标是帮助 Claude Code **快速定位入口、理解边界、减少无效搜索**。
