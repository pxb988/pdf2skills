"""Tests for LLM PDF parser."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.pdf_parser.llm_parser import LLMPDFParser, _MAX_CHARS_PER_CHUNK
from src.pipeline.config import LLMProviderConfig


class TestLLMPDFParserSplitText:
    def test_short_text(self):
        chunks = LLMPDFParser._split_text("hello world")
        assert chunks == ["hello world"]

    def test_exact_limit(self):
        text = "a" * _MAX_CHARS_PER_CHUNK
        chunks = LLMPDFParser._split_text(text)
        assert len(chunks) == 1

    def test_over_limit_paragraph_break(self):
        part1 = "a" * (_MAX_CHARS_PER_CHUNK - 100)
        part2 = "b" * 200
        text = part1 + "\n\n" + part2
        chunks = LLMPDFParser._split_text(text)
        assert len(chunks) == 2
        assert chunks[0] == part1
        assert chunks[1] == part2

    def test_over_limit_no_break(self):
        text = "a" * (_MAX_CHARS_PER_CHUNK + 100)
        chunks = LLMPDFParser._split_text(text)
        assert len(chunks) == 2
        assert len(chunks[0]) == _MAX_CHARS_PER_CHUNK


class TestLLMPDFParserParse:
    @patch("src.pdf_parser.llm_parser.LLMClient")
    def test_parse_writes_output(self, MockClient, tmp_path):
        mock_instance = MagicMock()
        mock_instance.chat.return_value = "# Title\n\nSome content"
        MockClient.return_value = mock_instance

        config = LLMProviderConfig(api_key="sk-test", model="m", base_url="http://x/v1")
        parser = LLMPDFParser(config)

        # Patch _extract_raw_text to avoid needing a real PDF
        with patch.object(parser, "_extract_raw_text", return_value="raw text"):
            output_dir = tmp_path / "out"
            result = parser.parse(Path("fake.pdf"), output_dir)

        assert result == "# Title\n\nSome content"
        assert (output_dir / "full.md").read_text() == result
        mock_instance.chat.assert_called_once()

    @patch("src.pdf_parser.llm_parser.LLMClient")
    def test_parse_multiple_chunks(self, MockClient, tmp_path):
        mock_instance = MagicMock()
        mock_instance.chat.side_effect = ["Part 1 md", "Part 2 md"]
        MockClient.return_value = mock_instance

        config = LLMProviderConfig(api_key="sk-test", model="m", base_url="http://x/v1")
        parser = LLMPDFParser(config)

        long_text = "a" * (_MAX_CHARS_PER_CHUNK + 100)
        with patch.object(parser, "_extract_raw_text", return_value=long_text):
            result = parser.parse(Path("fake.pdf"), tmp_path / "out")

        assert "Part 1 md" in result
        assert "Part 2 md" in result
        assert mock_instance.chat.call_count == 2
