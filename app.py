"""
app.py -- a browser view of the CFDE AI-Readiness Checker results.

Run locally:
    pip3 install -r requirements.txt
    streamlit run app.py

It reads only committed files (output/readiness_comparison.json and
output/readiness_projects.json), so it runs from a fresh clone without
data_real/. The upload page runs src/readiness_checker.py live on a user's
own small datapackage.

Pages:
  Overview           -- how AI-ready is CFDE metadata, at a glance? (a reviewer)
  Field coverage     -- which key fields are filled, where? (everyone)
  Find ML-ready data -- which programs have records with everything my model needs? (a researcher)
  Program report card -- what would raise this program's readiness most? (a program's data team)
  Dataset basket     -- which of the projects I want meet my needs? export the selection (a researcher)
"""

import hashlib
import json
import math
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
import readiness_checker as rc  # noqa: E402  (needs src/ on the path first)

REPO_URL = "https://github.com/OmKadam16/cfde-ai-readiness-prototype"
C2M2_ASSESSMENT_URL = "https://github.com/nih-cfde/c2m2-assessment"
PAPER_URL = "https://doi.org/10.1101/2024.10.23.619844"
COMPARISON_JSON = ROOT / "output" / "readiness_comparison.json"
PROJECTS_JSON = ROOT / "output" / "readiness_projects.json"

# Upload limits: the zip size is also enforced by .streamlit/config.toml.
# The unzipped cap keeps memory use within a free Streamlit Cloud instance.
MAX_UPLOAD_MB = 50
MAX_UNZIPPED_MB = 300

DIMENSION_NAMES = [name for name, _ in rc.DIMENSIONS]
SCORED_DIMENSIONS = [d for d in DIMENSION_NAMES if d != "Ethics"]  # Ethics: not measurable from C2M2
SHORT_DIMENSION = {"Pre-model Explainability": "Explainability"}
# Readable program names (e.g. "Kids First" rather than the package's "KFDRC"),
# taken from releases.tsv and matched on the release file each result came from.
RELEASES = pd.read_csv(ROOT / "releases.tsv", sep="\t", dtype=str)
DISPLAY_NAME = dict(zip(RELEASES["release_file"], RELEASES["program"]))

# ---------------------------------------------------------------------------
# Colour: one sequential blue scale for scores, gray for n/a. No red/green.
# (Blue steps from the dataviz reference palette's sequential ramp.)
# ---------------------------------------------------------------------------
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
HIGHLIGHT = "#2a78d6"
NA_FILL = "#c8c7c2"
INK_ON_LIGHT, INK_ON_DARK = "#0b0b0b", "#ffffff"
DARK_TEXT_FROM = 55  # cells scoring >= this are dark enough for white text
# Mid-gray neutrals that read on both light and dark backgrounds. Chart text
# has no colour set, so it takes Streamlit's theme text colour in either mode.
GRID = "#8f8e88"
CONTEXT_LINE = "#8f8e88"
TRACK = "rgba(143, 142, 136, 0.28)"
# Chart text (labels drawn inside charts). Streamlit themes axes but not text
# marks, and the page theme can't be detected reliably, so this gray is chosen
# to read on both backgrounds: 4.3:1 on white and on Streamlit's dark #0e1117.
CHART_TEXT = "#797979"

# Plain-English names for each check: (label, unit, fix wording). Column names
# stay in small print (C2M2 source) or on hover.
CHECK_INFO = {
    "persistent_ids": ("Persistent identifiers", "records", "Add persistent identifiers to {n} records"),
    "ontology_ids": ("Ontology term IDs", "values", "Replace {n} free-text values with ontology term IDs"),
    "creation_time": ("Creation time", "records", "Add creation times to {n} records"),
    "file_checksums": ("File checksums", "files", "Add checksums to {n} files"),
    "subject_sex": ("Sex", "single-organism subjects", "Record sex for {n} single-organism subjects"),
    "subject_age": ("Age", "single-organism subjects", "Record age for {n} single-organism subjects"),
    "biosample_anatomy": ("Anatomy", "biosamples", "Record anatomy for {n} biosamples"),
    "labeled_terms": ("Labelled term IDs", "term IDs", "Add labels for {n} term IDs to the term tables"),
    "file_locatable": ("File location (persistent ID or URL)", "files",
                       "Add a persistent ID or access URL to {n} files"),
    "file_format": ("File format", "files", "Declare a file format for {n} files"),
    "croissant_valid": ("Croissant metadata", "checks", "Make the generated Croissant metadata pass validation"),
}
CHECK_SOURCE = {check_id: source for _, check_id, _, source in rc.METHODS}
NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}
LEVEL_NOUN = {"subject": "subjects", "biosample": "biosamples", "file": "files"}


@st.cache_data
def load_comparison() -> dict:
    with open(COMPARISON_JSON) as f:
        return json.load(f)


def needs_checkboxes(labels: dict, page: str) -> list[str]:
    """The "My model needs" checkboxes. The choice is kept in session state, so it carries
    over between Find ML-ready data and the Dataset basket (widget state alone is cleared
    when a page is left)."""
    st.markdown("**My model needs:**")
    saved = st.session_state.setdefault("needs", ["sex", "age"])
    # Two rows of four, so labels are never cut off on narrower screens.
    cols = st.columns(4)
    chosen = [req for i, (req, label) in enumerate(labels.items())
              if cols[i % 4].checkbox(label, value=req in saved, key=f"{page}_need_{req}")]
    st.session_state["needs"] = chosen
    return chosen


def count_levels(chosen: list[str]) -> list[str]:
    """Record levels at which every chosen requirement can be counted."""
    if set(chosen) & rc.FILE_ONLY_REQUIREMENTS:
        return ["file"]
    if {"anatomy", "disease"} & set(chosen):
        return ["biosample", "file"]
    return ["subject", "biosample", "file"]


def level_choice(chosen: list[str], page: str) -> str:
    """Which records to count (subjects, biosamples or files), remembered across pages."""
    levels = count_levels(chosen)
    if len(levels) == 1:
        st.caption("Counting files: checksums and file format are recorded per file.")
        level = levels[0]
    else:
        saved = st.session_state.get("level")
        level = st.radio("Count", levels, index=levels.index(saved) if saved in levels else 0,
                         format_func=lambda lv: LEVEL_NOUN[lv], horizontal=True, key=f"{page}_level")
    st.session_state["level"] = level
    return level


SEX_RULE = "Sex = male or female recorded; Indeterminate not counted (a model can't use it)."


def indeterminate_note(records: list[tuple[str, dict]], level: str, chosen: list[str]) -> str:
    """'ExRNA: 1,223 subjects ...' for records whose only sex value is Indeterminate."""
    if "sex" not in chosen:
        return ""
    noun = finder_noun(level, ["sex"])
    parts = [f"{label}: {r['sex_indeterminate'][level]:,} {noun}" for label, r in records
             if r.get("sex_indeterminate", {}).get(level)]
    return ("Recorded only as Indeterminate, so not counted as having sex - " + "; ".join(parts) + ".") if parts else ""


def finder_noun(level: str, chosen: list[str]) -> str:
    """What the counts are out of: sex/age subject counts are out of single-organism subjects."""
    if level == "subject" and rc.ORGANISM_REQUIREMENTS & set(chosen):
        return "single-organism subjects"
    return LEVEL_NOUN[level]


