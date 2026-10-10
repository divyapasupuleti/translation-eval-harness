"""Build docs/translation-eval-harness.docx and docs/architecture.png.

Run: pip install -r docs/requirements.txt && python docs/build_doc.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tqe.checks import check  # noqa: E402
from tqe.evaluate import GATES, load_candidates, run  # noqa: E402
from tqe.inject import SYSTEMS  # noqa: E402

DOCS = ROOT / "docs"
DIAGRAM = DOCS / "architecture.png"
PIPELINE_DIAGRAM = DOCS / "check-pipeline.png"
CICD_DIAGRAM = DOCS / "ci-cd.png"
OUTPUT = DOCS / "translation-eval-harness.docx"
PAGES_URL = "https://divyapasupuleti.github.io/translation-eval-harness/"
INK = "#1f2d3d"


def _canvas(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def _save(fig, path: Path) -> None:
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _box(ax, x, y, w, h, title, lines, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                linewidth=1.4, edgecolor=INK, facecolor=color))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top", fontsize=10.5, weight="bold")
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.68 - i * 0.3, line, ha="center", va="top", fontsize=8.3)


def _arrow(ax, x1, y1, x2, y2, label="", dx=0.0, dy=0.17):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                                 linewidth=1.3, color=INK))
    if label:
        ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, label, ha="center", fontsize=8.3, style="italic")


def draw_check_pipeline() -> None:
    fig, ax = _canvas(12, 6.2)
    _box(ax, 0.1, 4.3, 2.3, 1.6, "Input", ["English source", "translation", "language: es / pl / pt"], "#e8f1fb")
    _box(ax, 2.95, 4.3, 2.3, 1.6, "Tokenise", ["words and numbers", "number + unit pairs", "e.g. (500, mg)"], "#fdf2e3")

    checks = [
        ("Numbers", ["same numbers", "critical"]),
        ("Units", ["same unit per number", "critical"]),
        ("Negation", ["not / no / nie / não", "critical"]),
        ("Glossary", ["approved term, false friend", "critical or major"]),
        ("Untranslated", ["English words left", "major"]),
        ("Length", ["ratio per language", "minor"]),
    ]
    for i, (title, lines) in enumerate(checks):
        x = 0.1 + i * 1.98
        _box(ax, x, 2.15, 1.82, 1.4, title, lines, "#fdecea")
        _arrow(ax, 4.1, 4.25, x + 0.91, 3.6)

    _box(ax, 2.95, 0.15, 2.3, 1.4, "Issues", ["check, severity,", "message, words to highlight"], "#fdf2e3")
    _box(ax, 5.8, 0.15, 2.3, 1.4, "Score", ["100 - 25 x critical", "- 5 x major - 1 x minor"], "#fdf2e3")
    _box(ax, 8.65, 0.15, 3.2, 1.4, "Verdict", ["FAIL: any critical", "REVIEW: any other issue", "PASS: no issues"], "#eef7ee")

    _arrow(ax, 2.45, 5.1, 2.9, 5.1)
    for i in range(6):
        ax.plot([0.1 + i * 1.98 + 0.91, 4.1], [2.1, 1.6], color=INK, linewidth=1.0)
    _arrow(ax, 5.3, 0.85, 5.75, 0.85)
    _arrow(ax, 8.15, 0.85, 8.6, 0.85)
    ax.text(6.0, 4.0, "all six checks run on every translation", fontsize=8.3, style="italic")
    _save(fig, PIPELINE_DIAGRAM)


def draw_cicd() -> None:
    fig, ax = _canvas(12, 5.6)
    _box(ax, 0.1, 2.0, 2.0, 1.6, "git push", ["to main", "or pull request"], "#e8f1fb")

    ax.add_patch(FancyBboxPatch((2.6, 3.1), 9.3, 2.3, boxstyle="round,pad=0.05,rounding_size=0.2",
                                linewidth=1, linestyle="--", edgecolor="#6b7c93", facecolor="none"))
    ax.text(2.75, 5.2, "ci.yml (push and pull request)", fontsize=9, color="#6b7c93")
    _box(ax, 2.9, 3.3, 2.0, 1.5, "Install", ["Python 3.12", "pytest"], "#fdf2e3")
    _box(ax, 5.3, 3.3, 2.0, 1.5, "Unit tests", ["9 tests", "pytest -q"], "#fdecea")
    _box(ax, 7.7, 3.3, 2.0, 1.5, "Quality gate", ["critical recall 100%", "false alarms <= 5%"], "#fdecea")
    _box(ax, 10.0, 3.3, 1.7, 1.5, "Result", ["green tick", "or red cross"], "#eef7ee")

    ax.add_patch(FancyBboxPatch((2.6, 0.1), 9.3, 2.3, boxstyle="round,pad=0.05,rounding_size=0.2",
                                linewidth=1, linestyle="--", edgecolor="#6b7c93", facecolor="none"))
    ax.text(2.75, 2.2, "pages.yml (push to main)", fontsize=9, color="#6b7c93")
    _box(ax, 2.9, 0.3, 2.0, 1.5, "Evaluate", ["python -m", "tqe.evaluate"], "#fdf2e3")
    _box(ax, 5.3, 0.3, 2.0, 1.5, "Build page", ["python -m", "tqe.dashboard"], "#fdf2e3")
    _box(ax, 7.7, 0.3, 2.0, 1.5, "Upload", ["site/ folder", "Pages artifact"], "#fdf2e3")
    _box(ax, 10.0, 0.3, 1.7, 1.5, "Live", ["github.io", "dashboard"], "#f3eefb")

    _arrow(ax, 2.15, 3.1, 2.85, 4.0)
    _arrow(ax, 2.15, 2.5, 2.85, 1.1)
    for x in (4.95, 7.35, 9.75):
        _arrow(ax, x, 4.05, x + 0.3, 4.05)
        _arrow(ax, x, 1.05, x + 0.3, 1.05)
    _save(fig, CICD_DIAGRAM)


def draw_architecture() -> None:
    fig, ax = _canvas(12, 5.4)

    def box(*args):
        _box(ax, *args)

    def arrow(*args, **kwargs):
        _arrow(ax, *args, **kwargs)

    box(0.1, 3.2, 2.1, 1.7, "Source phrases", ["12 English instructions", "+ reference es / pl / pt", "data/phrases.json"], "#e8f1fb")
    box(2.75, 3.2, 2.3, 1.7, "Error injector", ["3 simulated systems", "plant 7 error types", "tqe/inject.py"], "#fdf2e3")
    box(5.6, 3.2, 2.3, 1.7, "Quality checks", ["numbers, units, negation", "glossary, untranslated, length", "tqe/checks.py"], "#fdecea")
    box(8.45, 3.2, 3.4, 1.7, "Evaluation", ["system scores and verdicts", "checker recall vs planted errors", "tqe/evaluate.py"], "#fdf2e3")

    box(0.1, 0.5, 2.1, 1.6, "Glossary", ["approved terms", "false friends", "data/glossary.json"], "#eef7ee")
    box(5.6, 0.5, 2.3, 1.6, "CLI", ["python -m tqe", "check one translation"], "#f3eefb")
    box(8.45, 0.5, 1.6, 1.6, "CI gate", ["critical recall 100%", "false alarms <= 5%"], "#eef7ee")
    box(10.25, 0.5, 1.6, 1.6, "Dashboard", ["site/index.html", "GitHub Pages"], "#f3eefb")

    arrow(2.25, 4.05, 2.7, 4.05, "references", dy=0.2)
    arrow(5.1, 4.05, 5.55, 4.05, "144", dy=0.2)
    arrow(7.95, 4.05, 8.4, 4.05, "issues", dy=0.2)
    arrow(2.25, 1.6, 5.55, 3.35)
    ax.text(3.0, 1.55, "glossary terms", fontsize=8.3, style="italic")
    arrow(6.75, 2.15, 6.75, 3.15)
    arrow(9.25, 3.15, 9.25, 2.15)
    arrow(11.05, 3.15, 11.05, 2.15)
    ax.plot([3.9, 3.9, 8.85], [3.15, 2.7, 2.7], color="#1f2d3d", linewidth=1.3)
    arrow(8.85, 2.7, 8.85, 3.15)
    ax.text(7.85, 2.45, "planted error (answer key)", ha="center", fontsize=8.3, style="italic")
    _save(fig, DIAGRAM)


def code(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Inches(0.25)
    run_ = para.add_run(text)
    run_.font.name = "Menlo"
    run_.font.size = Pt(8.5)
    run_.font.color.rgb = RGBColor(0x1F, 0x2D, 0x3D)


def table(doc: Document, header: list[str], rows: list[list[str]], font_size: float | None = None) -> None:
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, text in zip(t.rows[0].cells, header):
        cell.text = text
    for row in rows:
        for cell, text in zip(t.add_row().cells, row):
            cell.text = text
    if font_size:
        for row in t.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for r in para.runs:
                        r.font.size = Pt(font_size)
    doc.add_paragraph()


def build() -> None:
    draw_architecture()
    draw_check_pipeline()
    draw_cicd()
    report = run(load_candidates())
    systems, checker = report["systems"], report["checker"]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("translation-eval-harness", 0)
    doc.add_paragraph(
        "Automatic quality checks for clinical translations from English into Spanish, Polish and Portuguese, "
        "with a dashboard that compares translation systems side by side and highlights each mistake. "
        "All phrases and systems are synthetic."
    )
    doc.add_paragraph(f"Live dashboard: {PAGES_URL}")

    doc.add_heading("1. Problem", 1)
    doc.add_paragraph(
        "Machine translation is fluent enough that its mistakes are easy to miss, and in a clinic some mistakes "
        "hurt people. \"Do not take ibuprofen\" losing its \"not\", 5 ml becoming 50 ml, or Spanish \"constipado\" "
        "(which means having a cold) used for \"constipated\" all read naturally to a non-speaker. A hospital needs "
        "to catch these before a translated instruction reaches a patient, without a human reference translation "
        "for every sentence."
    )

    doc.add_heading("2. Architecture", 1)
    doc.add_paragraph(
        "The project has three layers: offline data generation (phrases, glossary and simulated systems), a "
        "reference-free checking engine, and reporting (evaluation, dashboard and CI). Everything runs on the "
        "Python standard library, so it needs no API keys, databases or servers."
    )

    doc.add_heading("2.1 System overview", 2)
    doc.add_picture(str(DIAGRAM), width=Inches(6.5))
    doc.add_paragraph(
        "Twelve English instructions have a correct reference translation in each language. The injector "
        "simulates three translation systems by planting specific errors into those references, and records "
        "which error it planted. The checks then score all 144 translations using only the English source, the "
        "translation and the glossary, never the reference. Because the planted error is known, the evaluation "
        "can measure how many errors of each type the checks catch, and how often they flag a correct translation."
    )
    table(doc, ["Component", "File", "Responsibility"], [
        ["Phrases", "data/phrases.json", "12 English instructions with reference translations"],
        ["Glossary", "data/glossary.json", "Approved clinical terms per language and known false friends"],
        ["Injector", "tqe/inject.py", "Simulates 3 systems, writes data/candidates.json with the planted error"],
        ["Checks", "tqe/checks.py", "Reference-free checks, MQM-style score and PASS / REVIEW / FAIL verdict"],
        ["Evaluation", "tqe/evaluate.py", "System comparison, checker recall and false alarms, CI gate"],
        ["Dashboard", "tqe/dashboard.py", "Self-contained HTML: charts, filters, side-by-side highlighted view"],
        ["CLI", "tqe/__main__.py", "Check one translation; exits 1 on FAIL"],
        ["CI", ".github/workflows/", "Tests and quality gate; builds and publishes the dashboard"],
    ])

    doc.add_heading("2.2 How one translation is checked", 2)
    doc.add_picture(str(PIPELINE_DIAGRAM), width=Inches(6.5))
    doc.add_paragraph(
        "check(source, target, lang) splits both sentences into words and numbers, and pairs each number with the "
        "unit word after it. All six checks run independently and each returns zero or more issues with a "
        "severity and the exact words to highlight. The issues are combined into one score and a verdict. The same "
        "function is used by the CLI, the evaluation and the dashboard, so all three always agree."
    )

    doc.add_heading("2.3 Build and deployment", 2)
    doc.add_picture(str(CICD_DIAGRAM), width=Inches(6.5))
    doc.add_paragraph(
        "Two GitHub Actions workflows run on every push. ci.yml runs the unit tests and the quality gate, and "
        "fails the build if any critical error is missed or false alarms exceed 5%; it also runs on pull "
        "requests, so a change that weakens the checks cannot be merged unnoticed. pages.yml re-runs the "
        "evaluation, rebuilds the dashboard and publishes it to GitHub Pages, so the live page always reflects "
        "the code on main."
    )

    doc.add_heading("2.4 Folder layout", 2)
    code(doc,
         "translation-eval-harness/\n"
         "├── data/\n"
         "│   ├── phrases.json         12 English instructions + reference es / pl / pt\n"
         "│   ├── glossary.json        approved terms and false friends per language\n"
         "│   └── candidates.json      144 generated translations with the planted error\n"
         "├── tqe/\n"
         "│   ├── checks.py            the six checks, score and verdict\n"
         "│   ├── inject.py            simulated systems and error injectors\n"
         "│   ├── evaluate.py          system comparison, checker recall, CI gate\n"
         "│   ├── dashboard.py         builds site/index.html\n"
         "│   └── __main__.py          python -m tqe (check one translation)\n"
         "├── reports/results.json     every check result and all metrics\n"
         "├── site/index.html          the dashboard (one self-contained file)\n"
         "├── tests/test_checks.py     unit tests\n"
         "├── docs/                    this document, diagrams, screenshots\n"
         "└── .github/workflows/       ci.yml, pages.yml")

    doc.add_heading("2.5 Data format", 2)
    doc.add_paragraph("Each generated translation in data/candidates.json:")
    example = next(c for c in load_candidates() if c["planted_error"] == "swap_unit")
    code(doc, json.dumps(example, indent=2, ensure_ascii=False))
    doc.add_paragraph(
        "planted_error is the answer key. It is null for correct translations and is never shown to the checks; "
        "only the evaluation reads it, to work out whether each mistake was caught."
    )

    doc.add_heading("2.6 Design decisions", 2)
    table(doc, ["Decision", "Why"], [
        ["Reference-free checks", "In production there is no correct translation to compare against, so the "
                                  "checks use only the source, the translation and the glossary"],
        ["Rules, not a model", "Every flag is explainable and repeatable, runs offline, and costs nothing; "
                               "a model-based judge can be added later for meaning-level errors"],
        ["Planted errors", "Gives a known answer for every translation, so the checker itself can be measured"],
        ["Severity levels", "Critical issues block the translation; minor ones only ask for a human look, "
                            "which keeps reviewers focused on what matters"],
        ["Single-file dashboard", "No server or JavaScript libraries; it opens offline and hosts free on GitHub Pages"],
    ])

    doc.add_heading("Checks", 2)
    table(doc, ["Check", "Severity", "Catches"], [
        ["number_mismatch", "critical", "A number missing, added or changed, e.g. 5 ml to 50 ml"],
        ["unit_mismatch", "critical", "Same number, different unit, e.g. 500 mg to 500 ml or 6 hours to 6 days"],
        ["negation_dropped", "critical", "English says do not / never, translation has no negation word"],
        ["forbidden_term", "critical", "A known false friend, e.g. constipado, injuria"],
        ["missing_term", "major", "A glossary term in the source has no approved translation in the target"],
        ["untranslated", "major", "English words of 4+ letters copied into the translation"],
        ["length_ratio", "minor", "Translation much shorter or longer than usual for that language"],
    ])
    doc.add_paragraph("Score = 100 minus 25 per critical, 5 per major and 1 per minor issue. "
                      "Verdict: FAIL with any critical issue, REVIEW with any other issue, otherwise PASS.")

    doc.add_heading("Simulated systems", 2)
    table(doc, ["System", "Behaviour", "Planted error types"], [
        [name, p.get("description", "Correct reference translation"), ", ".join(p["errors"]) or "none"]
        for name, p in SYSTEMS.items()
    ])

    doc.add_heading("3. Commands to run", 1)
    code(doc, "git clone https://github.com/divyapasupuleti/translation-eval-harness.git\n"
              "cd translation-eval-harness\n"
              "python3 -m venv .venv\n"
              ".venv/bin/pip install -r requirements.txt\n"
              ".venv/bin/python -m pytest -v            # unit tests\n"
              ".venv/bin/python -m tqe.inject           # regenerate the 144 candidates\n"
              ".venv/bin/python -m tqe.evaluate         # score systems and the checks; exits 1 below the gate\n"
              ".venv/bin/python -m tqe.dashboard        # write site/index.html\n"
              "open site/index.html")
    doc.add_paragraph("The checks use only the Python standard library; pytest is needed only for the tests.")
    doc.add_paragraph("Dashboard filters can be set from the address, for example "
                      "site/index.html?verdict=FAIL&diff=1 opens only failures with changes shown.")

    doc.add_heading("4. Input and output", 1)
    doc.add_heading("Check one translation", 2)
    src = "If you feel constipated, drink 2 litres of water a day."
    tgt = "Si está constipado, beba 20 litros de agua al día."
    code(doc, f'python -m tqe --lang es \\\n  --source "{src}" \\\n  --target "{tgt}"')
    code(doc, json.dumps(check(src, tgt, "es").to_dict(), indent=2, ensure_ascii=False))
    doc.add_paragraph("Two critical issues: the amount changed from 2 to 20 litres, and \"constipado\" means "
                      "having a cold. Score 50, FAIL, exit code 1.")

    doc.add_heading("Dashboard", 2)
    doc.add_picture(str(DOCS / "dashboard.png"), width=Inches(6.5))
    doc.add_paragraph("Top: average score and verdict mix per system, score by language, and how well the checks "
                      "caught each planted error type. Bottom: each instruction with all four translations side "
                      "by side; flagged words are highlighted by severity.")
    doc.add_picture(str(DOCS / "dashboard-failures.png"), width=Inches(6.5))
    doc.add_paragraph("Filtered to FAIL with \"Show changes vs reference\" on: the wrong unit \"ml\" is highlighted "
                      "and the original \"mg\" is struck through.")

    doc.add_heading("5. Final validation", 1)
    doc.add_heading("System comparison", 2)
    code(doc, "python -m tqe.evaluate")
    table(doc, ["System", "Avg score", "Pass", "Review", "Fail"], [
        [name, str(systems[name]["avg_score"]), str(systems[name]["pass"]), str(systems[name]["review"]),
         str(systems[name]["fail"])] for name in SYSTEMS
    ])

    doc.add_heading("How good are the checks", 2)
    table(doc, ["Measure", "Result", "Gate"], [
        ["Critical errors caught", f"{100 * checker['critical_recall']:.0f}%", f">= {100 * GATES['critical_recall_min']:.0f}%"],
        ["All planted errors caught", f"{100 * checker['overall_recall']:.0f}% of {checker['planted_errors']}", "reported"],
        ["False alarms on correct translations", f"{100 * checker['false_alarm_rate']:.0f}% of {checker['clean_segments']}",
         f"<= {100 * GATES['false_alarm_rate_max']:.0f}%"],
    ])
    table(doc, ["Planted error", "Caught"], [
        [error, f"{s['caught']}/{s['planted']}"] for error, s in checker["per_error"].items()
    ])

    missed = [r for r in report["rows"] if r["planted_error"] and not r["caught"]]
    if missed:
        doc.add_heading("Known miss", 2)
        for r in missed:
            doc.add_paragraph(f"{r['id']} ({r['planted_error']})")
            code(doc, f"Source:      {r['source']}\nReference:   {r['reference']}\nTranslation: {r['target']}")
        doc.add_paragraph(
            "\"Before breakfast\" was dropped, but the sentence kept all its numbers and a normal length, so no "
            "reference-free check can tell. Catching this needs a meaning comparison, for example back-translation "
            "or a model-based judge, which is the next step for this project."
        )

    doc.add_heading("Unit tests", 2)
    code(doc, "python -m pytest -v")
    table(doc, ["Test", "What it proves"], [
        ["test_every_reference_translation_passes", "All 36 correct translations pass with no issues"],
        ["test_dose_changed_tenfold_fails", "5 ml becoming 50 ml is a critical failure"],
        ["test_mg_swapped_for_ml_fails_and_highlights_unit", "mg to ml is critical and the unit word is highlighted"],
        ["test_dropped_negation_fails_in_each_language", "A missing 'do not' fails in Spanish, Polish and Portuguese"],
        ["test_false_friend_constipado_fails", "'constipado' fails and the message explains it means a cold"],
        ["test_untranslated_term_needs_review", "'blood thinner' left in English needs review"],
        ["test_unsupported_language_is_rejected", "Unsupported languages raise an error instead of passing"],
        ["test_candidates_file_matches_generator", "The committed candidates are exactly what the generator produces"],
        ["test_checker_meets_gates", "100% critical recall and the false alarm gate"],
    ])
    code(doc, "============================== 9 passed ==============================")

    doc.add_heading("6. Limits", 1)
    doc.add_paragraph(
        "The errors are planted by rules, so the recall figures show the checks work on these error types, not "
        "how often real machine translation makes them. The glossary covers 7 terms and 4 false friends; a real "
        "deployment needs a clinical glossary maintained by interpreters. Omissions without a number, negation or "
        "glossary term can pass unnoticed, as in the known miss above."
    )

    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
    print(f"Wrote {OUTPUT} and {DIAGRAM}")
