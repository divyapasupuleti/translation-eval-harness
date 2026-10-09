"""Build a self-contained HTML dashboard from reports/results.json.

Run: python -m tqe.dashboard   (writes site/index.html)
"""

from __future__ import annotations

import difflib
import html
import json
import re
from pathlib import Path

from tqe.checks import LANGUAGES
from tqe.evaluate import CRITICAL_ERRORS, RESULTS
from tqe.inject import SYSTEMS

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "index.html"

LANG_NAMES = {"es": "Spanish", "pl": "Polish", "pt": "Portuguese"}
ERROR_NAMES = {
    "drop_negation": "Dropped negation",
    "change_number": "Wrong number",
    "swap_unit": "Wrong unit",
    "false_friend": "False friend",
    "untranslated": "Left in English",
    "omission": "Omitted content",
    "addition": "Added content",
}
CHECK_NAMES = {
    "negation_dropped": "Negation missing",
    "number_mismatch": "Number mismatch",
    "unit_mismatch": "Unit mismatch",
    "forbidden_term": "False friend",
    "missing_term": "Glossary term missing",
    "untranslated": "Untranslated words",
    "length_ratio": "Unusual length",
}
_SEVERITY_RANK = {"critical": 3, "major": 2, "minor": 1}


def _norm(word: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", word.lower())


def render_target(row: dict) -> str:
    spans: dict[str, str] = {}
    for issue in row["issues"]:
        for span in issue["spans"]:
            for part in span.lower().split():
                if _SEVERITY_RANK[issue["severity"]] > _SEVERITY_RANK.get(spans.get(part, ""), 0):
                    spans[part] = issue["severity"]

    def word(token: str, tag: str | None) -> str:
        text = html.escape(token)
        severity = spans.get(_norm(token))
        if severity and tag != "del":
            text = f'<mark class="{severity}">{text}</mark>'
        return f"<{tag}>{text}</{tag}>" if tag else text

    ref, tgt = row["reference"].split(), row["target"].split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ref, b=tgt, autojunk=False).get_opcodes():
        if op == "equal":
            out += [word(t, None) for t in tgt[j1:j2]]
        if op in ("delete", "replace"):
            out += [word(t, "del") for t in ref[i1:i2]]
        if op in ("insert", "replace"):
            out += [word(t, "ins") for t in tgt[j1:j2]]
    return " ".join(out)


