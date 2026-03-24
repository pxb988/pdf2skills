"""PDF parser that uses an LLM API to convert raw text to structured Markdown.

Flow: PyPDF2 extracts raw text → LLM API converts to clean Markdown.
Works with any OpenAI-compatible provider.
"""

from __future__ import annotations

from pathlib import Path

from .base import PDFParser
from ..llm.client import ChatMessage, LLMClient
from ..pipeline.config import LLMProviderConfig

_SYSTEM_PROMPT = """\
You are a document formatting assistant. Convert the raw text extracted from \
a PDF into well-structured Markdown. Follow these rules:

1. Preserve ALL content — do not summarize or omit anything.
2. Use proper heading hierarchy (# for title, ## for chapters, ### for sections).
3. Format lists, tables, and code blocks where appropriate.
4. Remove page headers/footers, page numbers, and watermarks.
5. Merge hyphenated line breaks (e.g., "knowl-\\nedge" → "knowledge").
6. Keep the original language of the document.
7. Output ONLY the Markdown content — no explanations or preamble."""

_MAX_CHARS_PER_CHUNK = 30_000


class LLMPDFParser(PDFParser):
    """Parse PDFs by extracting raw text with PyPDF2 then reformatting via LLM."""

    def __init__(self, provider_config: LLMProviderConfig) -> None:
        self._client = LLMClient(provider_config)

    def parse(self, pdf_path: Path, output_dir: Path) -> str:
        raw_text = self._extract_raw_text(pdf_path)
        chunks = self._split_text(raw_text)

        markdown_parts: list[str] = []
        for i, chunk in enumerate(chunks):
            print(f"  [LLM Parser] Processing chunk {i + 1}/{len(chunks)} ({len(chunk):,} chars)...", flush=True)
            user_msg = (
                f"Convert this raw PDF text (part {i + 1}/{len(chunks)}) "
                f"to structured Markdown:\n\n{chunk}"
            )
            result = self._client.chat([
                ChatMessage(role="system", content=_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ])
            markdown_parts.append(result)
            print(f"  [LLM Parser] Chunk {i + 1} done ({len(result):,} chars output)", flush=True)

        markdown = "\n\n".join(markdown_parts)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "full.md").write_text(markdown, encoding="utf-8")
        return markdown

    @staticmethod
    def _extract_raw_text(pdf_path: Path) -> str:
        try:
            from PyPDF2 import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PyPDF2 is required for LLM PDF parsing. "
                "Install with: pip install PyPDF2"
            ) from exc

        reader = PdfReader(str(pdf_path))
        pages: list[str] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i + 1}]\n{text}")
        return "\n\n".join(pages)

    @staticmethod
    def _split_text(text: str) -> list[str]:
        """Split text into chunks that fit within the LLM context."""
        if len(text) <= _MAX_CHARS_PER_CHUNK:
            return [text]

        chunks: list[str] = []
        while text:
            if len(text) <= _MAX_CHARS_PER_CHUNK:
                chunks.append(text)
                break
            # Find a paragraph break near the limit
            split_at = text.rfind("\n\n", 0, _MAX_CHARS_PER_CHUNK)
            if split_at == -1:
                split_at = text.rfind("\n", 0, _MAX_CHARS_PER_CHUNK)
            if split_at == -1:
                split_at = _MAX_CHARS_PER_CHUNK
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