def name(r: dict) -> str:
    return DISPLAY_NAME.get(r.get("release", ""), r["program"])


def score_of(r: dict, dim: str):
    s = r["dimensions"][dim]["score"]
    return None if s == rc.NOT_ASSESSABLE else s


def ink(value) -> str:
    """Text colour on a scale-coloured cell (cell colours are the same in both themes)."""
    return INK_ON_DARK if value is not None and value >= DARK_TEXT_FROM else INK_ON_LIGHT


def blue_scale() -> dict:
    return {"domain": [0, 100], "range": [BLUE_RAMP[0], BLUE_RAMP[-1]], "interpolate": "rgb"}


def show_chart(spec: dict, rows: list[dict], **kwargs):
    """Render a Vega-Lite chart. Streamlit keeps showing the previous chart when only the
    data changes and the new rows have the same shape (e.g. the radar after picking another
    program), so a fingerprint of the data goes into the spec: a changed spec is redrawn."""
    fingerprint = hashlib.sha1(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:12]
    st.vega_lite_chart(pd.DataFrame(rows), {**spec, "description": f"data {fingerprint}"}, **kwargs)


def footer():
    st.divider()
    st.caption(f"{rc.DISCLAIMER} Dimensions from [*AI-readiness Criteria for Biomedical Data*]({PAPER_URL}) "
               f"(Clark et al., bioRxiv 2024, doi:10.1101/2024.10.23.619844). "
               f"Source code: [GitHub]({REPO_URL}).")


# ---------------------------------------------------------------------------
# Charts (Vega-Lite specs; rendered with st.vega_lite_chart)
# ---------------------------------------------------------------------------

def radar_chart(programs: list[dict], highlight: str):
    """All programs as thin gray outlines, one highlighted in blue, on the 6 scored dimensions."""
    n = len(SCORED_DIMENSIONS)
    angle = [math.pi / 2 - 2 * math.pi * i / n for i in range(n)]  # start at the top, go clockwise
    rows = []
    for level in (0.25, 0.5, 0.75, 1.0):
        for i in range(n + 1):
            rows.append({"kind": "grid", "level": level, "i": i,
                         "x": level * math.cos(angle[i % n]), "y": level * math.sin(angle[i % n])})
    for i, dim in enumerate(SCORED_DIMENSIONS):
        x, y = math.cos(angle[i]), math.sin(angle[i])
        rows.append({"kind": "spoke", "x": 0, "y": 0, "x2": x, "y2": y})
        side = "center" if abs(x) < 0.1 else ("left" if x > 0 else "right")
        rows.append({"kind": f"label-{side}", "x": 1.42 * x, "y": 1.42 * y,
                     "text": SHORT_DIMENSION.get(dim, dim)})
    for r in programs:
        kind = "focus" if name(r) == highlight else "context"
        points = [(i, dim, score_of(r, dim)) for i, dim in enumerate(SCORED_DIMENSIONS) if score_of(r, dim) is not None]
        for order, (i, dim, score) in enumerate(points + points[:1]):  # repeat the first point to close
            rows.append({"kind": kind, "program": name(r), "dimension": dim, "score": score, "i": order,
                         "x": score / 100 * math.cos(angle[i]), "y": score / 100 * math.sin(angle[i]),
                         "lx": (score / 100 + 0.17) * math.cos(angle[i]),
                         "ly": (score / 100 + 0.17) * math.sin(angle[i]), "last": order == len(points)})

    def only(kind):
        return [{"filter": f"datum.kind == '{kind}'"}]

    # 600 x 540 px: x spans 4.4 units and y 4.0, so both are ~135 px per unit (no stretching),
    # with room for the longest dimension name beside the outer ring.
    scale = {"domain": [-2.2, 2.2], "nice": False, "zero": False}
    y_scale = {"domain": [-2.0, 2.0], "nice": False, "zero": False}
    xy = {"x": {"field": "x", "type": "quantitative", "scale": scale, "axis": None},
          "y": {"field": "y", "type": "quantitative", "scale": y_scale, "axis": None}}
    tooltip = [{"field": "program", "title": "Program"}, {"field": "dimension", "title": "Dimension"},
               {"field": "score", "title": "Score"}]
    layers = [
        {"transform": only("grid"), "mark": {"type": "line", "color": GRID, "strokeWidth": 1, "opacity": 0.45},
         "encoding": {**xy, "detail": {"field": "level"}, "order": {"field": "i"}}},
        {"transform": only("spoke"), "mark": {"type": "rule", "color": GRID, "strokeWidth": 1, "opacity": 0.45},
         "encoding": {**xy, "x2": {"field": "x2"}, "y2": {"field": "y2"}}},
        {"transform": only("context"), "mark": {"type": "line", "color": CONTEXT_LINE, "strokeWidth": 1.25},
         "encoding": {**xy, "detail": {"field": "program"}, "order": {"field": "i"}}},
        {"transform": only("context") + [{"filter": "!datum.last"}],
         "mark": {"type": "point", "filled": True, "size": 60, "color": CONTEXT_LINE, "opacity": 0.9},
         "encoding": {**xy, "tooltip": tooltip}},
        {"transform": only("focus"), "mark": {"type": "line", "color": HIGHLIGHT, "strokeWidth": 2.5},
         "encoding": {**xy, "order": {"field": "i"}}},
        {"transform": only("focus") + [{"filter": "!datum.last"}],
         "mark": {"type": "point", "filled": True, "size": 90, "color": HIGHLIGHT},
         "encoding": {**xy, "tooltip": tooltip}},
        {"transform": only("focus") + [{"filter": "!datum.last"}],
         "mark": {"type": "text", "fontSize": 13, "fontWeight": "bold", "color": CHART_TEXT},
         "encoding": {"x": {"field": "lx", "type": "quantitative", "scale": scale, "axis": None},
                      "y": {"field": "ly", "type": "quantitative", "scale": y_scale, "axis": None},
                      "text": {"field": "score"}}},
    ]
    for side in ("left", "right", "center"):
        layers.append({"transform": only(f"label-{side}"),
                       "mark": {"type": "text", "fontSize": 14, "fontWeight": 600, "color": CHART_TEXT, "align": side,
                                "baseline": "middle"},
                       "encoding": {**xy, "text": {"field": "text"}}})
    spec = {"width": 600, "height": 540, "layer": layers, "config": {"view": {"stroke": None}}}
    show_chart(spec, rows, width="content")


def track_bars(rows: list[dict], y_title: str, label_field: str, height_per_row: int = 44, label_room: int = 45):
    """Horizontal 0-100 bars on a gray track, with a text label to the right of each track."""
    order = [r["row"] for r in rows]
    y = {"field": "row", "type": "nominal", "sort": order, "title": None,
         "axis": {"labelFontSize": 13, "labelLimit": 220, "ticks": False, "domain": False}}
    x = {"type": "quantitative", "scale": {"domain": [0, 100]}, "title": y_title,
         "axis": {"grid": False, "values": [0, 25, 50, 75, 100]}}
    spec = {
        "height": height_per_row * len(rows),
        "padding": {"left": 5, "top": 5, "bottom": 5, "right": label_room},
        "layer": [
            {"mark": {"type": "bar", "color": TRACK, "cornerRadiusEnd": 4, "height": 20},
             "encoding": {"y": y, "x": {**x, "datum": 100}}},
            {"mark": {"type": "bar", "color": HIGHLIGHT, "cornerRadiusEnd": 4, "height": 20},
             "encoding": {"y": y, "x": {**x, "field": "pct"},
                          "tooltip": [{"field": "row", "title": "Program"},
                                      {"field": label_field, "title": "Records"}]}},
            {"mark": {"type": "text", "align": "left", "dx": 8, "fontSize": 14, "fontWeight": 600, "color": CHART_TEXT},
             "encoding": {"y": y, "x": {**x, "datum": 100}, "text": {"field": label_field}}},
        ],
        "config": {"view": {"stroke": None}},
    }
    show_chart(spec, rows, width="stretch")


