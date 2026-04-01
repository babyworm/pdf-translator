import tempfile
from pathlib import Path

from pdf_translator.core.cache import TranslationCache


def test_cache_miss():
    with tempfile.TemporaryDirectory() as d:
        cache = TranslationCache(Path(d) / "cache.db")
        result = cache.get("hello", "en", "ko")
        assert result is None


def test_cache_put_and_get():
    with tempfile.TemporaryDirectory() as d:
        cache = TranslationCache(Path(d) / "cache.db")
        cache.put("hello", "en", "ko", "안녕하세요")
        assert cache.get("hello", "en", "ko") == "안녕하세요"


def test_cache_different_langs():
    with tempfile.TemporaryDirectory() as d:
        cache = TranslationCache(Path(d) / "cache.db")
        cache.put("hello", "en", "ko", "안녕하세요")
        cache.put("hello", "en", "ja", "こんにちは")
        assert cache.get("hello", "en", "ko") == "안녕하세요"
        assert cache.get("hello", "en", "ja") == "こんにちは"


def test_cache_persistence():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "cache.db"
        cache1 = TranslationCache(db_path)
        cache1.put("test", "en", "ko", "테스트")
        cache1.flush()
        cache1.close()

        cache2 = TranslationCache(db_path)
        assert cache2.get("test", "en", "ko") == "테스트"
        cache2.close()
