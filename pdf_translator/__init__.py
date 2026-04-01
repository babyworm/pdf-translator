"""PDF Translator — core re-exports for backward compatibility."""
from pdf_translator.core.cache import TranslationCache as TranslationCache
from pdf_translator.core.chunker import build_batches as build_batches
from pdf_translator.core.config import TranslatorConfig as TranslatorConfig
from pdf_translator.core.extractor import Element as Element
from pdf_translator.core.extractor import extract_pdf as extract_pdf
from pdf_translator.core.extractor import parse_elements as parse_elements
from pdf_translator.core.md_builder import build_markdown as build_markdown
from pdf_translator.core.pdf_builder import build_pdf as build_pdf