def _bar_chart(systems: dict) -> str:
    names = [s for s in SYSTEMS]
    width, height, pad_left, pad_bottom = 640, 260, 40, 40
    group = (width - pad_left) / len(names)
    bar = group / (len(LANGUAGES) + 1.5)
    y = lambda v: 10 + (height - pad_bottom - 10) * (1 - (v - 50) / 50)  # noqa: E731
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Average score by system and language">']
    for v in (50, 75, 100):
        parts.append(f'<line x1="{pad_left}" x2="{width}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                     f'<text x="{pad_left - 6}" y="{y(v) + 4:.1f}" class="axis" text-anchor="end">{v}</text>')
    for gi, name in enumerate(names):
        x0 = pad_left + gi * group + bar * 0.75
        for li, lang in enumerate(LANGUAGES):
            v = systems[f"{name}|{lang}"]["avg_score"]
            x = x0 + li * bar
            parts.append(f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{bar - 4:.1f}" '
                         f'height="{height - pad_bottom - y(v):.1f}" class="bar {lang}"><title>{name}, '
                         f'{LANG_NAMES[lang]}: {v}</title></rect>'
                         f'<text x="{x + (bar - 4) / 2:.1f}" y="{y(v) - 4:.1f}" class="val" '
                         f'text-anchor="middle">{v:.0f}</text>')
        parts.append(f'<text x="{x0 + bar * 1.5:.1f}" y="{height - 16}" class="label" '
                     f'text-anchor="middle">{name}</text>')
    parts.append("</svg>")
    return "".join(parts)


def build_rows(report: dict) -> list[dict]:
    rows = []
    for r in report["rows"]:
        rows.append({
            "id": r["id"],
            "phrase": r["phrase_id"],
            "lang": r["lang"],
            "system": r["system"],
            "source": r["source"],
            "html": render_target(r),
            "score": r["score"],
            "verdict": r["verdict"],
            "planted": r["planted_error"],
            "planted_name": ERROR_NAMES.get(r["planted_error"], ""),
            "caught": r["caught"],
            "issues": [{"name": CHECK_NAMES[i["check"]], "severity": i["severity"], "message": i["message"]}
                       for i in r["issues"]],
        })
    return rows


def build(report: dict) -> str:
    systems, checker = report["systems"], report["checker"]
    cards = []
    for name, profile in SYSTEMS.items():
        s = systems[name]
        total = s["segments"]
        cards.append(f"""
        <div class="card">
          <div class="card-head"><h3>{html.escape(name)}</h3><span class="score">{s['avg_score']}</span></div>
          <p class="muted">{html.escape(profile.get('description', 'Human reference translation'))}</p>
          <div class="stack" title="{s['pass']} pass, {s['review']} review, {s['fail']} fail">
            <span class="pass" style="width:{100 * s['pass'] / total:.1f}%"></span>
            <span class="review" style="width:{100 * s['review'] / total:.1f}%"></span>
            <span class="fail" style="width:{100 * s['fail'] / total:.1f}%"></span>
          </div>
          <p class="legend"><b class="t-pass">{s['pass']}</b> pass · <b class="t-review">{s['review']}</b> review ·
             <b class="t-fail">{s['fail']}</b> fail</p>
        </div>""")

    recall_rows = []
    for error, stats in checker["per_error"].items():
        pct = 100 * stats["recall"]
        tag = '<span class="pill critical">critical</span>' if error in CRITICAL_ERRORS else ""
        recall_rows.append(f"""
        <tr><td>{ERROR_NAMES[error]} {tag}</td><td class="num">{stats['caught']}/{stats['planted']}</td>
            <td><div class="meter"><span style="width:{pct:.0f}%" class="{'ok' if pct == 100 else 'warn'}"></span></div></td>
        </tr>""")

    data = json.dumps(build_rows(report), ensure_ascii=False).replace("</", "<\\/")
    error_options = "".join(f'<option value="{k}">{v}</option>' for k, v in ERROR_NAMES.items())
    lang_options = "".join(f'<option value="{k}">{v}</option>' for k, v in LANG_NAMES.items())

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clinical translation quality dashboard</title>
<style>
:root {{
  --bg:#f6f7f9; --card:#fff; --ink:#1f2933; --muted:#6b7785; --line:#e3e7ec;
  --pass:#2f9e6b; --review:#e0a526; --fail:#d64545; --minor:#3b82c4;
  --es:#5b8def; --pl:#e8735a; --pt:#3fb28c;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--ink); }}
header {{ background:#14202e; color:#fff; padding:28px 32px 24px; }}
header h1 {{ margin:0 0 6px; font-size:24px; }}
header p {{ margin:0; color:#b8c4d1; max-width:880px; }}
main {{ padding:24px 32px 48px; max-width:1320px; margin:0 auto; }}
h2 {{ font-size:18px; margin:32px 0 12px; }}
.muted {{ color:var(--muted); font-size:13px; margin:4px 0 12px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; }}
.card-head {{ display:flex; justify-content:space-between; align-items:baseline; }}
.card h3 {{ margin:0; font-size:16px; }}
.score {{ font-size:26px; font-weight:700; }}
.stack {{ display:flex; height:10px; border-radius:5px; overflow:hidden; background:var(--line); }}
.stack .pass {{ background:var(--pass); }} .stack .review {{ background:var(--review); }} .stack .fail {{ background:var(--fail); }}
.legend {{ font-size:13px; margin:8px 0 0; color:var(--muted); }}
.t-pass {{ color:var(--pass); }} .t-review {{ color:#b07f0c; }} .t-fail {{ color:var(--fail); }}
.split {{ display:grid; grid-template-columns:1.3fr 1fr; gap:14px; }}
@media (max-width:900px) {{ .split {{ grid-template-columns:1fr; }} }}
svg {{ width:100%; height:auto; }}
svg .grid {{ stroke:var(--line); }} svg .axis, svg .val {{ font-size:11px; fill:var(--muted); }}
svg .label {{ font-size:12px; fill:var(--ink); font-weight:600; }}
svg .bar.es {{ fill:var(--es); }} svg .bar.pl {{ fill:var(--pl); }} svg .bar.pt {{ fill:var(--pt); }}
.key span {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin:0 4px 0 12px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
td {{ padding:7px 4px; border-bottom:1px solid var(--line); }}
td.num {{ text-align:right; width:60px; font-variant-numeric:tabular-nums; }}
.meter {{ height:8px; background:var(--line); border-radius:4px; overflow:hidden; }}
.meter span {{ display:block; height:100%; }} .meter .ok {{ background:var(--pass); }} .meter .warn {{ background:var(--review); }}
.kpis {{ display:flex; gap:22px; margin:6px 0 12px; }}
.kpi b {{ display:block; font-size:22px; }} .kpi span {{ font-size:12px; color:var(--muted); }}
.pill {{ font-size:11px; padding:1px 7px; border-radius:10px; font-weight:600; vertical-align:middle; }}
.pill.critical {{ background:#fde8e8; color:var(--fail); }} .pill.major {{ background:#fdf3dc; color:#a6740a; }}
.pill.minor {{ background:#e3effa; color:var(--minor); }}
.filters {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; background:var(--card); border:1px solid var(--line);
           border-radius:10px; padding:12px 14px; position:sticky; top:0; z-index:5; }}
.filters select, .filters input {{ font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:#fff; }}
.filters input[type=search] {{ flex:1; min-width:180px; }}
.filters label {{ font-size:13px; color:var(--muted); display:flex; gap:6px; align-items:center; }}
#count {{ font-size:13px; color:var(--muted); margin-left:auto; }}
.phrase {{ background:var(--card); border:1px solid var(--line); border-radius:10px; margin-top:14px; overflow:hidden; }}
.phrase-head {{ padding:12px 16px; border-bottom:1px solid var(--line); display:flex; gap:12px; align-items:baseline; }}
.phrase-head .lang {{ font-size:12px; font-weight:700; color:#fff; padding:2px 8px; border-radius:4px; }}
.lang.es {{ background:var(--es); }} .lang.pl {{ background:var(--pl); }} .lang.pt {{ background:var(--pt); }}
.phrase-head .src {{ font-weight:600; }}
.grid4 {{ display:grid; grid-template-columns:repeat(4,1fr); }}
@media (max-width:1000px) {{ .grid4 {{ grid-template-columns:repeat(2,1fr); }} }}
.cell {{ padding:12px 14px; border-right:1px solid var(--line); border-top:3px solid transparent; }}
.cell:last-child {{ border-right:none; }}
.cell.PASS {{ border-top-color:var(--pass); }} .cell.REVIEW {{ border-top-color:var(--review); }} .cell.FAIL {{ border-top-color:var(--fail); background:#fffafa; }}
.cell.dim {{ opacity:.28; }}
.cell-head {{ display:flex; justify-content:space-between; font-size:12px; color:var(--muted); margin-bottom:6px; }}
.verdict {{ font-weight:700; }} .verdict.PASS {{ color:var(--pass); }} .verdict.REVIEW {{ color:#b07f0c; }} .verdict.FAIL {{ color:var(--fail); }}
.text {{ font-size:15px; }}
mark {{ border-radius:3px; padding:0 2px; }}
mark.critical {{ background:#fbd5d5; color:#8a1c1c; }} mark.major {{ background:#fbe9bf; }} mark.minor {{ background:#d8e8f7; }}
ins {{ text-decoration:none; }} del {{ display:none; }}
body.diff ins {{ background:#d9f2e4; text-decoration:underline; text-decoration-color:var(--pass); }}
body.diff del {{ display:inline; color:#9aa5b1; }}
.issues {{ list-style:none; padding:0; margin:8px 0 0; font-size:12.5px; }}
.issues li {{ margin:4px 0; }}
.planted {{ margin-top:8px; font-size:12px; color:var(--muted); border-top:1px dashed var(--line); padding-top:6px; }}
.planted .yes {{ color:var(--pass); font-weight:700; }} .planted .no {{ color:var(--fail); font-weight:700; }}
footer {{ color:var(--muted); font-size:13px; margin-top:32px; }}
</style>
</head>
<body>
<header>
  <h1>Clinical translation quality dashboard</h1>
  <p>12 discharge and medication instructions translated from English into Spanish, Polish and Portuguese by three
  simulated machine translation systems, checked automatically for the mistakes that hurt patients: dropped
  negations, wrong doses and units, false friends, and untranslated or missing content.</p>
</header>
<main>
  <h2>Systems</h2>
  <p class="muted">Average quality score (100 = no issues; each critical issue costs 25, major 5, minor 1).
  FAIL means at least one critical issue.</p>
  <div class="cards">{''.join(cards)}</div>

  <div class="split">
    <div>
      <h2>Score by language</h2>
      <div class="card">
        <div class="key muted"><span style="background:var(--es)"></span>Spanish<span style="background:var(--pl)"></span>Polish<span style="background:var(--pt)"></span>Portuguese</div>
        {_bar_chart(systems)}
      </div>
    </div>
    <div>
      <h2>How good are the checks?</h2>
      <div class="card">
        <p class="muted">Errors were planted on purpose, so every check can be scored against a known answer.</p>
        <div class="kpis">
          <div class="kpi"><b>{100 * checker['critical_recall']:.0f}%</b><span>critical errors caught</span></div>
          <div class="kpi"><b>{100 * checker['overall_recall']:.0f}%</b><span>all errors caught</span></div>
          <div class="kpi"><b>{100 * checker['false_alarm_rate']:.0f}%</b><span>false alarms on {checker['clean_segments']} clean</span></div>
        </div>
        <table>{''.join(recall_rows)}</table>
      </div>
    </div>
  </div>

  <h2>Side by side</h2>
  <div class="filters">
    <select id="lang"><option value="">All languages</option>{lang_options}</select>
    <select id="verdict"><option value="">Any verdict</option><option>FAIL</option><option>REVIEW</option><option>PASS</option></select>
    <select id="error"><option value="">Any planted error</option>{error_options}<option value="none">No planted error</option></select>
    <input id="q" type="search" placeholder="Search source or translation...">
    <label><input id="diff" type="checkbox"> Show changes vs reference</label>
    <span id="count"></span>
  </div>
  <div id="phrases"></div>

  <footer>All phrases and systems are synthetic. Built by <code>python -m tqe.dashboard</code> from
  <code>reports/results.json</code>.</footer>
</main>
<script id="data" type="application/json">{data}</script>
<script>
const rows = JSON.parse(document.getElementById('data').textContent);
const systems = {json.dumps(list(SYSTEMS))};
const langNames = {json.dumps(LANG_NAMES)};
const $ = id => document.getElementById(id);
const esc = s => s.replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const strip = s => s.replace(/<[^>]+>/g, '');

const groups = {{}};
for (const r of rows) (groups[r.phrase + '|' + r.lang] ||= []).push(r);

function matches(r, f) {{
  if (f.verdict && r.verdict !== f.verdict) return false;
  if (f.error === 'none' && r.planted) return false;
  if (f.error && f.error !== 'none' && r.planted !== f.error) return false;
  if (f.q && !(r.source + ' ' + strip(r.html)).toLowerCase().includes(f.q)) return false;
  return true;
}}

function cell(r, on) {{
  const issues = r.issues.map(i => `<li><span class="pill ${{i.severity}}">${{i.severity}}</span> <b>${{esc(i.name)}}</b>: ${{esc(i.message)}}</li>`).join('');
  const planted = r.planted
    ? `<div class="planted">Planted: ${{esc(r.planted_name)}} · ${{r.caught ? '<span class="yes">caught</span>' : '<span class="no">missed</span>'}}</div>`
    : '';
  return `<div class="cell ${{r.verdict}} ${{on ? '' : 'dim'}}">
    <div class="cell-head"><span>${{esc(r.system)}}</span><span><span class="verdict ${{r.verdict}}">${{r.verdict}}</span> · ${{r.score}}</span></div>
    <div class="text">${{r.html}}</div>
    ${{issues ? `<ul class="issues">${{issues}}</ul>` : ''}}${{planted}}
  </div>`;
}}

function render() {{
  const f = {{ lang: $('lang').value, verdict: $('verdict').value, error: $('error').value, q: $('q').value.trim().toLowerCase() }};
  document.body.classList.toggle('diff', $('diff').checked);
  const out = [];
  let shown = 0;
  for (const [key, list] of Object.entries(groups)) {{
    const [, lang] = key.split('|');
    if (f.lang && lang !== f.lang) continue;
    const hits = list.filter(r => matches(r, f));
    if (!hits.length) continue;
    shown += hits.length;
    const ordered = systems.map(s => list.find(r => r.system === s));
    out.push(`<section class="phrase">
      <div class="phrase-head"><span class="lang ${{lang}}">${{langNames[lang]}}</span><span class="src">${{esc(list[0].source)}}</span></div>
      <div class="grid4">${{ordered.map(r => cell(r, hits.includes(r))).join('')}}</div>
    </section>`);
  }}
  $('phrases').innerHTML = out.join('') || '<p class="muted">No translations match these filters.</p>';
  $('count').textContent = `${{shown}} of ${{rows.length}} translations`;
}}

const params = new URLSearchParams(location.search);
for (const id of ['lang', 'verdict', 'error', 'q']) if (params.has(id)) $(id).value = params.get(id);
$('diff').checked = params.get('diff') === '1';
for (const id of ['lang', 'verdict', 'error', 'q', 'diff']) $(id).addEventListener('input', render);
render();
</script>
</body>
</html>
"""


def main() -> None:
    report = json.loads(RESULTS.read_text(encoding="utf-8"))
    SITE.parent.mkdir(exist_ok=True)
    SITE.write_text(build(report), encoding="utf-8")
    print(f"Wrote {SITE}")


if __name__ == "__main__":
    main()
