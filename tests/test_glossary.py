import tempfile

from pdf_translator.core.glossary import Glossary, load_builtin_pack, load_glossary


def test_load_csv_2col():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("source,target\ntransformer,트랜스포머\nattention,어텐션\n")
        f.flush()
        g = Glossary.from_csv(f.name)
    assert g.get("transformer") == "트랜스포머"
    assert g.get("attention") == "어텐션"

def test_load_csv_3col_keep():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("source,target,rule\nAPI,API,keep\nmethod,방법,translate\n")
        f.flush()
        g = Glossary.from_csv(f.name)
    assert g.get("API") == "API"
    assert g.get("method") == "방법"
    assert "API" in g.keep_terms

def test_load_dict():
    g = Glossary.from_dict({"transformer": "트랜스포머", "GPU": "GPU"})
    assert g.get("transformer") == "트랜스포머"
    assert "GPU" in g.keep_terms

def test_merge_priority():
    builtin = Glossary.from_dict({"API": "API", "transformer": "transformer"})
    user = Glossary.from_dict({"transformer": "트랜스포머"})
    merged = Glossary.merge(builtin, user)
    assert merged.get("transformer") == "트랜스포머"
    assert merged.get("API") == "API"

def test_to_prompt_dict():
    g = Glossary.from_dict({"API": "API", "method": "방법"})
    d = g.to_prompt_dict()
    assert d["API"] == "API"
    assert d["method"] == "방법"

def test_builtin_packs_exist():
    cs = load_builtin_pack("cs-general")
    assert cs is not None
    assert "API" in cs.to_prompt_dict()

def test_load_unknown_pack_returns_none():
    assert load_builtin_pack("nonexistent") is None

def test_load_glossary_dict():
    g = load_glossary({"test": "테스트"})
    assert g.get("test") == "테스트"

def test_load_glossary_none():
    assert load_glossary(None) is None


def test_builtin_medical():
    g = load_builtin_pack("medical")
    assert g is not None
    assert g.get("DNA") == "DNA"
    assert g.get("placebo") == "위약"
    assert "DNA" in g.keep_terms


def test_builtin_legal():
    g = load_builtin_pack("legal")
    assert g is not None
    assert g.get("GDPR") == "GDPR"
    assert g.get("jurisdiction") == "관할권"


def test_builtin_finance():
    g = load_builtin_pack("finance")
    assert g is not None
    assert g.get("ETF") == "ETF"
    assert g.get("dividend") == "배당"
