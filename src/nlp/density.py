"""Three-dimensional NLP semantic density scoring.

Ported from the original pdf2skills semantic_density.py, with all
external API dependencies removed. This module does pure NLP computation;
LLM calibration is handled by the Claude Code SubAgent.

Three dimensions:
- S_logic : logic density (connectives, reasoning patterns)
- S_entity: entity density (NER, technical terms, numbers, formulas)
- S_struct: structural density (lists, tables, code blocks)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.linear_model import LinearRegression


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ChunkScore:
    """Density scores for a single chunk."""

    chunk_id: str
    title: str
    parent_path: list[str]
    book_index: int = 0
    start_line: int = 0
    end_line: int = 0
    s_logic: float = 0.0
    s_entity: float = 0.0
    s_struct: float = 0.0
    gold_score: Optional[float] = None
    final_score: float = 0.0
    content_preview: str = ""
    token_count: int = 0

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "book_index": self.book_index,
            "title": self.title,
            "parent_path": self.parent_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "s_logic": round(self.s_logic, 4),
            "s_entity": round(self.s_entity, 4),
            "s_struct": round(self.s_struct, 4),
            "gold_score": self.gold_score,
            "final_score": round(self.final_score, 4),
            "content_preview": self.content_preview,
            "token_count": self.token_count,
        }


# ---------------------------------------------------------------------------
# NLP analyzer (language-aware, no external API)
# ---------------------------------------------------------------------------

class NLPAnalyzer:
    """Language-aware NLP feature extractor.

    Lazy-loads spaCy/jieba only when needed.
    """

    def __init__(self, language: str = "auto"):
        self.language = language
        self._spacy_model = None
        self._jieba_loaded = False

    def _detect_language(self, text: str) -> str:
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        total_chars = len(text.replace(" ", "").replace("\n", ""))
        if total_chars == 0:
            return "English"
        return "Chinese" if chinese_chars / total_chars > 0.3 else "English"

    def _get_language(self, text: str) -> str:
        if self.language == "auto":
            return self._detect_language(text)
        return self.language

    def _load_spacy(self):
        if self._spacy_model is None:
            import spacy

            try:
                self._spacy_model = spacy.load("en_core_web_sm")
            except OSError:
                spacy.cli.download("en_core_web_sm")
                self._spacy_model = spacy.load("en_core_web_sm")
        return self._spacy_model

    def _load_jieba(self):
        if not self._jieba_loaded:
            import jieba

            jieba.setLogLevel(jieba.logging.INFO)
            self._jieba_loaded = True
        import jieba

        return jieba

    # -- S_logic --------------------------------------------------------

    def calc_s_logic(self, text: str) -> float:
        lang = self._get_language(text)
        text_lower = text.lower()
        word_count = max(1, len(text.split()))

        if lang == "Chinese":
            connectives = [
                r"如果", r"那么", r"因此", r"所以", r"由于", r"因为",
                r"但是", r"然而", r"虽然", r"尽管", r"除非", r"否则",
                r"必须", r"应该", r"需要", r"导致", r"造成", r"引起",
                r"首先", r"其次", r"最后", r"总之", r"综上",
                r"当.*时", r"若.*则", r"只有.*才", r"不仅.*而且",
                r"一方面.*另一方面", r"根据", r"按照", r"依据",
            ]
            count = sum(len(re.findall(p, text)) for p in connectives)
            char_count = max(1, len(text.replace(" ", "").replace("\n", "")))
            score = (count / char_count) * 100
        else:
            connectives = [
                r"\bif\b", r"\bthen\b", r"\btherefore\b", r"\bthus\b",
                r"\bbecause\b", r"\bsince\b", r"\bhence\b", r"\bso\b",
                r"\bhowever\b", r"\bbut\b", r"\balthough\b", r"\bwhile\b",
                r"\bmust\b", r"\bshould\b", r"\brequire[sd]?\b", r"\bneed[sd]?\b",
                r"\blead[s]?\s+to\b", r"\bresult[s]?\s+in\b", r"\bcause[sd]?\b",
                r"\bfirst\b", r"\bsecond\b", r"\bfinally\b", r"\bin\s+conclusion\b",
                r"\bwhen\b", r"\bunless\b", r"\bprovided\s+that\b",
                r"\baccording\s+to\b", r"\bbased\s+on\b", r"\bgiven\s+that\b",
            ]
            count = sum(len(re.findall(p, text_lower)) for p in connectives)
            score = (count / word_count) * 100

        avg_sentence_len = self._avg_sentence_length(text)
        complexity_bonus = min(avg_sentence_len / 50, 1.0) * 20
        return min(100, score + complexity_bonus)

    def _avg_sentence_length(self, text: str) -> float:
        sentences = re.split(r"[.!?。！？]", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 0
        return sum(len(s) for s in sentences) / len(sentences)

    # -- S_entity -------------------------------------------------------

    def calc_s_entity(self, text: str) -> float:
        lang = self._get_language(text)
        char_count = max(1, len(text.replace(" ", "").replace("\n", "")))

        numbers = len(re.findall(r"\d+(?:\.\d+)?%?", text))
        currency = len(re.findall(r"[$¥€£]\s*\d+|\d+\s*(?:元|美元|万|亿|千)", text))
        latex = len(re.findall(r"\$[^$]+\$|\\\[.*?\\\]|\\\(.*?\\\)", text))
        tech_patterns = len(re.findall(r"\([A-Z]{2,}\)", text))
        tech_patterns += len(re.findall(r'「[^」]+」|"[^"]+"', text))

        if lang == "Chinese":
            ner_patterns = [
                r"[\u4e00-\u9fff]{2,4}(?:公司|集团|银行|基金|股份)",
                r"[\u4e00-\u9fff]{2,3}(?:率|额|值|数|量)",
                r"(?:总|净|毛)?(?:收入|利润|资产|负债|现金流)",
            ]
            ner_count = sum(len(re.findall(p, text)) for p in ner_patterns)

            jieba = self._load_jieba()
            import jieba.posseg as pseg

            words = pseg.cut(text[:5000])
            ner_count += sum(1 for _, flag in words if flag in ("nr", "ns", "nt", "nz"))
        else:
            nlp = self._load_spacy()
            doc = nlp(text[:10000])
            ner_count = len(doc.ents)
            ner_count += len(re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text))

        total_entities = numbers + currency + latex + tech_patterns + ner_count
        return min(100, (total_entities / char_count) * 500)

    # -- S_struct -------------------------------------------------------

    def calc_s_struct(self, text: str) -> float:
        lines = text.split("\n")
        total_lines = max(1, len(lines))

        bullet_lists = sum(1 for line in lines if re.match(r"^\s*[-*+•]\s+", line))
        numbered_lists = sum(1 for line in lines if re.match(r"^\s*\d+[.)]\s+", line))
        chinese_lists = sum(
            1 for line in lines
            if re.match(r"^\s*[（(][一二三四五六七八九十\d]+[)）]", line)
        )
        table_rows = sum(1 for line in lines if "|" in line and line.count("|") >= 2)
        code_blocks = len(re.findall(r"```[\s\S]*?```", text))
        inline_code = len(re.findall(r"`[^`]+`", text))
        headers = sum(1 for line in lines if re.match(r"^#{1,6}\s+", line))

        struct_elements = (
            bullet_lists + numbered_lists + chinese_lists
            + table_rows * 0.5
            + code_blocks * 3
            + inline_code * 0.3
            + headers * 2
        )
        return min(100, (struct_elements / total_lines) * 100)


# ---------------------------------------------------------------------------
# Density analyzer (orchestrates NLP + calibration)
# ---------------------------------------------------------------------------

class DensityAnalyzer:
    """Analyze semantic density for a set of chunks.

    The NLP scoring is done locally. LLM calibration gold scores are
    expected to be provided externally (by the Claude Code SubAgent).
    """

    def __init__(self, language: str = "auto"):
        self.nlp = NLPAnalyzer(language=language)
        self.weights = {"w_logic": 1 / 3, "w_entity": 1 / 3, "w_struct": 1 / 3}

    def score_chunk(self, chunk_id: str, title: str, content: str,
                    parent_path: list[str] | None = None,
                    book_index: int = 0) -> ChunkScore:
        """Compute NLP density scores for a single chunk."""
        return ChunkScore(
            chunk_id=chunk_id,
            title=title,
            parent_path=parent_path or [],
            book_index=book_index,
            s_logic=self.nlp.calc_s_logic(content),
            s_entity=self.nlp.calc_s_entity(content),
            s_struct=self.nlp.calc_s_struct(content),
            content_preview=content[:200],
            token_count=len(content) // 2,
        )

    def score_chunks(self, chunks: list[dict]) -> list[ChunkScore]:
        """Score multiple chunks.

        Each dict must have keys: id, title, content.
        Optional: parent_path, book_index.
        """
        return [
            self.score_chunk(
                chunk_id=c["id"],
                title=c["title"],
                content=c["content"],
                parent_path=c.get("parent_path", []),
                book_index=c.get("book_index", i),
            )
            for i, c in enumerate(chunks)
        ]

    def calibrate_weights(self, scores: list[ChunkScore],
                          gold_scores: dict[str, float]) -> dict[str, float]:
        """Calibrate weights using LLM-provided gold scores.

        Args:
            scores: list of ChunkScore with NLP features computed
            gold_scores: mapping chunk_id -> gold score (0-100)

        Returns:
            Updated weights dict.
        """
        X, y = [], []
        for s in scores:
            if s.chunk_id in gold_scores:
                s.gold_score = gold_scores[s.chunk_id]
                X.append([s.s_logic, s.s_entity, s.s_struct])
                y.append(s.gold_score)

        if len(X) < 3:
            return self.weights

        X_arr = np.array(X)
        y_arr = np.array(y)

        reg = LinearRegression(fit_intercept=False, positive=True)
        reg.fit(X_arr, y_arr)

        w = reg.coef_
        w = w / w.sum() if w.sum() > 0 else np.array([1 / 3, 1 / 3, 1 / 3])

        self.weights = {
            "w_logic": float(w[0]),
            "w_entity": float(w[1]),
            "w_struct": float(w[2]),
        }
        return self.weights

    def apply_weights(self, scores: list[ChunkScore]) -> list[ChunkScore]:
        """Apply current weights to compute final_score on each ChunkScore."""
        for s in scores:
            s.final_score = (
                self.weights["w_logic"] * s.s_logic
                + self.weights["w_entity"] * s.s_entity
                + self.weights["w_struct"] * s.s_struct
            )
        return scores

    def select_calibration_samples(self, scores: list[ChunkScore],
                                   n: int = 15) -> list[ChunkScore]:
        """Select stratified sample of chunks for LLM calibration."""
        for s in scores:
            s.final_score = (s.s_logic + s.s_entity + s.s_struct) / 3

        sorted_scores = sorted(scores, key=lambda x: x.final_score)
        total = len(sorted_scores)

        if total <= n:
            return sorted_scores

        indices = [int((i / (n - 1)) * (total - 1)) for i in range(n)]
        return [sorted_scores[i] for i in sorted(set(indices))]

    def export_results(self, scores: list[ChunkScore]) -> dict:
        """Export analysis results as a dict (JSON-serializable)."""
        ordered = sorted(scores, key=lambda x: x.book_index)
        final_scores = [s.final_score for s in scores]
        return {
            "metadata": {
                "total_chunks": len(scores),
                "weights": self.weights,
            },
            "chunks": [s.to_dict() for s in ordered],
            "statistics": {
                "mean_score": float(np.mean(final_scores)) if final_scores else 0,
                "std_score": float(np.std(final_scores)) if final_scores else 0,
                "max_score": float(max(final_scores)) if final_scores else 0,
                "min_score": float(min(final_scores)) if final_scores else 0,
            },
        }
