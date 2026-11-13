"""Pure text cleaning: hidden characters, HTML, personal data, length."""

import hashlib
import re
import unicodedata
from html.parser import HTMLParser

MAX_TEXT_LENGTH = 2000

_MAX_PASSES = 5
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
# 9 to 15 digits, optionally with a +/00 prefix and spaces, dots, dashes or brackets between them.
_PHONE = re.compile(r"(?<![\w])(?:\+|00)?\d(?:[ .\-()]?\d){8,14}(?![\w])")
_SKIPPED_TAGS = frozenset({"script", "style"})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip += 1
        self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip:
            self._skip -= 1
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _strip_html(text: str) -> str:
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    # Whatever the parser left as angle brackets is not a tag; it could only fake a data delimiter.
    return "".join(parser.parts).replace("<", " ").replace(">", " ")


def _strip_hidden(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    kept = (
        " " if ch.isspace() else ch
        for ch in text
        if ch.isspace() or not unicodedata.category(ch).startswith("C")
    )
    return re.sub(r" +", " ", "".join(kept)).strip()


def clean_text(text: str) -> str:
    """Return the text without HTML and hidden characters, personal contacts masked, trimmed."""
    for _ in range(_MAX_PASSES):
        cleaned = _strip_hidden(_strip_html(_strip_hidden(text)))
        if cleaned == text:
            break
        text = cleaned
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    return text[:MAX_TEXT_LENGTH].strip()


def text_hash(text: str) -> str:
    """Hash of a cleaned text that ignores case, so a repeated Review is recognised."""
    return hashlib.sha256(text.casefold().encode()).hexdigest()
