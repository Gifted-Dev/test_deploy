import re


def clean_text(text: str) -> str:
    """Clean extracted texts."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    return text