def coverage_heatmap(programs: list[dict]):
    rows = []
    for r in programs:
        for f in r["field_coverage"]:
            pct = round(100 * f["passed"] / f["total"]) if f["total"] else None
            rows.append({"Program": name(r), "Field": f["label"], "pct": pct,
                         "text": f"{pct}%" if pct is not None else "n/a",
                         "Records": (f"{f['passed']:,} of {f['total']:,} {f['unit']}" if f["total"]
                                     else f"no {f['unit']} to measure"),
                         "Source": f["columns"], "ink": ink(pct)})
    fields = [f["label"] for f in programs[0]["field_coverage"]]
    # Gaps between cells come from band padding, so they show the page background in either theme.
    band = {"paddingInner": 0.08}
    enc = {"x": {"field": "Field", "type": "nominal", "sort": fields, "title": None, "scale": band,
                 # Multi-word headers on two lines, so all 8 fit side by side without Vega hiding any.
                 "axis": {"orient": "top", "labelAngle": 0, "labelFontSize": 13, "labelLimit": 160,
                          "labelExpr": "split(datum.label, ' ')", "labelOverlap": False,
                          "ticks": False, "domain": False}},
           "y": {"field": "Program", "type": "nominal", "sort": [name(r) for r in programs], "title": None,
                 "scale": band,
                 "axis": {"labelFontSize": 13, "labelLimit": 200, "ticks": False, "domain": False}}}
    tooltip = [{"field": "Program"}, {"field": "Field"}, {"field": "Records"},
               {"field": "Source", "title": "C2M2 column(s)"}]
    spec = {
        "height": {"step": 46},
        "layer": [
            {"mark": {"type": "rect", "color": NA_FILL, "cornerRadius": 3},
             "encoding": {**enc, "tooltip": tooltip}},
            {"transform": [{"filter": "datum.pct != null"}],
             "mark": {"type": "rect", "cornerRadius": 3},
             "encoding": {**enc, "tooltip": tooltip,
                          "color": {"field": "pct", "type": "quantitative", "scale": blue_scale(),
                                    "legend": {"title": "% filled", "orient": "bottom", "gradientLength": 220}}}},
            {"mark": {"type": "text", "fontSize": 14, "fontWeight": "bold"},
             "encoding": {**enc, "text": {"field": "text"}, "tooltip": tooltip,
                          "color": {"field": "ink", "type": "nominal", "scale": None}}},
        ],
        # The cells' blue scale and the text's literal ink colours are separate colour scales.
        "resolve": {"scale": {"color": "independent"}},
        "config": {"view": {"stroke": None}},
    }
    show_chart(spec, rows, width="stretch")


# ---------------------------------------------------------------------------
# Report card pieces
# ---------------------------------------------------------------------------

def top_fixes(r: dict, n: int = 3) -> list[dict]:
    """The checks whose gap, if closed, would raise the overall score most.
    Overall = mean of assessed dimensions, each the mean of its measured checks,
    so bringing one check to 100 adds (100 - score) / checks-in-dimension / dimensions."""
    fixes = []
    for dim_name, dim in r["dimensions"].items():
        measured = [c for c in dim["checks"] if c["score"] is not None]
        for c in measured:
            if c["score"] < 100:
                gain = (100 - c["score"]) / len(measured) / r["dimensions_assessed"]
                label, _, fix = CHECK_INFO.get(c["id"], (c["id"], "", "Improve {n}"))
                fixes.append({"gain": gain, "dimension": dim_name, "label": label,
                              "text": fix.format(n=f"{c['total'] - c['passed']:,}")})
    return sorted(fixes, key=lambda f: -f["gain"])[:n]


CARDS_PER_ROW = 4  # wide enough for "Metabolomics Workbench" and the caption at 1100px


def score_cards(programs: list[dict]):
    rows = [programs[i:i + CARDS_PER_ROW] for i in range(0, len(programs), CARDS_PER_ROW)]
    cards = [(col, r) for row in rows for col, r in zip(st.columns(CARDS_PER_ROW), row)]
    for col, r in cards:
        with col.container(border=True):
            st.markdown(f"**{name(r)}**")
            st.metric("Score", r["overall_score"], help="Overall score, 0-100")
            # The older-release flag is part of the caption so it wraps in narrow cards
            # (a badge is cut off below ~1200px wide).
            old = rc.is_old_release(r["release_date"])
            st.caption(f"Released {r['release_date']}" + (" · **older release**" if old else ""),
                       help=rc.OLD_RELEASE_FLAG if old else None)


