"""Simulate machine translation systems by planting known errors into reference translations.

The planted error type is stored with each candidate, so the checks can be scored against it.
Run: python -m tqe.inject   (writes data/candidates.json)
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from tqe.checks import DATA, LANGUAGES, NEGATION, load_glossary, words

SYSTEMS = {
    "Reference": {"error_rate": 0.0, "errors": []},
    "System A": {"error_rate": 0.25, "errors": ["omission", "addition"],
                 "description": "Fluent, occasionally drops or adds a clause"},
    "System B": {"error_rate": 0.6, "errors": ["drop_negation", "change_number", "swap_unit"],
                 "description": "Fast, mishandles negation, numbers and units"},
    "System C": {"error_rate": 0.6, "errors": ["false_friend", "untranslated", "addition"],
                 "description": "Literal, uses false friends and leaves English words",
                 "always_first": "false_friend"},
}

ADDITIONS = {
    "es": ", y llame a su médico si tiene fiebre",
    "pl": ", a w razie gorączki zadzwonić do lekarza",
    "pt": ", e ligue para o médico se tiver febre",
}
CONJUNCTIONS = {"es": [" y ", " ni "], "pl": [" i ", " ani "], "pt": [" e ", " nem "]}
UNIT_SWAPS = {
    "es": [("mg", "ml"), ("ml", "mg"), ("horas", "días"), ("días", "semanas")],
    "pl": [("mg", "ml"), ("ml", "mg"), ("godzin", "dni"), ("dni", "tygodni")],
    "pt": [("mg", "ml"), ("ml", "mg"), ("horas", "dias"), ("dias", "semanas")],
}


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _body(text: str) -> tuple[str, str]:
    return (text[:-1], text[-1]) if text and text[-1] in ".!?" else (text, "")


def drop_negation(source: str, target: str, lang: str) -> str | None:
    pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, NEGATION[lang])) + r")\b\s*", re.IGNORECASE)
    if not pattern.search(target) or not any(w in NEGATION["en"] for w in words(source)):
        return None
    return _capitalize(pattern.sub("", target))


def change_number(source: str, target: str, lang: str) -> str | None:
    match = re.search(r"\d+", target)
    if not match:
        return None
    return target[: match.start()] + str(int(match.group()) * 10) + target[match.end():]


def swap_unit(source: str, target: str, lang: str) -> str | None:
    for old, new in UNIT_SWAPS[lang]:
        pattern = re.compile(rf"(\d+\s+){re.escape(old)}\b")
        if pattern.search(target):
            return pattern.sub(rf"\g<1>{new}", target, count=1)
    return None


def omission(source: str, target: str, lang: str) -> str | None:
    body, end = _body(target)
    if ", " in body:
        return body.rsplit(", ", 1)[0] + end
    for conj in CONJUNCTIONS[lang]:
        if conj in body:
            return body.rsplit(conj, 1)[0] + end
    parts = body.split()
    if len(parts) < 5:
        return None
    return " ".join(parts[: len(parts) - len(parts) // 3]) + end


def addition(source: str, target: str, lang: str) -> str | None:
    body, end = _body(target)
    return body + ADDITIONS[lang] + end


def _glossary_rules(source: str, lang: str):
    for term, entry in load_glossary().items():
        if term in source.lower() and lang in entry:
            yield term, entry[lang]


def false_friend(source: str, target: str, lang: str) -> str | None:
    for _, rule in _glossary_rules(source, lang):
        if "false_friend" in rule:
            old, new = rule["false_friend"]
            if old in target:
                return target.replace(old, new, 1)
    return None


def untranslated(source: str, target: str, lang: str) -> str | None:
    for term, rule in _glossary_rules(source, lang):
        for approved in rule["approved"]:
            match = re.search(re.escape(approved) + r"[^\W\d_]*", target, re.IGNORECASE)
            if match:
                return target[: match.start()] + term + target[match.end():]
    return None


INJECTORS = {
    "omission": omission,
    "addition": addition,
    "drop_negation": drop_negation,
    "change_number": change_number,
    "swap_unit": swap_unit,
    "false_friend": false_friend,
    "untranslated": untranslated,
}


def build_candidates(phrases: list[dict], seed: int = 7) -> list[dict]:
    candidates = []
    for phrase in phrases:
        for lang in LANGUAGES:
            reference = phrase[lang]
            for system, profile in SYSTEMS.items():
                rng = random.Random(f"{seed}-{system}-{phrase['id']}-{lang}")
                target, planted = reference, None
                first = profile.get("always_first")
                if first and INJECTORS[first](phrase["en"], reference, lang):
                    target, planted = INJECTORS[first](phrase["en"], reference, lang), first
                elif profile["errors"] and rng.random() < profile["error_rate"]:
                    options = profile["errors"][:]
                    rng.shuffle(options)
                    for error in options:
                        injected = INJECTORS[error](phrase["en"], reference, lang)
                        if injected and injected != reference:
                            target, planted = injected, error
                            break
                candidates.append({
                    "id": f"{phrase['id']}-{lang}-{system.split()[-1].lower()}",
                    "phrase_id": phrase["id"],
                    "lang": lang,
                    "system": system,
                    "source": phrase["en"],
                    "reference": reference,
                    "target": target,
                    "planted_error": planted,
                })
    return candidates


def main() -> None:
    phrases = json.loads((DATA / "phrases.json").read_text(encoding="utf-8"))
    candidates = build_candidates(phrases)
    out = DATA / "candidates.json"
    out.write_text(json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    planted = sum(1 for c in candidates if c["planted_error"])
    print(f"Wrote {len(candidates)} candidates ({planted} with a planted error) to {out}")


if __name__ == "__main__":
    main()
