"""PDF parser that delegates to Claude Code's native PDF reading.

When running inside Claude Code, the Read tool can directly read PDF
files. This parser prepares the instructions for the SubAgent to read
and structure the PDF content.

In standalone mode (outside Claude Code), falls back to PyPDF2.
"""

from __future__ import annotations

from pathlib import Path

from .base import PDFParser


class ClaudeParser(PDFParser):
    """Parse PDFs via Claude Code's Read tool or PyPDF2 fallback.

    This parser is designed to be invoked by the Claude Code Skill.
    It generates page-by-page reading instructions that the Skill's
    SubAgent uses to read the PDF via the Read tool.
    """

    def parse(self, pdf_path: Path, output_dir: Path) -> str:
        """Fall back to PyPDF2 for standalone extraction."""
        try:
            from PyPDF2 import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PyPDF2 is required for standalone PDF parsing. "
                "Install with: pip install PyPDF2"
            ) from exc

        reader = PdfReader(str(pdf_path))
        pages: list[str] = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"## Page {i + 1}\n\n{text}")

        markdown = "\n\n".join(pages)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "full.md").write_text(markdown, encoding="utf-8")
        return markdown

    @staticmethod
    def page_count(pdf_path: Path) -> int:
        """Get the number of pages in a PDF."""
        try:
            from PyPDF2 import PdfReader

            return len(PdfReader(str(pdf_path)).pages)
        except Exception:
            return 0

    @staticmethod
    def generate_read_instructions(pdf_path: Path) -> list[dict]:
        """Generate page-range reading instructions for Claude Code.

        Returns a list of dicts with 'pages' ranges (max 20 pages each)
        that can be used with the Read tool's pages parameter.
        """
        total = ClaudeParser.page_count(pdf_path)
        if total == 0:
            return [{"pages": "1-20"}]

        instructions = []
        for start in range(1, total + 1, 20):
            end = min(start + 19, total)
            instructions.append({"pages": f"{start}-{end}"})
        return instructions