def report_card(r: dict):
    """One program's report card (also used for an uploaded datapackage)."""
    head = st.columns([1, 1, 2])
    head[0].metric("Overall score", r["overall_score"])
    head[1].metric("Dimensions assessed", f"{r['dimensions_assessed']} of {len(DIMENSION_NAMES)}")
    rc_counts = r["record_counts"]
    head[2].markdown(f"**Release:** `{r['release']}` · {r.get('release_date') or 'unknown'}  \n"
                     + " · ".join(f"{rc_counts.get(t, 0):,} {t}s" for t in rc.RECORD_TABLES))
    if rc.is_old_release(r.get("release_date", "")):
        head[2].badge("Older release - may not reflect current metadata", color="gray")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("##### Scores by dimension")
        rows = [{"row": SHORT_DIMENSION.get(d, d), "pct": score_of(r, d) or 0,
                 "label": str(score_of(r, d)) if score_of(r, d) is not None else "n/a"}
                for d in SCORED_DIMENSIONS]
        track_bars(rows, "Score (0-100)", "label", height_per_row=40, label_room=45)
        st.caption("Ethics is not shown: it is not measurable from C2M2 (a schema gap - there are no consent "
                   "or governance fields), not a gap in this program's metadata.")
    with right:
        with st.container(border=True):
            st.markdown("##### Top fixes")
            fixes = top_fixes(r)
            if not fixes:
                st.markdown("Every measured check is at 100.")
            for i, f in enumerate(fixes, 1):
                st.markdown(f"**{i}. {f['text']}**  \n+{f['gain']:.1f} points overall · {f['dimension']}")
            st.caption("Points each change would add to the overall score on its own, holding everything else "
                       "equal.")

    st.markdown("#### Every check")
    cols = st.columns(2, gap="large")
    for i, dim_name in enumerate(DIMENSION_NAMES):
        dim = r["dimensions"][dim_name]
        with cols[i % 2].container(border=True):
            score = score_of(r, dim_name)
            st.markdown(f"**{dim_name}** · " + (f"{score} / 100" if score is not None else "not assessable"))
            if score is None:
                st.caption(dim["reason"])
            for c in dim["checks"]:
                label, unit, _ = CHECK_INFO.get(c["id"], (c["id"], "", ""))
                if c["score"] is None:
                    st.markdown(f"{label}: nothing to measure")
                    continue
                if c["id"] == "croissant_valid":  # a pass/fail check, not a count
                    passed = c["passed"] == c["total"]
                    st.progress(c["score"] / 100, text=f"{label} — {'passes' if passed else 'does not pass'} validation")
                    st.caption(f"{c['detail']}.")
                    continue
                st.progress(c["score"] / 100, text=f"{label} — {c['passed']:,} of {c['total']:,} {unit} ({c['score']}%)")
                observation = (f"All {c['total']:,} {unit} have it recorded." if c["passed"] == c["total"]
                               else f"{c['detail']}.")
                st.caption(observation)
            for info in dim.get("info", []):
                st.caption(f"Info (not scored): {info}")
            if dim["checks"]:
                with st.expander("Why these matter · C2M2 source"):
                    for c in dim["checks"]:
                        label = CHECK_INFO.get(c["id"], (c["id"],))[0]
                        st.markdown(f"**{label}.** {c.get('why_it_matters', '')}  \n"
                                    f"Source: `{CHECK_SOURCE.get(c['id'], '')}` · check `{c['id']}`")

    notes = r.get("data_quality_notes", [])
    with st.expander(f"Data quality notes ({len(notes)}) - reported, not scored"):
        for note in notes or ["None found by the checks we run."]:
            st.markdown(f"- {note}")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def overview():
    data = load_comparison()
    programs = data["programs"]
    st.title("CFDE metadata AI-readiness at a glance")
    st.markdown(f"How much of what an AI developer needs is recorded in the C2M2 metadata of "
                f"{len(programs)} CFDE programs, scored 0-100 on six measurable dimensions.")
    score_cards(programs)

    st.markdown(f"### Six dimensions, {NUMBER_WORDS.get(len(programs), len(programs))} programs")
    names = [name(r) for r in programs]
    highlight = st.segmented_control("Highlight a program", names, default=names[0], key="radar_program") or names[0]
    st.caption(f"{highlight} in blue with its scores; the other programs in gray (hover a point for its name). "
               "Rings mark 25, 50, 75 and 100. Ethics is not shown: not measurable from C2M2 - schema gap.")
    radar_chart(programs, highlight)

    st.markdown("### 3 key findings")
    program_name = {r["program"]: name(r) for r in programs}.get
    for col, gap in zip(st.columns(3), data["top_gaps"]):
        label, unit, _ = CHECK_INFO.get(gap["check"], (gap["description"], "records", ""))
        low = min(gap["programs"], key=lambda p: p["score"])
        high = max(gap["programs"], key=lambda p: p["score"])
        with col.container(border=True):
            st.markdown(f"<div style='font-size:2.4rem;font-weight:700;line-height:1.1'>{gap['average_score']}%</div>",
                        unsafe_allow_html=True)
            st.markdown(f"**{label}: recorded for {gap['average_score']}% of {unit} on average**")
            st.caption(f"Across {len(gap['programs'])} programs, from {low['score']}% "
                       f"({program_name(low['program'])}) to {high['score']}% "
                       f"({program_name(high['program'])}). {gap['why_it_matters']}")
    footer()


def field_coverage_page():
    data = load_comparison()
    programs = data["programs"]
    st.title("Field coverage")
    st.markdown("How many records have each key field filled in. Darker blue = more records filled; "
                "hover a cell for the exact count and the C2M2 column it comes from.")
    coverage_heatmap(programs)
    st.caption("Sex and age are counted for single-organism subjects (human or animal); sex here counts any recorded value, including Indeterminate, as the score does. Disease link = biosamples "
               "linked to a disease directly or through their subject. Persistent ID and creation time count all "
               "project, subject, biosample and file records. n/a = nothing to measure.")
    with st.expander("Show as a table"):
        st.dataframe(pd.DataFrame([{"Program": name(r), **{f["label"]: (f"{f['passed']:,} / {f['total']:,}")
                                                          for f in r["field_coverage"]}} for r in programs]),
                     hide_index=True, width="stretch")
    footer()


def finder_page():
    data = load_comparison()
    programs = data["programs"]
    labels = data["requirements"]
    st.title("Find ML-ready data")
    st.markdown("Pick what your model needs. Each bar shows how many records in each program meet **all** "
                "of the selected requirements, counted exactly from the metadata.")
    chosen = needs_checkboxes(labels, "finder")
    if not chosen:
        st.info("Select at least one requirement.")
        footer()
        return
    level = level_choice(chosen, "finder")

    organism_rule = bool(rc.ORGANISM_REQUIREMENTS & set(chosen))
    noun = finder_noun(level, chosen)
    if organism_rule:
        st.caption("Sex and age count only for single-organism subjects (human or animal), the same rule as the "
                   "scores and Field coverage. Cell lines, microbiomes and synthetic subjects - and biosamples or "
                   "files linked only to them - don't meet a sex or age requirement."
                   + (f" **{SEX_RULE}**" if "sex" in chosen else ""))

    rows = []
    for r in programs:
        met, total = rc.count_meeting(r["combinations"], level, chosen)
        pct = 100 * met / total if total else 0
        rows.append({"row": name(r), "pct": pct, "met": met, "total": total,
                     # The unit is in the heading above, so the bar labels stay short enough to fit.
                     "label": f"{met:,} of {total:,}" + (f" ({pct:.0f}%)" if total else "")})
    rows.sort(key=lambda row: (-row["pct"], -row["met"]))
    wanted = " and ".join(labels[c].lower().replace(" ids", " IDs") for c in chosen)
    st.markdown(f"##### {noun[0].upper() + noun[1:]} with {wanted}")
    track_bars(rows, f"% of {noun}", "label")
    if note := indeterminate_note([(name(r), r["combinations"]) for r in programs], level, chosen):
        st.caption(note)
    with st.expander("Show as text"):
        for row in rows:
            st.markdown(f"- **{row['row']}:** {row['met']:,} of {row['total']:,} {noun} have {wanted}")
    with st.expander("How requirements are counted"):
        st.markdown(data["combination_rules"])
        st.markdown("SenNet's files are not linked to individual biosamples or subjects in its C2M2 release "
                    "(its file_describes_biosample / file_describes_subject tables are empty), so file counts "
                    "that need sex, age, anatomy or disease are 0 there.")
    footer()


def program_page():
    data = load_comparison()
    st.title("Program report card")
    by_name = {name(r): r for r in data["programs"]}
    uploaded = st.session_state.get("uploaded_result")
    if uploaded:
        by_name[f"{name(uploaded)} (your upload)"] = uploaded
    choice = st.selectbox("Program", list(by_name), key="report_program")
    report_card(by_name[choice])
    footer()


