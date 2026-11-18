"""Name and number standardisation, driven by the `standardise` section of a rule file.

Every option is off unless the rule file turns it on, so a participant sees the effect of each one.
"""
from __future__ import annotations

import re

DIACRITICS = re.compile("[ً-ْٰ]")
ARABIC = re.compile("[؀-ۿ]")
NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)

# Arabic letters and Latin letters share one consonant class each, for the cross-script key.
AR_CLASS = {
    "ب": "b", "ت": "t", "ط": "t", "ث": "t", "ج": "j", "غ": "j", "خ": "k", "ك": "k", "ق": "k",
    "د": "d", "ض": "d", "ذ": "d", "ظ": "d", "ر": "r", "ز": "z", "س": "s", "ص": "s", "ش": "s",
    "ف": "f", "ل": "l", "م": "m", "ن": "n",
}
LATIN_DIGRAPHS = [("kh", "k"), ("sh", "s"), ("th", "t"), ("dh", "d"), ("gh", "j"), ("ph", "f")]
LATIN_CLASS = {"b": "b", "p": "b", "t": "t", "j": "j", "g": "j", "k": "k", "q": "k", "c": "k", "d": "d",
               "r": "r", "z": "z", "s": "s", "f": "f", "v": "f", "l": "l", "m": "m", "n": "n"}


def is_arabic(text: str) -> bool:
    return bool(ARABIC.search(text or ""))


def arabic(text: str, o: dict) -> str:
    if o.get("remove_diacritics"):
        text = DIACRITICS.sub("", text)
    if o.get("remove_tatweel"):
        text = text.replace("ـ", "")
    if o.get("unify_alef"):
        text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    if o.get("taa_marbuta"):
        text = re.sub("ة(?=\\s|$)", "ه", text)
    if o.get("alef_maqsura"):
        text = re.sub("ى(?=\\s|$)", "ي", text)
    return text


def latin(text: str, o: dict) -> str:
    if o.get("lowercase", True):
        text = text.lower()
    if o.get("unify_article"):
        text = re.sub(r"\b(al|el)[-\s]+", "al ", text, flags=re.IGNORECASE)
    return text


def name(text: str, opts: dict, remove: set[str] | None = None) -> str | None:
    """The standardised form of a name, in its own script."""
    if not text or not text.strip():
        return None
    o_ar = opts.get("arabic", {}) or {}
    o_la = opts.get("latin", {}) or {}
    t = arabic(text, o_ar) if is_arabic(text) else latin(text, o_la)
    if opts.get("strip_punctuation"):
        t = NON_WORD.sub(" ", t.replace("&", " and "))
    toks = t.split()
    if remove:
        toks = [x for x in toks if x not in remove]
    out = " ".join(toks)
    return out or None


def remove_set(opts: dict) -> set[str]:
    """The words to remove, standardised with the same options as the names."""
    words = opts.get("remove_words") or []
    out = set()
    for w in words:
        s = name(str(w), {**opts, "remove_words": []})
        if s:
            out.update(s.split())
    return out


def skeleton(std: str | None) -> str | None:
    """Cross-script key: the consonant classes of each word, without articles, vowels or h/w/y."""
    if not std:
        return None
    parts = []
    for tok in std.split():
        if is_arabic(tok):
            if tok.startswith("ال") and len(tok) > 3:
                tok = tok[2:]
            if tok.startswith("لل") and len(tok) > 3:
                tok = tok[2:]
            sk = "".join(AR_CLASS.get(ch, "") for ch in tok)
        else:
            if tok in ("al", "el"):
                continue
            if (tok.startswith("al") or tok.startswith("el")) and len(tok) > 5:
                tok = tok[2:]
            for a, b in LATIN_DIGRAPHS:
                tok = tok.replace(a, b)
            sk = "".join(LATIN_CLASS.get(ch, "") for ch in tok)
        sk = re.sub(r"(.)\1+", r"\1", sk)
        if sk:
            parts.append(sk)
    return " ".join(parts) or None


def digits(text: str | None, placeholders: list[str] | None = None) -> str | None:
    if not text:
        return None
    d = re.sub(r"\D", "", text)
    if not d or (placeholders and d in placeholders):
        return None
    return d


def phone(text: str | None) -> str | None:
    d = digits(text)
    if not d:
        return None
    if d.startswith("966"):
        d = "0" + d[3:]
    return d
