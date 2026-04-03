import pytest

from pdf_translator.core.chunker import build_batches, is_math
from pdf_translator.core.extractor import Element


def _el(content: str, page: int = 1) -> Element:
    return Element(
        type="paragraph", content=content, page_number=page,
        bbox=[0, 0, 100, 20],
    )

def test_single_batch():
    elements = [_el("Hello world."), _el("Goodbye world.")]
    batches = build_batches(elements)
    assert len(batches) == 1
    assert len(batches[0]) == 2


def test_split_by_count():
    elements = [_el(f"Item {i} is here.") for i in range(50)]
    batches = build_batches(elements, max_segments=40)
    assert len(batches) == 2
    assert len(batches[0]) == 40
    assert len(batches[1]) == 10


def test_merge_split_sentences():
    """Elements without sentence-ending punctuation are merged."""
    elements = [_el("This is the first half"), _el("of the sentence.")]
    batches = build_batches(elements)
    texts = [e.content for batch in batches for e in batch]
    assert len(texts) == 1
    assert texts[0] == "This is the first half of the sentence."


def test_no_merge_complete_sentences():
    """Complete sentences stay separate."""
    elements = [_el("First sentence."), _el("Second sentence.")]
    batches = build_batches(elements)
    texts = [e.content for batch in batches for e in batch]
    assert len(texts) == 2


def test_merge_skips_over_license():
    """Sentence fragments are reconnected across license-like elements."""
    elements = [
        _el("This is a sentence"),
        _el("Copyright 2024 Some Corp"),
        _el("that continues here."),
    ]
    batches = build_batches(elements)
    texts = [e.content for batch in batches for e in batch]
    # Fragments should be merged, skipping the license element
    assert "This is a sentence that continues here." in texts
    # License element is excluded from translation batches
    assert not any("Copyright" in t for t in texts)


def test_merge_skips_over_math():
    """Sentence fragments are reconnected across math elements."""
    elements = [
        _el("We define the function"),
        _el("FFN(x) = max(0,xW1 + b1)W2 + b2"),
        _el("for all input vectors."),
    ]
    batches = build_batches(elements)
    texts = [e.content for batch in batches for e in batch]
    assert "We define the function for all input vectors." in texts


def test_split_by_chars():
    elements = [_el("a" * 1999 + ".") for _ in range(5)]
    batches = build_batches(elements, max_chars=4500)
    assert len(batches) >= 3


def test_empty_input():
    assert build_batches([]) == []


def test_skips_empty_content():
    elements = [_el(""), _el("real text"), _el("   ")]
    batches = build_batches(elements)
    assert len(batches) == 1
    assert len(batches[0]) == 1


# --- is_math tests ---

class TestIsMath:
    """Test math formula detection."""

    # Should be detected as math (skipped from translation)
    @pytest.mark.parametrize("text", [
        "Attention(Q,K,V ) = softmax(QKT√dk)V",          # attention formula
        "MultiHead(Q,K,V ) = Concat(head1,...,headh)WO",  # multihead formula
        "headi = Attention(QWiQ,KWiK,V WiV )",            # head definition
        "FFN(x) = max(0,xW1 + b1)W2 + b2 (2)",           # FFN formula
        "L(C) = aCb + c",                                  # loss formula
        "∑i=1 xi",                                         # summation
        "WiK ∈ Rd",                                        # set membership
        ")V (1)",                                           # formula fragment
        "model×dk, WiV ∈ Rd",                              # variable declaration
    ])
    def test_math_detected(self, text):
        assert is_math(text), f"Should be math: {text!r}"

    # Should NOT be detected as math (must be translated)
    @pytest.mark.parametrize("text", [
        "Attention Is All You Need",
        "Abstract",
        "1 Introduction",
        "3.1 Encoder and Decoder Stacks",
        "Recurrent neural networks, long short-term memory and gated recurrent neural networks",
        "Figure 1: The Transformer - model architecture.",
        "We propose a new simple network architecture, the Transformer.",
        "In this work we employ h = 8 parallel attention layers, or heads. For each of these we use dk = dv = 64.",
        "While the linear transformations are the same across different positions, they use different parameters.",
        "4To illustrate why the dot products get large, assume that the components of q and k are independent.",
        "Provided proper attribution is provided, Google hereby grants permission",
        "Google Brain avaswani@google.com",
    ])
    def test_not_math(self, text):
        assert not is_math(text), f"Should NOT be math: {text!r}"

    def test_skips_math_in_batches(self):
        """Math elements should be excluded from translation batches."""
        elements = [
            _el("Normal text to translate."),
            _el("FFN(x) = max(0,xW1 + b1)W2 + b2"),
            _el("Another normal paragraph."),
        ]
        batches = build_batches(elements)
        all_texts = [e.content for batch in batches for e in batch]
        assert "Normal text to translate." in all_texts
        assert "Another normal paragraph." in all_texts
        assert "FFN(x) = max(0,xW1 + b1)W2 + b2" not in all_texts