def methods_page():
    data = load_comparison()
    st.title("Methods")
    st.markdown(
        "Each dimension is made of one or more checks. Each check is a fraction (records that pass / records "
        "checked), shown as 0-100 with its raw numbers. A check with nothing to measure is skipped, not scored 0; "
        "a dimension with no measurable checks is *not assessable*. A dimension's score is the average of its "
        "checks, and the overall score is the average of the assessable dimensions. Info lines, field coverage, "
        "requirement counts and data quality notes are reported but never scored.")
    # A static table wraps long cells, so the C2M2 column lists are never cut off.
    st.table(pd.DataFrame([{"Dimension": dim, "Check": CHECK_INFO.get(cid, (cid,))[0], "What it measures": what,
                            "C2M2 table: column(s)": src, "Check ID": cid}
                           for dim, cid, what, src in rc.METHODS]).set_index("Dimension"))
    st.markdown(
        "**Rules worth knowing**\n"
        "- *Persistent identifiers:* one scheme list applies to both `persistent_id` and `access_url`: DOI, "
        "identifiers.org, ARK, `drs://`, Handle, PURL. Plain `s3://` and ordinary `https://` URLs don't count. "
        "identifiers.org compact identifiers are recognised for prefixes confirmed in the registry "
        f"({', '.join(f'`{p}`' for p in rc.IDENTIFIERS_ORG_PREFIXES)}).\n"
        "- *Sex and age* are scored only for single-organism subjects (human or animal); cell lines, synthetic "
        "entities, microbiomes etc. are excluded and reported. NIH's Sex as a Biological Variable policy applies "
        "to human and animal studies alike.\n"
        "- *Labels* count if they come from the datapackage's own term tables, or were read off the CFDE portal.\n"
        "- A real datapackage is one program's submission and is scored as a whole.\n"
        f"- *Find ML-ready data:* {data['combination_rules']}\n"
        "- *Top fixes:* bringing one check to 100 adds (100 - its score) / (checks in its dimension) / "
        "(dimensions assessed) points to the overall score.")
    st.subheader("Dataset basket: project-level scores")
    st.markdown(
        f"A C2M2 datapackage is a whole program, but researchers usually pick projects or studies, so every "
        f"project is also scored. {rc.PROJECT_RULES} The whole-program project (the root of each program's "
        "project tree) reproduces the program's own scores exactly, which is checked every time the project "
        "scores are rebuilt. Project scores are precomputed offline (`readiness_checker.py --projects`) and "
        "stored in `output/readiness_projects.json`; project descriptions there are shortened to "
        f"{rc.PROJECT_DESCRIPTION_CHARS} characters.\n\n"
        "**What \"meets your needs\" means.** For each project in the basket, the counts come from the same exact "
        "combination counts as *Find ML-ready data*, at the record level you choose:\n"
        f"- *{MEETS}*: every counted record has all the selected needs.\n"
        f"- *{PARTLY}*: some do; the review shows how many, and which needs not every record has.\n"
        f"- *{NOT_MET}*: none do, or the project has no records of that kind.\n\n"
        "If a project and one of its sub-projects are both in the basket, the sub-project's records are counted "
        "once, as part of the parent.\n\n"
        "**What the export contains.** Everything is generated in your browser session; nothing is stored on the "
        "server.\n"
        "- *Manifest (CSV or JSON):* one row per project with program, project name and ID, record counts, the "
        "needs, qualifying and total counts, status, the C2M2 download URL, release file, release date and the "
        "release zip's sha256.\n"
        "- *Croissant metadata:* a Croissant 1.0 JSON-LD file listing each program's release zip (with its sha256), "
        "the C2M2 tables inside it and the columns behind your needs, and naming the selected projects. It passes "
        "`validate_croissant.py`.\n"
        "- *Summary report (Markdown):* the needs, the status of each project, and the download links.")
    st.subheader("Relation to CFDE's c2m2-assessment")
    st.markdown(
        f"CFDE already has an assessment tool for C2M2 datapackages, [nih-cfde/c2m2-assessment]"
        f"({C2M2_ASSESSMENT_URL}) (by Daniel J. B. Clarke). It runs FAIRshake-style rubrics and reports, per "
        "metric, a value with its numerator and denominator; its default rubric measures FAIRness, including "
        "live-testing a sample of access URLs, persistent identifiers on files, and about 34 coverage metrics. "
        "This tool does not replace it and does not use its code. It asks a different question: the Bridge2AI "
        "paper argues that FAIR conformance alone is not sufficient for AI-readiness and defines seven "
        "dimensions, of which FAIRness is one. This checker is a first attempt at simple proxies for all seven "
        "from C2M2 metadata alone; its FAIRness checks are deliberately coarser than c2m2-assessment's.")
    st.subheader("Limitations")
    st.markdown(
        "- Simplified proxies, not an official implementation of the Bridge2AI criteria; they measure "
        "metadata coverage only.\n"
        "- One release per program; releases older than two years are flagged.\n"
        "- Some gaps come from the C2M2 schema rather than the programs (no consent or governance fields).\n"
        "- Persistent identifiers are recognised by scheme; nothing is resolved over the network.\n"
        "- Every check and dimension is weighted equally, so overall scores are a rough summary.\n"
        "- Labels are checked for presence, not correctness.")
    st.caption(f"Citation: {rc.CITATION}.")
    footer()


def upload_page():
    st.title("Check your own datapackage")
    st.markdown(
        f"Upload a C2M2 datapackage as a `.zip` (up to **{MAX_UPLOAD_MB} MB** zipped and **{MAX_UNZIPPED_MB} MB** "
        "unzipped) to see its report card. The file is unpacked into a temporary folder, scored, and deleted; "
        "nothing is stored. Larger packages can be scored locally with "
        "`python3 src/readiness_checker.py --data-dir <folder>`.")
    file = st.file_uploader("C2M2 datapackage (.zip)", type="zip")
    if file is not None:
        result = score_upload(file)
        if result:
            st.session_state["uploaded_result"] = result
            st.success(f"Scored {file.name}. It also appears in the Program report card dropdown for this session.")
            report_card(result)
    footer()


def score_upload(file) -> dict | None:
    if file.size > MAX_UPLOAD_MB * 1024 * 1024:
        st.error(f"This file is {file.size / 1e6:.0f} MB; the limit here is {MAX_UPLOAD_MB} MB.")
        return None
    try:
        with zipfile.ZipFile(file) as zf:
            unzipped = sum(info.file_size for info in zf.infolist())
            if unzipped > MAX_UNZIPPED_MB * 1024 * 1024:
                st.error(f"Unzipped, this package is {unzipped / 1e6:.0f} MB; the limit here is "
                         f"{MAX_UNZIPPED_MB} MB. Please run the checker locally instead.")
                return None
            with tempfile.TemporaryDirectory() as tmp, st.spinner("Scoring the datapackage..."):
                zf.extractall(tmp)  # zipfile strips absolute paths and '..' from member names
                data_dir = rc.find_package_dir(Path(tmp))
                if data_dir is None:
                    st.error("No project.tsv was found in this zip, so it doesn't look like a C2M2 datapackage.")
                    return None
                return rc.score_real_package(data_dir, Path(tmp), release=(file.name, "unknown"))
    except zipfile.BadZipFile:
        st.error("This file could not be read as a zip archive.")
    except Exception as e:  # show the problem rather than a stack trace
        st.error(f"The checker could not score this package: {type(e).__name__}: {e}")
    return None


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Dataset basket: choose projects, set needs, review, export.
# Reads only output/readiness_projects.json (precomputed with
# `readiness_checker.py --projects`); nothing is scored or stored server-side.
# ---------------------------------------------------------------------------
MEETS, PARTLY, NOT_MET = "Meets your needs", "Partly", "Doesn't meet your needs"
STATUS_MARK = {MEETS: "●", PARTLY: "◐", NOT_MET: "○"}  # shape, not colour, tells them apart


@st.cache_data
def load_projects() -> dict:
    with open(PROJECTS_JSON) as f:
        data = json.load(f)
    data["program_info"] = {p["program"]: p for p in data["programs"]}
    for p in data["projects"]:
        p["key"] = project_key(p["program"], p["id"])
        p["parent_key"] = project_key(p["program"], p["parent"]) if p["parent"] else None
    data["by_key"] = {p["key"]: p for p in data["projects"]}
    return data


