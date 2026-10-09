"""Reference-free quality checks for clinical translations (English to es, pl, pt)."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
LANGUAGES = ("es", "pl", "pt")

SEVERITY_PENALTY = {"critical": 25, "major": 5, "minor": 1}

NEGATION = {
    "en": {"not", "never", "no", "don't", "dont"},
    "es": {"no", "nunca", "jamás"},
    "pl": {"nie", "nigdy"},
    "pt": {"não", "nunca", "jamais"},
}

UNITS = {
    "mg": {"mg"},
    "ml": {"ml"},
    "litre": {"litres", "liters", "litre", "liter", "litros", "litro", "litry", "litrów"},
    "unit": {"units", "unidades", "jednostek", "jednostki"},
    "hour": {"hours", "horas", "godzin", "godziny"},
    "day": {"days", "días", "dias", "dni"},
    "week": {"weeks", "semanas", "tygodni", "tygodnie"},
}
_UNIT_OF = {word: unit for unit, words in UNITS.items() for word in words}

# Typical target/source character-length ratio on clean clinical sentences.
LENGTH_RATIO = {"es": (0.8, 1.45), "pl": (0.9, 1.75), "pt": (0.85, 1.45)}

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?|\d+(?:[.,]\d+)?", re.UNICODE)


@dataclass
class Issue:
    check: str
    severity: str
    message: str
    spans: list[str] = field(default_factory=list)


@dataclass
class Result:
    lang: str
    source: str
    target: str
    issues: list[Issue]

    @property
    def score(self) -> int:
        return max(0, 100 - sum(SEVERITY_PENALTY[i.severity] for i in self.issues))

    @property
    def verdict(self) -> str:
        severities = {i.severity for i in self.issues}
        if "critical" in severities:
            return "FAIL"
        if severities:
            return "REVIEW"
        return "PASS"

    def to_dict(self) -> dict:
        return {
            "lang": self.lang,
            "source": self.source,
            "target": self.target,
            "score": self.score,
            "verdict": self.verdict,
            "issues": [asdict(i) for i in self.issues],
        }


@lru_cache(maxsize=1)
def load_glossary() -> dict:
    return json.loads((DATA / "glossary.json").read_text(encoding="utf-8"))


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def quantities(text: str) -> list[tuple[str, str | None, str | None]]:
    """Return (number, canonical unit, unit word as written) for each number in the text."""
    tokens = words(text)
    found = []
    for i, token in enumerate(tokens):
        if token[0].isdigit():
            unit_word = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1] in _UNIT_OF else None
            found.append((token.replace(",", "."), _UNIT_OF.get(unit_word), unit_word))
    return found


def check_numbers(source: str, target: str) -> list[Issue]:
    src, tgt = quantities(source), quantities(target)
    src_numbers, tgt_numbers = Counter(n for n, *_ in src), Counter(n for n, *_ in tgt)
    issues = []
    missing = src_numbers - tgt_numbers
    extra = tgt_numbers - src_numbers
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(sorted(missing.elements())))
        if extra:
            parts.append("unexpected " + ", ".join(sorted(extra.elements())))
        issues.append(Issue("number_mismatch", "critical", "Numbers differ from source: " + "; ".join(parts),
                            sorted(set(extra.elements()))))
        return issues

    src_units = {n: u for n, u, _ in src if u}
    for number, unit, unit_word in tgt:
        if unit and number in src_units and src_units[number] != unit:
            issues.append(Issue("unit_mismatch", "critical",
                                f"{number} is '{src_units[number]}' in the source but '{unit}' in the translation",
                                [_surface(target, unit_word)]))
    return issues


def check_negation(source: str, target: str, lang: str) -> list[Issue]:
    if not any(w in NEGATION["en"] for w in words(source)) and "n't" not in source.lower():
        return []
    if any(w in NEGATION[lang] for w in words(target)):
        return []
    return [Issue("negation_dropped", "critical",
                  "Source is a prohibition ('do not' / 'never') but the translation has no negation")]


def check_terminology(source: str, target: str, lang: str) -> list[Issue]:
    issues = []
    src, tgt = source.lower(), target.lower()
    for term, entry in load_glossary().items():
        if term not in src or lang not in entry:
            continue
        rule = entry[lang]
        forbidden = [f for f in rule.get("forbidden", []) if f in tgt]
        if forbidden:
            issues.append(Issue("forbidden_term", "critical",
                                f"'{term}' translated with a false friend. {rule.get('note', '')}".strip(),
                                [_surface(target, f) for f in forbidden]))
        elif not any(a in tgt for a in rule["approved"]):
            issues.append(Issue("missing_term", "major",
                                f"Expected an approved translation of '{term}': {', '.join(rule['approved'])}"))
    return issues


def check_untranslated(source: str, target: str) -> list[Issue]:
    src_words = {w for w in words(source) if len(w) >= 4 and not w[0].isdigit()}
    left = sorted({w for w in words(target) if w in src_words})
    if not left:
        return []
    return [Issue("untranslated", "major", "English words left in the translation: " + ", ".join(left),
                  [_surface(target, w) for w in left])]


def check_length(source: str, target: str, lang: str) -> list[Issue]:
    low, high = LENGTH_RATIO[lang]
    ratio = len(target) / max(len(source), 1)
    if low <= ratio <= high:
        return []
    kind = "shorter" if ratio < low else "longer"
    return [Issue("length_ratio", "minor",
                  f"Translation is {ratio:.2f}x the source length, {kind} than usual; check for "
                  f"{'omitted' if kind == 'shorter' else 'added'} content")]


def _surface(text: str, needle: str) -> str:
    match = re.search(re.escape(needle) + r"[^\W\d_]*", text, re.IGNORECASE)
    return match.group(0) if match else needle


def check(source: str, target: str, lang: str) -> Result:
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported language '{lang}', expected one of {LANGUAGES}")
    issues = (
        check_numbers(source, target)
        + check_negation(source, target, lang)
        + check_terminology(source, target, lang)
        + check_untranslated(source, target)
        + check_length(source, target, lang)
    )
    return Result(lang, source, target, issues)
