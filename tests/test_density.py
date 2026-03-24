"""Tests for NLP density scoring."""

import pytest
from src.nlp.density import NLPAnalyzer, DensityAnalyzer, ChunkScore


class TestNLPAnalyzer:
    def setup_method(self):
        self.nlp = NLPAnalyzer(language="English")

    def test_calc_s_logic_with_connectives(self):
        text = (
            "If the revenue exceeds the threshold, then the company must "
            "report because regulatory requirements demand it. However, "
            "unless the board approves, the disclosure should be delayed."
        )
        score = self.nlp.calc_s_logic(text)
        assert score > 0, "Text with many connectives should have positive logic score"

    def test_calc_s_logic_low_for_simple_text(self):
        text = "The cat sat on the mat. The dog barked."
        score = self.nlp.calc_s_logic(text)
        text_complex = (
            "If the temperature rises, then the reaction must accelerate "
            "because the kinetic energy increases. Therefore, the yield should improve."
        )
        score_complex = self.nlp.calc_s_logic(text_complex)
        assert score_complex > score

    def test_calc_s_struct_lists(self):
        text = (
            "# Header\n\n"
            "- Item one\n"
            "- Item two\n"
            "- Item three\n\n"
            "1. First step\n"
            "2. Second step\n"
        )
        score = self.nlp.calc_s_struct(text)
        assert score > 0, "Text with lists should have positive struct score"

    def test_calc_s_struct_tables(self):
        text = (
            "| Name | Value |\n"
            "|------|-------|\n"
            "| A    | 100   |\n"
            "| B    | 200   |\n"
        )
        score = self.nlp.calc_s_struct(text)
        assert score > 0

    def test_calc_s_struct_code_blocks(self):
        text = "Some text\n\n```python\nx = 1\ny = 2\n```\n\nMore text"
        score = self.nlp.calc_s_struct(text)
        assert score > 0

    def test_calc_s_entity_numbers(self):
        text = "The ROI was 15.3% with a P/E ratio of 22.5 and revenue of $1.2M."
        score = self.nlp.calc_s_entity(text)
        assert score > 0

    def test_language_detection(self):
        nlp_auto = NLPAnalyzer(language="auto")
        assert nlp_auto._detect_language("Hello world") == "English"
        assert nlp_auto._detect_language("你好世界这是中文文本") == "Chinese"

    def test_scores_bounded(self):
        long_text = "If then because therefore however " * 100
        assert self.nlp.calc_s_logic(long_text) <= 100
        assert self.nlp.calc_s_entity(long_text) <= 100
        assert self.nlp.calc_s_struct(long_text) <= 100


class TestDensityAnalyzer:
    def test_score_chunk(self):
        analyzer = DensityAnalyzer(language="English")
        score = analyzer.score_chunk(
            chunk_id="test_001",
            title="Test Chunk",
            content="If revenue > threshold, then report the finding because regulations require it.",
        )
        assert isinstance(score, ChunkScore)
        assert score.chunk_id == "test_001"
        assert score.s_logic >= 0
        assert score.s_entity >= 0
        assert score.s_struct >= 0

    def test_score_chunks(self):
        analyzer = DensityAnalyzer(language="English")
        chunks = [
            {"id": "c1", "title": "A", "content": "Simple text here."},
            {"id": "c2", "title": "B", "content": "If X then Y because Z."},
        ]
        scores = analyzer.score_chunks(chunks)
        assert len(scores) == 2

    def test_calibrate_weights(self):
        analyzer = DensityAnalyzer(language="English")
        scores = [
            ChunkScore("c1", "A", [], s_logic=10, s_entity=20, s_struct=30),
            ChunkScore("c2", "B", [], s_logic=50, s_entity=60, s_struct=70),
            ChunkScore("c3", "C", [], s_logic=80, s_entity=40, s_struct=10),
            ChunkScore("c4", "D", [], s_logic=30, s_entity=70, s_struct=50),
        ]
        gold = {"c1": 20, "c2": 60, "c3": 50, "c4": 55}
        weights = analyzer.calibrate_weights(scores, gold)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_apply_weights(self):
        analyzer = DensityAnalyzer(language="English")
        scores = [ChunkScore("c1", "A", [], s_logic=30, s_entity=40, s_struct=50)]
        analyzer.apply_weights(scores)
        expected = 30 / 3 + 40 / 3 + 50 / 3
        assert abs(scores[0].final_score - expected) < 0.01

    def test_export_results(self):
        analyzer = DensityAnalyzer(language="English")
        scores = [
            ChunkScore("c1", "A", [], s_logic=10, s_entity=20, s_struct=30, final_score=20),
            ChunkScore("c2", "B", [], s_logic=50, s_entity=60, s_struct=70, final_score=60),
        ]
        result = analyzer.export_results(scores)
        assert result["metadata"]["total_chunks"] == 2
        assert "statistics" in result
        assert len(result["chunks"]) == 2

    def test_select_calibration_samples(self):
        analyzer = DensityAnalyzer(language="English")
        scores = [
            ChunkScore(f"c{i}", f"T{i}", [], s_logic=i * 5, s_entity=i * 3, s_struct=i * 2)
            for i in range(30)
        ]
        samples = analyzer.select_calibration_samples(scores, n=10)
        assert len(samples) <= 10
        assert len(samples) > 0
