"""PDF parser using MinerU API.

Requires MINERU_API_KEY to be configured.
"""

from __future__ import annotations

import time
from pathlib import Path

from .base import PDFParser


class MineruParser(PDFParser):
    """Parse PDFs via the MinerU cloud API with OCR support."""

    def __init__(self, api_key: str, base_url: str = "https://mineru.net/api/v4/extract/task"):
        if not api_key:
            raise ValueError("MINERU_API_KEY is required for MinerU parser")
        self.api_key = api_key
        self.base_url = base_url

    def parse(self, pdf_path: Path, output_dir: Path) -> str:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "requests is required for MinerU parser. "
                "Install with: pip install requests"
            ) from exc

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Upload PDF
        with open(pdf_path, "rb") as f:
            resp = requests.post(
                self.base_url,
                headers=headers,
                files={"file": (pdf_path.name, f, "application/pdf")},
                timeout=60,
            )
        resp.raise_for_status()
        task_id = resp.json().get("task_id")
        if not task_id:
            raise RuntimeError(f"MinerU API did not return task_id: {resp.text}")

        # Poll for result
        status_url = f"{self.base_url}/{task_id}"
        for _ in range(120):
            time.sleep(5)
            status_resp = requests.get(status_url, headers=headers, timeout=30)
            status_resp.raise_for_status()
            data = status_resp.json()
            if data.get("status") == "completed":
                markdown = data.get("markdown", "")
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "full.md").write_text(markdown, encoding="utf-8")
                return markdown
            if data.get("status") == "failed":
                raise RuntimeError(f"MinerU extraction failed: {data.get('error')}")

        raise TimeoutError("MinerU extraction timed out after 10 minutes")
