"""PDF Translator — core re-exports for backward compatibility."""
from pdf_translator.core.extractor import Element, extract_pdf, parse_elements
from pdf_translator.core.config import TranslatorConfig
from pdf_translator.core.chunker import build_batches
from pdf_translator.core.cache import TranslationCache
from pdf_translator.core.md_builder import build_markdown
from pdf_translator.core.pdf_builder import build_pdf
