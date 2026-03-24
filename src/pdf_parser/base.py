"""Abstract base for PDF parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PDFParser(ABC):
    """Interface for converting a PDF file to Markdown text."""

    @abstractmethod
    def parse(self, pdf_path: Path, output_dir: Path) -> str:
        """Parse a PDF and return the extracted Markdown content.

        Also writes the result to output_dir/full.md.
        """
        ...
