# Third-Party Licenses

pdf-translator is distributed under the MIT License. All core dependencies use
permissive licenses compatible with MIT.

## Core Dependencies

| Package | License |
|---------|---------|
| opendataloader-pdf | Apache-2.0 |
| pypdf | BSD-3-Clause |
| reportlab | BSD |
| rich | MIT |
| langdetect | Apache-2.0 |
| deep-translator | MIT |
| requests | Apache-2.0 |

## Web UI Dependencies (optional: `pip install pdf-translator[web]`)

| Package | License |
|---------|---------|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| python-multipart | Apache-2.0 |

## OCR Dependencies (optional: `pip install pdf-translator[ocr]`)

| Package | License | Note |
|---------|---------|------|
| pypdfium2 | Apache-2.0 / BSD-3-Clause | Page rendering for OCR |
| Pillow | HPND (MIT-like) | Image processing |
| pytesseract | Apache-2.0 | Tesseract OCR wrapper |
| **surya-ocr** | **GPLv3+** | ML-based OCR engine. Installing this package makes the combined runtime subject to GPLv3 terms. The pdf-translator source code itself remains MIT-licensed. |
