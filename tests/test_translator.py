from investment_research.research_service import ResearchService
from investment_research.translator import (
    _split_into_chunks,
    translate_chunk,
    translate_text,
    translate_to_hindi,
)


def test_translate_english_noop() -> None:
    text = "Detailed equity research report for Apple Inc."
    assert translate_text(text, target_lang="en") == text
    assert translate_text(text, target_lang="English") == text


def test_translate_empty_strings() -> None:
    assert translate_text("") == ""
    assert translate_text("   ") == "   "
    assert translate_to_hindi("") == ""


def test_split_into_chunks_short_text() -> None:
    text = "Short paragraph 1\n\nShort paragraph 2"
    chunks = _split_into_chunks(text, max_chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_into_chunks_long_text() -> None:
    para1 = "A" * 300
    para2 = "B" * 300
    text = f"{para1}\n\n{para2}"
    chunks = _split_into_chunks(text, max_chunk_size=400)
    assert len(chunks) == 2
    assert chunks[0] == para1
    assert chunks[1] == para2


def test_translate_to_hindi_translates() -> None:
    text = "Hello world! This is a test."
    translated = translate_to_hindi(text)
    assert translated is not None
    assert len(translated) > 0
    # Should not be equal to original English text
    assert translated != text


def test_research_service_translate_report() -> None:
    service = ResearchService()
    text = "Market research summary"
    hindi = service.translate_report(text, target_lang="hi")
    assert hindi is not None
    assert len(hindi) > 0
