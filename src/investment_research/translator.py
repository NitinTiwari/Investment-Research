from collections.abc import Sequence
import requests
from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
    NotValidLength,
    RequestError,
    TooManyRequests,
    TranslationNotFound,
)


def _split_into_chunks(text: str, max_chunk_size: int = 3500) -> list[str]:
    """Split text into smaller chunks by paragraphs or lines to avoid translation length limits."""
    if len(text) <= max_chunk_size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        # If single paragraph exceeds max size, split by lines
        if len(paragraph) > max_chunk_size:
            lines = paragraph.split("\n")
            for line in lines:
                if len(line) > max_chunk_size:
                    # Break long line by sentences/words
                    words = line.split(" ")
                    temp_line = ""
                    for word in words:
                        if len(temp_line) + len(word) + 1 > max_chunk_size:
                            if temp_line:
                                current_chunk.append(temp_line)
                                chunks.append("\n".join(current_chunk))
                                current_chunk = []
                                current_length = 0
                            temp_line = word
                        else:
                            temp_line = f"{temp_line} {word}".strip()
                    if temp_line:
                        current_chunk.append(temp_line)
                else:
                    if current_length + len(line) + 1 > max_chunk_size:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 1
        else:
            if current_length + len(paragraph) + 2 > max_chunk_size:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [paragraph]
                current_length = len(paragraph)
            else:
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def _fallback_google_translate(text: str, target_lang: str = "hi", source_lang: str = "auto") -> str:
    """Fallback translator using the Google translate API endpoint when web scraper is rate limited."""
    headers = {
        "User-Agent": "AndroidTranslate/5.3.0.RC02.130475354-53000263 5.1 phone TRANSLATE_60MIN_GAP",
    }
    response = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={
            "client": "at",
            "sl": source_lang,
            "tl": target_lang,
            "dt": "t",
            "q": text,
        },
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload and isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], list):
        return "".join([segment[0] for segment in payload[0] if segment and segment[0]])
    return text


def translate_chunk(chunk: str, target_lang: str = "hi", source_lang: str = "auto") -> str:
    """Translate an individual text chunk using GoogleTranslator, with API fallback if blocked."""
    if not chunk or not chunk.strip():
        return chunk

    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        result = translator.translate(chunk)
        if result:
            return result
    except (TooManyRequests, RequestError, TranslationNotFound, NotValidLength, Exception):
        pass

    # Fallback to direct client endpoint
    try:
        return _fallback_google_translate(chunk, target_lang=target_lang, source_lang=source_lang)
    except Exception:
        return chunk


def translate_text(text: str, target_lang: str = "hi", source_lang: str = "auto") -> str:
    """Translate text to the target language, preserving layout across chunks."""
    if not text or not text.strip():
        return text

    if target_lang.lower() in {"en", "english"}:
        return text

    chunks = _split_into_chunks(text)
    translated_chunks = [
        translate_chunk(chunk, target_lang=target_lang, source_lang=source_lang)
        for chunk in chunks
    ]
    return "\n\n".join(translated_chunks)


def translate_to_hindi(text: str) -> str:
    """Translate the given text to Hindi using GoogleTranslator."""
    return translate_text(text, target_lang="hi", source_lang="auto")