def project_key(program: str, pid: list[str]) -> str:
    return f"{program}|{pid[0]}|{pid[1]}"


def slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def assess(p: dict, requirements: list[str], level: str, chosen: list[str], labels: dict) -> dict:
    """Does this project meet the needs? Exact counts from the project's stored combinations."""
    combos = {"requirements": requirements, "levels": p["combinations"]}
    met, total = rc.count_meeting(combos, level, chosen)
    noun = finder_noun(level, chosen)
    # Each need on its own, out of the same records (single-organism subjects when sex/age apply).
    organism_rule = level == "subject" and bool(rc.ORGANISM_REQUIREMENTS & set(chosen))
    missing = []
    for need in chosen:
        extra = [rc.SINGLE_ORGANISM_BIT] if organism_rule and need not in rc.ORGANISM_REQUIREMENTS else []
        n, _ = rc.count_meeting(combos, level, [need] + extra)
        if n < total:
            missing.append(f"{labels[need].lower().replace(' ids', ' IDs')}: {n:,} of {total:,}")
    indeterminate = p.get("sex_indeterminate", {}).get(level, 0) if "sex" in chosen else 0
    if indeterminate:
        missing.append(f"{indeterminate:,} {finder_noun(level, ['sex'])} have sex recorded only as Indeterminate "
                       "(not counted)")
    status = NOT_MET if met == 0 else MEETS if met == total else PARTLY  # total == 0 -> met == 0
    return {"met": met, "total": total, "noun": noun, "status": status, "missing": missing}


def included_in(p: dict, basket: set, by_key: dict) -> dict | None:
    """The nearest ancestor project also in the basket (its counts already include this project)."""
    key = p["parent_key"]
    while key:
        if key in basket:
            return by_key.get(key)
        key = by_key[key]["parent_key"] if key in by_key else None
    return None


def basket_review(data: dict, chosen: list[str], level: str, labels: dict) -> list[dict]:
    basket = st.session_state["basket"]
    in_basket = set(basket)
    reviewed = []
    for key in basket:
        p = data["by_key"][key]
        a = assess(p, data["requirements"], level, chosen, labels)
        parent = included_in(p, in_basket, data["by_key"])
        reviewed.append({"project": p, **a, "included_in": parent["name"] if parent else ""})
    return reviewed


# -- basket state changes (callbacks run before the rerun, so the whole page sees them) --

def basket_set(keys: list[str], add: bool):
    basket = st.session_state["basket"]
    for key in keys:
        if add and key not in basket:
            basket.append(key)
        elif not add and key in basket:
            basket.remove(key)
    st.session_state["basket_version"] += 1  # fresh editors, so no stale edits linger


def apply_editor(editor_key: str, shown_key: str, column: str):
    """Turn checkbox edits in a data editor into basket changes: ticked = in the basket."""
    shown = st.session_state[shown_key]
    for row, change in st.session_state[editor_key]["edited_rows"].items():
        if column in change:
            basket_set([shown[int(row)]], add=bool(change[column]))


# -- exports (built in the browser session; nothing is written server-side) --

def manifest_rows(reviewed: list[dict], data: dict, chosen: list[str], labels: dict) -> list[dict]:
    rows = []
    for r in reviewed:
        p, info = r["project"], data["program_info"][r["project"]["program"]]
        parent = data["by_key"].get(p["parent_key"]) if p["parent_key"] else None
        rows.append({
            "program": p["program"],
            "project_name": p["name"],
            "project_id_namespace": p["id"][0],
            "project_local_id": p["id"][1],
            "part_of": parent["name"] if parent else "",
            "subjects": p["record_counts"]["subject"],
            "biosamples": p["record_counts"]["biosample"],
            "files": p["record_counts"]["file"],
            "needs": "; ".join(labels[c] for c in chosen),
            "counted": r["noun"],
            "qualifying": r["met"],
            "out_of": r["total"],
            "status": r["status"],
            "missing": "; ".join(r["missing"]),
            "already_included_in": r["included_in"],
            "overall_score": p["overall_score"],
            "c2m2_download_url": info["download_url"],
            "release_file": info["release"],
            "release_date": info["release_date"],
            "older_release": info["old_release"],
            "release_zip_sha256": info["sha256"],
        })
    return rows


# Columns described in the Croissant export: keys always, plus the columns behind each need.
KEY_COLUMNS = {
    "project": ["id_namespace", "local_id", "name", "description"],
    "subject": ["id_namespace", "local_id", "project_id_namespace", "project_local_id", "granularity"],
    "biosample": ["id_namespace", "local_id", "project_id_namespace", "project_local_id"],
    "file": ["id_namespace", "local_id", "project_id_namespace", "project_local_id", "filename",
             "size_in_bytes", "access_url"],
    "biosample_from_subject": ["biosample_id_namespace", "biosample_local_id",
                               "subject_id_namespace", "subject_local_id"],
    "file_describes_biosample": ["file_id_namespace", "file_local_id", "biosample_id_namespace", "biosample_local_id"],
    "file_describes_subject": ["file_id_namespace", "file_local_id", "subject_id_namespace", "subject_local_id"],
    "biosample_disease": ["biosample_id_namespace", "biosample_local_id", "disease"],
    "subject_disease": ["subject_id_namespace", "subject_local_id", "disease"],
}
NEED_COLUMNS = {
    "sex": {"subject": ["sex"]},
    "age": {"subject": ["age_at_enrollment"], "biosample_from_subject": ["age_at_sampling"]},
    "anatomy": {"biosample": ["anatomy"]},
    "disease": {},  # the disease tables themselves (always listed when present)
    "checksum": {"file": ["md5", "sha256"]},
    "persistent_id": {t: ["persistent_id"] for t in ("project", "subject", "biosample", "file")},
    "file_format": {"file": ["file_format"]},
}
NUMERIC_COLUMNS = {"age_at_enrollment": "sc:Float", "age_at_sampling": "sc:Float", "size_in_bytes": "sc:Integer"}


