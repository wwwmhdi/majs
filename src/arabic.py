"""Arabic text helpers."""
import re

# Tashkeel / diacritics to strip for subtitles (keep plain readable letters).
_TASHKEEL = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")

# Tatweel (kashida) - decorative elongation, useless in subtitles.
_TATWEEL = re.compile(r"\u0640")


def normalize_arabic(text: str) -> str:
    """Strip diacritics + tatweel and collapse whitespace.

    Keeps original letters (no aggressive substitutions) so spelling stays
    correct, while giving TTS and libass clean input.
    """
    text = _TASHKEEL.sub("", text)
    text = _TATWEEL.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def wrap_2_lines(text: str, limit: int = 48) -> list[str]:
    """Split long text into cues of at most `limit` chars at word boundaries."""
    text = normalize_arabic(text)
    if len(text) <= limit:
        return [text]
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) > limit and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines
