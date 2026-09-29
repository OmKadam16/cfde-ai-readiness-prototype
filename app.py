"""
app.py -- a browser view of the CFDE AI-Readiness Checker results.

Run locally:
    pip3 install -r requirements.txt
    streamlit run app.py

It reads only committed files (output/readiness_comparison.json), so it
runs from a fresh clone without data_real/. The upload page runs
src/readiness_checker.py live on a user's own small datapackage.

Pages answer three questions:
  Overview           -- how AI-ready is CFDE metadata, at a glance? (a reviewer)
  Field coverage     -- which key fields are filled, where? (everyone)
  Find ML-ready data -- which programs have records with everything my model needs? (a researcher)
  Program report card -- what would raise this program's readiness most? (a program's data team)
"""

import hashlib
import json
import math
import sys
import tempfile
import zipfile
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
    st.caption("Sex and age are counted for single-organism subjects (human or animal). Disease link = biosamples "
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
    st.markdown("**My model needs:**")
    # Two rows of four, so labels are never cut off on narrower screens.
    cols = st.columns(4)
    chosen = [req for i, (req, label) in enumerate(labels.items())
              if cols[i % 4].checkbox(label, value=req in ("sex", "age"), key=f"need_{req}")]
    if not chosen:
        st.info("Select at least one requirement.")
        footer()
        return

    # Count at the most specific level the requirements need.
    if set(chosen) & rc.FILE_ONLY_REQUIREMENTS:
        levels = ["file"]
    elif {"anatomy", "disease"} & set(chosen):
        levels = ["biosample", "file"]
    else:
        levels = ["subject", "biosample", "file"]
    if len(levels) == 1:
        level = levels[0]
        st.caption("Counting files: checksums and file format are recorded per file.")
    else:
        level = st.radio("Count", levels, format_func=lambda lv: LEVEL_NOUN[lv], horizontal=True, key="finder_level")

    organism_rule = bool(rc.ORGANISM_REQUIREMENTS & set(chosen))
    noun = finder_noun(level, chosen)
    if organism_rule:
        st.caption("Sex and age count only for single-organism subjects (human or animal), the same rule as the "
                   "scores and Field coverage. Cell lines, microbiomes and synthetic subjects - and biosamples or "
                   "files linked only to them - don't meet a sex or age requirement.")

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

st.set_page_config(page_title="CFDE AI-Readiness", layout="wide")
page = st.navigation([
    st.Page(overview, title="Overview", default=True),
    st.Page(field_coverage_page, title="Field coverage", url_path="coverage"),
    st.Page(finder_page, title="Find ML-ready data", url_path="find"),
    st.Page(program_page, title="Program report card", url_path="program"),
    st.Page(methods_page, title="Methods", url_path="methods"),
    st.Page(upload_page, title="Check your own datapackage", url_path="upload"),
])
page.run()