def basket_croissant(reviewed: list[dict], data: dict, chosen: list[str], labels: dict) -> dict:
    """Croissant 1.0 metadata describing the selection: each program's C2M2 release zip, the
    tables inside it, and the columns that matter for the chosen needs. The selected projects
    are named in the descriptions (C2M2 rows belong to a project via project_id_namespace/local_id)."""
    by_program: dict[str, list[dict]] = {}
    for r in reviewed:
        by_program.setdefault(r["project"]["program"], []).append(r["project"])
    distribution, record_sets = [], []
    for program, chosen_projects in by_program.items():
        info, prefix = data["program_info"][program], slug(program)
        zip_id = f"{prefix}-c2m2-zip"
        zip_obj = {"@type": "cr:FileObject", "@id": zip_id, "name": info["release"],
                   "description": f"{program} C2M2 datapackage, release {info['release_date']}.",
                   "contentUrl": info["download_url"], "encodingFormat": "application/zip"}
        if info["sha256"]:
            zip_obj["sha256"] = info["sha256"]
        distribution.append(zip_obj)
        ids = "; ".join(f"{p['name']} ({p['id'][0]} / {p['id'][1]})" for p in chosen_projects)
        for table, columns in info["columns"].items():
            wanted = list(KEY_COLUMNS.get(table, []))
            for need in chosen:
                wanted += NEED_COLUMNS[need].get(table, [])
            fields = [c for c in dict.fromkeys(wanted) if c in columns]
            if not fields:
                continue
            file_id = f"{prefix}/{table}.tsv"
            distribution.append({"@type": "cr:FileObject", "@id": file_id, "name": f"{table}.tsv",
                                 "containedIn": {"@id": zip_id},
                                 "contentUrl": f"{info['package_path']}/{table}.tsv".lstrip("/"),
                                 "encodingFormat": "text/tab-separated-values"})
            rs_id = f"{prefix}-{table}"
            key = ([{"@id": f"{rs_id}/local_id"}] if "local_id" in fields
                   else [{"@id": f"{rs_id}/{c}"} for c in fields if c.endswith("_local_id")])
            record_sets.append({
                "@type": "cr:RecordSet", "@id": rs_id, "name": f"{program} {table}",
                "description": (f"Rows of {program}'s C2M2 {table}.tsv. For this selection, use the rows that "
                                f"belong to the selected projects: {ids}."),
                "key": key,
                "field": [{"@type": "cr:Field", "@id": f"{rs_id}/{c}", "name": c,
                           "dataType": NUMERIC_COLUMNS.get(c, "sc:Text"),
                           "source": {"fileObject": {"@id": file_id}, "extract": {"column": c}}}
                          for c in fields],
            })
    needs_text = ", ".join(labels[c].lower() for c in chosen) or "none selected"
    return {
        "@context": {"@language": "en", "@vocab": "https://schema.org/", "cr": "http://mlcommons.org/croissant/",
                     "dct": "http://purl.org/dc/terms/", "sc": "https://schema.org/"},
        "@type": "sc:Dataset",
        "name": "cfde-dataset-basket",
        "description": (
            f"A selection of {len(reviewed)} project(s) from {len(by_program)} CFDE program(s), made with the "
            f"CFDE AI-readiness prototype's Dataset basket. Needs checked: {needs_text}. Each program's full C2M2 "
            "release is listed; a project's records are the subjects, biosamples and files whose "
            "project_id_namespace/project_local_id is that project or one of its sub-projects, plus the "
            f"biosamples and subjects they link to. {rc.DISCLAIMER}"),
        "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
        "url": "https://cfde.cloud/",
        "dateCreated": date.today().isoformat(),
        "isBasedOn": [data["program_info"][prog]["download_url"] for prog in by_program],
        "distribution": distribution,
        "recordSet": record_sets,
    }


def basket_report(reviewed: list[dict], data: dict, chosen: list[str], labels: dict, totals: dict) -> str:
    needs_text = ", ".join(labels[c] for c in chosen)
    lines = [
        "# Dataset basket summary", "",
        f"Generated {date.today().isoformat()} with the CFDE AI-readiness prototype ({REPO_URL}).", "",
        f"**{rc.DISCLAIMER}**", "",
        f"- Needs: {needs_text}; records counted: {reviewed[0]['noun'] if reviewed else 'records'}",
        f"- Projects in basket: {len(reviewed)}",
        f"- Meet your needs: {totals['meets']}; partly: {totals['partly']}; don't meet: {totals['not_met']}",
        f"- Qualifying records: {totals['qualifying']:,} {totals['noun']}"
        + (" (projects already included in a parent project in the basket are counted once)" if totals["nested"] else ""),
        "", "| Program | Project | Status | Qualifying | Not every record has | Overall score | Release |",
        "|---|---|---|---|---|---|---|"]
    for r in reviewed:
        p, info = r["project"], data["program_info"][r["project"]["program"]]
        note = f" (included in {r['included_in']})" if r["included_in"] else ""
        cell = lambda text: str(text).replace("|", "\\|")
        lines.append(f"| {cell(p['program'])} | {cell(p['name'])}{cell(note)} | {r['status']} | "
                     f"{r['met']:,} of {r['total']:,} {r['noun']} | {cell('; '.join(r['missing']) or '-')} | "
                     f"{p['overall_score'] if p['overall_score'] is not None else 'n/a'} | "
                     f"{info['release_date']}{' (older release)' if info['old_release'] else ''} |")
    lines += ["", "## Downloads", ""]
    for program in dict.fromkeys(r["project"]["program"] for r in reviewed):
        info = data["program_info"][program]
        lines.append(f"- {program}: [{info['release']}]({info['download_url']})"
                     + (f" (sha256 `{info['sha256']}`)" if info["sha256"] else ""))
    lines += ["", "## How this was counted", "",
              f"- {data['rules']}",
              f"- {MEETS}: every counted record has all the needs. {PARTLY}: some do. "
              f"{NOT_MET}: none do, or there are no such records.",
              f"- {data['combination_rules']}"]
    return "\n".join(lines) + "\n"


