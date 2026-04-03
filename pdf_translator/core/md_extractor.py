"""Markdown-based PDF extraction using opendataloader's native markdown output.

This module replaces the JSON element pipeline with a simpler approach:
opendataloader markdown → clean up → translate paragraphs → output.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path


def extract_markdown(pdf_path: str, pages: str | None = None) -> str:
    """Extract markdown from PDF using opendataloader."""
    import opendataloader_pdf

    work_dir = tempfile.mkdtemp(prefix="pdf_md_")
    try:
        convert_args = dict(
            input_path=pdf_path,
            output_dir=work_dir,
            format="markdown",
        )
        if pages:
            convert_args["pages"] = pages

        opendataloader_pdf.convert(**convert_args)

        md_files = list(Path(work_dir).glob("*.md"))
        if not md_files:
            raise FileNotFoundError(f"No markdown output found in {work_dir}")

        return md_files[0].read_text(encoding="utf-8")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# Hyphen at end of line followed by paragraph break then continuation
_HYPHEN_BREAK = re.compile(r'(\w)-\s*\n\s*\n(\w)')
# Hyphen at end of line followed by single newline then continuation
_HYPHEN_SOFT = re.compile(r'(\w)-\s*\n(\w)')
# Drop cap: heading with single letter(s) followed by paragraph starting with uppercase
# Handles: "# I\n\nN RECENT", "# T\n\nHE proposed", "## A\n\nS shown"
_DROP_CAP = re.compile(r'^#+\s+([A-Z]{1,2})\s*$\n\s*\n([A-Z])', re.MULTILINE)
# References section
_REFERENCES = re.compile(r'^#+\s*(?:References|Bibliography|REFERENCES)\s*$', re.MULTILINE)
# Decorative / metadata patterns to remove or keep as-is
_DECORATIVE = re.compile(
    r'^(?:'
    r'Authorized licensed use limited to.*$|'
    r'Downloaded on\s.*$|'
    r'\d+-\d+/\$\d+\.\d+\s+©.*$'
    r')',
    re.MULTILINE,
)


def clean_markdown(md: str) -> str:
    """Clean up opendataloader markdown for translation.

    - Join hyphenated line breaks (word-\\ncontinuation → wordcontinuation)
    - Fix drop caps (# I\\n\\nN RECENT → IN RECENT)
    - Remove decorative elements (license footers, etc.)
    """
    # Fix drop caps first
    md = _DROP_CAP.sub(r'\1\2', md)

    # Join hyphenated words across paragraph breaks
    md = _HYPHEN_BREAK.sub(r'\1\2', md)
    md = _HYPHEN_SOFT.sub(r'\1\2', md)

    # Remove decorative lines
    md = _DECORATIVE.sub('', md)

    # Clean up excessive blank lines (3+ → 2)
    md = re.sub(r'\n{3,}', '\n\n', md)

    # Join paragraphs split across column/page breaks
    md = join_split_paragraphs(md)

    return md.strip()


# Sentence-ending punctuation
_SENT_END = re.compile(r'[.!?;:。！？；：…]\s*$')
# Metadata paragraphs that can appear between sentence fragments
_INTERSTITIAL = re.compile(
    r'^(?:'
    r'Manuscript received\s|'
    r'This work was supported\s|'
    r'This paper was recommended\s|'
    r'[A-Z]\.-[A-Z]\.\s\w+.*(?:are with|is with)\s|'  # author affiliations
    r'Digital Object Identi|'
    r'!\[.*?\]\(.*?\)|'                                  # image references
    r'Fig\.\s*\d|'                                       # figure captions
    r'TABLE\s+[IVX]|Table\s+[IVX]|'                     # table captions
    r'\d+\s+IEEE\s|'                                     # journal page headers
    r'[A-Z]+\s+et\s+al\.\s*:'                           # author page headers
    r')',
)


def join_split_paragraphs(md: str) -> str:
    """Join paragraphs where a sentence was split across column/page breaks.

    When a paragraph ends without sentence-ending punctuation (e.g., ends with
    a preposition like "in", "the", "to"), look ahead past metadata/image
    paragraphs and join with the continuation.
    """
    paragraphs = md.split('\n\n')
    result: list[str] = []
    i = 0

    while i < len(paragraphs):
        para = paragraphs[i].strip()
        if not para:
            i += 1
            continue

        # Only attempt joining for prose paragraphs (not headings, images, tables)
        if para.startswith('#') or para.startswith('![') or para.startswith('|'):
            result.append(para)
            i += 1
            continue

        # Skip interstitial paragraphs (metadata, page headers) — don't start joining from them
        if _INTERSTITIAL.match(para):
            result.append(para)
            i += 1
            continue

        # Short paragraphs (< 80 chars) without sentence endings are likely titles/headers
        # — don't join them with the next paragraph
        if len(para) < 80 and not _SENT_END.search(para):
            result.append(para)
            i += 1
            continue

        # Check if paragraph ends mid-sentence
        while not _SENT_END.search(para) and i + 1 < len(paragraphs):
            nxt = paragraphs[i + 1].strip()
            if not nxt:
                i += 1
                continue
            # Stop at headings, section markers, or author lines
            if (nxt.startswith('#') or nxt.startswith('Abstract')
                    or re.match(r'^[A-Z][a-z]+-[A-Z][a-z]+\s', nxt)):  # author names like "Yi-Hau Chen"
                break
            # Skip interstitial paragraphs (metadata, images, captions)
            if _INTERSTITIAL.match(nxt):
                result.append(nxt)
                i += 1
                continue
            # Join the continuation
            para = para.rstrip() + ' ' + nxt.lstrip()
            i += 1

        result.append(para)
        i += 1

    return '\n\n'.join(result)


def truncate_at_references(md: str) -> str:
    """Remove everything from the References section onward."""
    match = _REFERENCES.search(md)
    if match:
        return md[:match.start()].strip()
    return md


def split_paragraphs(md: str) -> list[str]:
    """Split markdown into translatable paragraph chunks.

    Each chunk is a paragraph separated by blank lines.
    Headings, images, and tables are kept as separate chunks.
    """
    blocks = re.split(r'\n\n+', md)
    return [b.strip() for b in blocks if b.strip()]
