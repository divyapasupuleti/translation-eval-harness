import json

import pytest

from tqe.checks import DATA, LANGUAGES, check
from tqe.evaluate import gate_failures, run
from tqe.inject import build_candidates


def _issues(source, target, lang):
    return {i.check for i in check(source, target, lang).issues}


@pytest.fixture(scope="module")
def phrases():
    return json.loads((DATA / "phrases.json").read_text(encoding="utf-8"))


def test_every_reference_translation_passes(phrases):
    for phrase in phrases:
        for lang in LANGUAGES:
            result = check(phrase["en"], phrase[lang], lang)
            assert result.verdict == "PASS", (phrase["id"], lang, [i.message for i in result.issues])


def test_dose_changed_tenfold_fails():
    result = check("Give the child 5 ml of syrup every 8 hours.", "Dele al niño 50 ml de jarabe cada 8 horas.", "es")
    assert result.verdict == "FAIL"
    assert "number_mismatch" in {i.check for i in result.issues}


def test_mg_swapped_for_ml_fails_and_highlights_unit():
    result = check("Take 2 tablets of 500 mg every 6 hours.", "Tome 2 comprimidos de 500 ml cada 6 horas.", "es")
    issue = next(i for i in result.issues if i.check == "unit_mismatch")
    assert issue.severity == "critical"
    assert issue.spans == ["ml"]


def test_dropped_negation_fails_in_each_language():
    source = "Do not take ibuprofen with your blood thinner."
    assert "negation_dropped" in _issues(source, "Tome ibuprofeno con su anticoagulante.", "es")
    assert "negation_dropped" in _issues(source, "Proszę przyjmować ibuprofen razem z lekiem przeciwzakrzepowym.", "pl")
    assert "negation_dropped" in _issues(source, "Tome ibuprofeno com o seu anticoagulante.", "pt")


def test_false_friend_constipado_fails():
    result = check("If you feel constipated, drink 2 litres of water a day.",
                   "Si está constipado, beba 2 litros de agua al día.", "es")
    issue = next(i for i in result.issues if i.check == "forbidden_term")
    assert result.verdict == "FAIL"
    assert issue.spans == ["constipado"]
    assert "cold" in issue.message


def test_untranslated_term_needs_review():
    result = check("Do not take ibuprofen with your blood thinner.", "No tome ibuprofeno con su blood thinner.", "es")
    assert result.verdict == "REVIEW"
    assert {"untranslated", "missing_term"} <= {i.check for i in result.issues}


def test_unsupported_language_is_rejected():
    with pytest.raises(ValueError):
        check("Take 2 tablets.", "Prenez 2 comprimés.", "fr")


def test_candidates_file_matches_generator(phrases):
    committed = json.loads((DATA / "candidates.json").read_text(encoding="utf-8"))
    assert committed == build_candidates(phrases)


def test_checker_meets_gates():
    report = run(json.loads((DATA / "candidates.json").read_text(encoding="utf-8")))
    assert report["checker"]["critical_recall"] == 1.0
    assert gate_failures(report["checker"]) == []