def basket_page():
    data = load_projects()
    labels = load_comparison()["requirements"]
    ss = st.session_state
    ss.setdefault("basket", [])
    ss.setdefault("basket_version", 0)
    version = ss["basket_version"]

    st.title("Dataset basket")
    st.markdown("Pick the projects you're interested in, say what your model needs, and see which projects "
                "have it. Keep the ones that fit and export the selection. Nothing is stored on the server; "
                "the basket lives in this browser session.")
    summary = st.container()

    # ---- 1. Choose ------------------------------------------------------------------
    st.subheader("1. Choose projects")
    f1, f2, f3 = st.columns([2, 2, 1])
    search = f1.text_input("Search project names and descriptions", key="basket_search",
                           placeholder="e.g. liver, RNA-seq, pediatric")
    programs = f2.multiselect("Programs", list(data["program_info"]), key="basket_programs",
                              placeholder="All programs")
    min_score = f3.number_input("Minimum score", 0, 100, 0, step=5, key="basket_min_score")
    basket = set(ss["basket"])
    needle = search.strip().lower()
    shown = [p for p in data["projects"]
             if (not programs or p["program"] in programs)
             and (p["overall_score"] or 0) >= min_score
             and (not needle or needle in p["name"].lower() or needle in p["description"].lower())]
    ss["basket_shown"] = [p["key"] for p in shown]
    table = pd.DataFrame([{
        "In basket": p["key"] in basket, "Program": p["program"], "Project": p["name"],
        "Subjects": p["record_counts"]["subject"], "Biosamples": p["record_counts"]["biosample"],
        "Files": p["record_counts"]["file"], "Score": p["overall_score"],
        "Contains": f"{p['sub_projects']} sub-projects" if p["sub_projects"] else "",
        "Description": p["description"]} for p in shown],
        columns=["In basket", "Program", "Project", "Subjects", "Biosamples", "Files", "Score", "Contains",
                 "Description"])
    st.caption(f"{len(shown):,} of {len(data['projects']):,} projects shown · {len(basket):,} in your basket. "
               "Tick **In basket** to add a project. A project that contains sub-projects includes their records.")
    editor_key = f"basket_choose_{version}"
    st.data_editor(
        table, key=editor_key, hide_index=True, height=380, width="stretch",
        disabled=[c for c in table.columns if c != "In basket"],
        on_change=apply_editor, args=(editor_key, "basket_shown", "In basket"),
        # Pixel widths wide enough for each header and value, so nothing is clipped at 1100px.
        column_config={
            "In basket": st.column_config.CheckboxColumn(width=85),
            "Program": st.column_config.TextColumn(width=165),
            "Project": st.column_config.TextColumn(width=300),
            "Subjects": st.column_config.NumberColumn(format="localized", width=85),
            "Biosamples": st.column_config.NumberColumn(format="localized", width=95),
            "Files": st.column_config.NumberColumn(format="localized", width=95),
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d", width=125,
                                                     help="Overall AI-readiness score of the project, 0-100"),
            "Contains": st.column_config.TextColumn(width=135),
            "Description": st.column_config.TextColumn(width="large"),
        })
    b1, b2, _ = st.columns([1, 1, 2])
    to_add = [p["key"] for p in shown if p["key"] not in basket]
    b1.button(f"Add all {len(to_add):,} shown" if to_add else "All added",
              disabled=not to_add, on_click=basket_set, args=(to_add, True), key="basket_add_all")
    b2.button("Empty the basket", disabled=not basket, on_click=basket_set, args=(list(ss["basket"]), False),
              key="basket_clear")

    # ---- 2. Needs -------------------------------------------------------------------
    st.subheader("2. Set your needs")
    chosen = needs_checkboxes(labels, "basket")
    level = level_choice(chosen, "basket") if chosen else "subject"
    if chosen and rc.ORGANISM_REQUIREMENTS & set(chosen):
        st.caption("Sex and age count only for single-organism subjects (human or animal), as elsewhere in the app."
                   + (f" **{SEX_RULE}**" if "sex" in chosen else ""))

    # ---- 3. Review ------------------------------------------------------------------
    st.subheader("3. Review")
    reviewed = basket_review(data, chosen, level, labels) if chosen else []
    counted = [r for r in reviewed if not r["included_in"]]
    totals = {"meets": sum(r["status"] == MEETS for r in reviewed),
              "partly": sum(r["status"] == PARTLY for r in reviewed),
              "not_met": sum(r["status"] == NOT_MET for r in reviewed),
              "qualifying": sum(r["met"] for r in counted),
              "noun": finder_noun(level, chosen) if chosen else "records",
              "nested": len(reviewed) - len(counted)}
    if not ss["basket"]:
        st.info("Your basket is empty. Tick projects in step 1 to add them.")
    elif not chosen:
        st.info("Select at least one need in step 2 to see which projects have it.")
    else:
        review_table = pd.DataFrame([{
            "Keep": True,
            "Status": f"{STATUS_MARK[r['status']]} {r['status']}",
            # Short "X of Y" form; the status column says whether that meets the needs.
            "Qualifying": f"{r['met']:,} of {r['total']:,} {r['noun']}",
            "Program": r["project"]["program"], "Project": r["project"]["name"],
            "Missing": "; ".join(r["missing"]) or "-",
            "Within": r["included_in"]} for r in reviewed])
        ss["basket_review_keys"] = [r["project"]["key"] for r in reviewed]
        review_key = f"basket_review_{version}"
        st.caption("● meets your needs: every counted record has all of them · ◐ partly: some records do · "
                   "○ doesn't meet your needs: none do. Untick **Keep** to remove a project.")
        st.data_editor(
            review_table, key=review_key, hide_index=True, width="stretch",
            height=min(38 + 35 * len(review_table), 420),
            disabled=[c for c in review_table.columns if c != "Keep"],
            on_change=apply_editor, args=(review_key, "basket_review_keys", "Keep"),
            column_config={
                "Keep": st.column_config.CheckboxColumn(width=70),
                "Status": st.column_config.TextColumn(width=185),
                "Program": st.column_config.TextColumn(width=165),
                "Project": st.column_config.TextColumn(width=240),
                "Qualifying": st.column_config.TextColumn("Qualifying records", width=260,
                                                          help="Records with everything you need, out of all counted"),
                "Missing": st.column_config.TextColumn("Not every record has", width="large"),
                "Within": st.column_config.TextColumn(
                    "Counted as part of", width="medium",
                    help="This project sits inside another project in your basket, so its records are "
                         "counted once, as part of that project"),
            })
        not_met = [r["project"]["key"] for r in reviewed if r["status"] == NOT_MET]
        st.button(f"Remove {len(not_met):,} project{'s' if len(not_met) != 1 else ''} that don't meet my needs"
                  if not_met else "Every project meets your needs at least partly",
                  disabled=not not_met, on_click=basket_set, args=(not_met, False), key="basket_remove_not_met")
        if totals["nested"]:
            st.caption(f"{totals['nested']} project(s) sit inside another project in your basket; their records "
                       "are counted once, as part of that project.")

    # ---- 4. Export ------------------------------------------------------------------
    st.subheader("4. Export")
    if not reviewed:
        st.info("Add projects and choose at least one need to export a selection.")
    else:
        rows = manifest_rows(reviewed, data, chosen, labels)
        croissant = basket_croissant(reviewed, data, chosen, labels)
        errors = rc.validate_croissant(croissant)
        # Two rows of two, so button labels are never cut off on narrower screens.
        e1, e2 = st.columns(2)
        e3, e4 = st.columns(2)
        e1.download_button("Manifest (CSV)", pd.DataFrame(rows).to_csv(index=False), "basket_manifest.csv",
                           "text/csv", key="export_csv", on_click="ignore", width="stretch")
        e2.download_button("Manifest (JSON)",
                           json.dumps({"generated": date.today().isoformat(), "disclaimer": rc.DISCLAIMER,
                                       "needs": chosen, "counted": totals["noun"], "projects": rows}, indent=2),
                           "basket_manifest.json", "application/json", key="export_json", on_click="ignore",
                           width="stretch")
        e3.download_button("Croissant metadata (JSON-LD)", json.dumps(croissant, indent=2),
                           "basket_croissant.json", "application/ld+json", key="export_croissant",
                           on_click="ignore", width="stretch")
        e4.download_button("Summary report (Markdown)", basket_report(reviewed, data, chosen, labels, totals),
                           "basket_summary.md", "text/markdown", key="export_md", on_click="ignore",
                           width="stretch")
        st.caption("The manifest lists each project with its record counts, qualifying counts, C2M2 download URL "
                   "and release date. The Croissant file describes each program's release zip, the C2M2 tables "
                   "inside it and the columns behind your needs, and names the selected projects. "
                   + ("It passes validate_croissant.py." if not errors
                      else f"Validation problems: {'; '.join(errors)}"))

    with summary:
        c1, c2, c3 = st.columns(3)
        c1.metric("Projects in basket", f"{len(ss['basket']):,}")
        c2.metric("Meet your needs", f"{totals['meets']:,}" if chosen and reviewed else "-",
                  help=f"{totals['partly']:,} more meet them partly" if chosen and reviewed else None)
        c3.metric("Qualifying records", f"{totals['qualifying']:,}" if chosen and reviewed else "-",
                  help="Records that have everything you need, summed over the basket "
                       "(a project inside another basket project is counted once).")
        if chosen and reviewed:
            c3.caption(totals["noun"])
    footer()


st.set_page_config(page_title="CFDE AI-Readiness", layout="wide")
page = st.navigation([
    st.Page(overview, title="Overview", default=True),
    st.Page(field_coverage_page, title="Field coverage", url_path="coverage"),
    st.Page(finder_page, title="Find ML-ready data", url_path="find"),
    st.Page(program_page, title="Program report card", url_path="program"),
    st.Page(basket_page, title="Dataset basket", url_path="basket"),
    st.Page(methods_page, title="Methods", url_path="methods"),
    st.Page(upload_page, title="Check your own datapackage", url_path="upload"),
])
page.run()
