"""
app.py -- a browser view of the CFDE AI-Readiness Checker results.

Run locally:
    pip3 install -r requirements.txt
    streamlit run app.py

It reads only committed files (output/readiness_comparison.json), so it
runs from a fresh clone without data_real/. The optional upload page runs
src/readiness_checker.py live on a user's own small datapackage.
"""

import json
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
# The unzipped cap keeps memory use within a free Streamlit Cloud instance
# (the checker needs roughly 1.5x the unzipped size in memory).
MAX_UPLOAD_MB = 50
MAX_UNZIPPED_MB = 300

DIMENSION_NAMES = [name for name, _ in rc.DIMENSIONS]


@st.cache_data
def load_comparison() -> dict:
    with open(COMPARISON_JSON) as f:
        return json.load(f)


def score_text(score) -> str:
    return "n/a" if score == rc.NOT_ASSESSABLE else str(score)


def release_date_text(r: dict) -> str:
    date = r.get("release_date") or "unknown"
    return f"{date} ({rc.OLD_RELEASE_FLAG})" if rc.is_old_release(date) else date


def records_text(r: dict) -> str:
    return " / ".join(f"{r['record_counts'].get(t, 0):,}" for t in rc.RECORD_TABLES)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def home():
    data = load_comparison()
    st.title("CFDE AI-Readiness Report Card")
    st.info(f"**{rc.DISCLAIMER}**")
    st.markdown(
        "This is an AI-readiness report card for the metadata that NIH Common Fund Data Ecosystem (CFDE) "
        "programs publish in the C2M2 format. It looks at each program's current C2M2 release and asks how "
        "much of what an AI developer would need is recorded in the metadata: persistent identifiers, "
        "provenance, descriptions of subjects and samples, labelled terms, and machine-readable file "
        "information. The checks are simple, measurable proxies for the seven AI-readiness dimensions "
        "defined by the Bridge2AI Standards Working Group in "
        f"[*AI-readiness Criteria for Biomedical Data*]({PAPER_URL}) (Clark et al., bioRxiv 2024, "
        "doi:10.1101/2024.10.23.619844). The results describe metadata coverage, not the quality of any "
        "program's data or work, and are meant to point at concrete, fixable gaps."
    )
    st.markdown(
        f"- **Source code and method:** [{REPO_URL.removeprefix('https://')}]({REPO_URL})\n"
        f"- **Programs covered:** {', '.join(r['program'] for r in data['programs'])} "
        f"(results generated {data['generated']})\n"
        "- **Pages:** *Comparison* (all programs side by side), *Program report card* (one program in "
        "detail), *Methods* (every check and its C2M2 source), *Check your own datapackage* (optional upload)."
    )
    st.caption(f"Citation: {rc.CITATION}.")


def comparison():
    data = load_comparison()
    programs = data["programs"]
    st.title("Comparison across programs")
    st.caption(rc.DISCLAIMER)

    rows = [{
        "Program": r["program"],
        "Overall": score_text(r["overall_score"]),
        **{name: score_text(r["dimensions"][name]["score"]) for name in DIMENSION_NAMES},
        "Release date": r["release_date"],
        "Release note": rc.OLD_RELEASE_FLAG if rc.is_old_release(r["release_date"]) else "",
        "Records (project / subject / biosample / file)": records_text(r),
        "Release file": r["release"],
    } for r in programs]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "Scores are 0-100. n/a = not assessable. Ethics is n/a for every program because of the C2M2 schema, "
        "not the programs: C2M2 has no consent or governance fields. Overall = average of the dimensions that "
        f"could be assessed. Releases older than {rc.OLD_RELEASE_YEARS} years are flagged."
    )

    st.subheader("Dimension scores")
    cells = [{"Program": r["program"], "Dimension": name,
              "Score": None if r["dimensions"][name]["score"] == rc.NOT_ASSESSABLE else r["dimensions"][name]["score"],
              "Label": score_text(r["dimensions"][name]["score"])}
             for r in programs for name in DIMENSION_NAMES]
    st.vega_lite_chart(pd.DataFrame(cells), {
        "height": 60 * len(programs),
        "encoding": {
            "x": {"field": "Dimension", "type": "nominal", "sort": DIMENSION_NAMES,
                  "axis": {"labelAngle": -25, "labelLimit": 250, "labelOverlap": False, "title": None}},
            "y": {"field": "Program", "type": "nominal", "title": None,
                  "sort": [r["program"] for r in programs]},
        },
        "layer": [
            # Light gray under every cell, so n/a cells read as "not measured", not as a low score.
            {"mark": {"type": "rect", "stroke": "white", "color": "#d9d9d9"}},
            {"mark": {"type": "rect", "stroke": "white"},
             "encoding": {
                 "color": {"field": "Score", "type": "quantitative",
                           "scale": {"domain": [0, 100], "scheme": "blues"},
                           "legend": {"title": "Score"}},
                 "tooltip": [{"field": "Program"}, {"field": "Dimension"}, {"field": "Label", "title": "Score"}]}},
            {"mark": {"type": "text", "fontSize": 13},
             "encoding": {
                 "text": {"field": "Label"},
                 "color": {"condition": {"test": "datum.Score > 60", "value": "white"}, "value": "black"}}},
        ],
    }, width="stretch")
    st.caption("Gray (n/a) cells could not be assessed from C2M2 metadata.")

    st.subheader("Top 3 AI-readiness gaps across programs")
    for i, gap in enumerate(data["top_gaps"], 1):
        per_program = "; ".join(f"{p['program']}: {p['passed']:,} of {p['total']:,} ({p['score']}%)"
                                for p in gap["programs"])
        st.markdown(f"**{i}. {gap['description']}** — {gap['average_score']}% coverage on average.  \n"
                    f"{gap['why_it_matters']}  \n*{per_program}*")


def render_program(r: dict):
    """One program's report card (also used for an uploaded datapackage)."""
    col1, col2, col3 = st.columns(3)
    col1.metric("Overall score", score_text(r["overall_score"]))
    col2.metric("Dimensions assessed", f"{r['dimensions_assessed']} of {len(DIMENSION_NAMES)}")
    col3.metric("Files", f"{r['record_counts'].get('file', 0):,}")
    st.markdown(f"**Release:** `{r['release']}`, released {r.get('release_date') or 'unknown'}  \n"
                f"**Records (project / subject / biosample / file):** {records_text(r)}  \n"
                f"**Namespace(s):** `{r['namespace']}`")
    if rc.is_old_release(r.get("release_date", "")):
        st.warning(f"This is an older release and may not reflect {r['program']}'s current metadata.")

    for name in DIMENSION_NAMES:
        dim = r["dimensions"][name]
        st.subheader(f"{name}: {score_text(dim['score'])}" + ("" if dim["score"] == rc.NOT_ASSESSABLE else " / 100"))
        if dim["score"] == rc.NOT_ASSESSABLE:
            st.markdown(f"**Not assessable.** {dim['reason']}")
        elif dim.get("observation"):
            st.markdown(f"**Observation:** {dim['observation']}")
        if dim["checks"]:
            st.dataframe(pd.DataFrame([{
                "Check": c["id"],
                "What it measures": c["description"],
                "Result": (f"{c['passed']:,} of {c['total']:,}" if c["score"] is not None else "nothing to measure"),
                "Score": c["score"] if c["score"] is not None else "skipped",
                "Detail": c["detail"],
            } for c in dim["checks"]]), hide_index=True, width="stretch")
            with st.expander("Why these checks matter for AI"):
                for c in dim["checks"]:
                    st.markdown(f"- **{c['id']}**: {c.get('why_it_matters', rc.WHY_IT_MATTERS.get(c['id'], ''))}")
        for info in dim.get("info", []):
            st.caption(f"Info (not scored): {info}")
        for note in rc.notes(dim):
            st.caption(f"Note: {note}")

    st.subheader("Data quality notes (not scored)")
    if r["data_quality_notes"]:
        for n in r["data_quality_notes"]:
            st.markdown(f"- {n}")
    else:
        st.markdown("None found by the checks we run.")


def program_report():
    data = load_comparison()
    st.title("Program report card")
    st.caption(rc.DISCLAIMER)
    by_name = {r["program"]: r for r in data["programs"]}
    uploaded = st.session_state.get("uploaded_result")
    if uploaded:
        by_name[f"{uploaded['program']} (your upload)"] = uploaded
    choice = st.selectbox("Program", list(by_name))
    render_program(by_name[choice])


def methods():
    st.title("Methods")
    st.caption(rc.DISCLAIMER)
    st.markdown(
        "Each dimension is made of one or more checks. Each check is a fraction (records that pass / "
        "records checked), shown as 0-100 with its raw numbers. A check with nothing to measure is skipped, "
        "not scored 0; a dimension with no measurable checks is *not assessable*. A dimension's score is the "
        "average of its checks, and the overall score is the average of the assessable dimensions. Info lines "
        "and data quality notes are reported but never scored."
    )
    st.dataframe(pd.DataFrame(rc.METHODS, columns=["Dimension", "Check", "What it measures", "C2M2 table: column(s)"]),
                 hide_index=True, width="stretch")
    st.markdown(
        "**Rules worth knowing**\n"
        "- *Persistent identifiers:* one scheme list applies to both `persistent_id` and `access_url`: "
        "DOI, identifiers.org, ARK, `drs://`, Handle, PURL. Plain `s3://` and ordinary `https://` URLs don't "
        "count. identifiers.org compact identifiers are recognised for prefixes confirmed in the registry "
        f"({', '.join(f'`{p}`' for p in rc.IDENTIFIERS_ORG_PREFIXES)}).\n"
        "- *Sex and age* are checked only for single-organism subjects (human or animal); cell lines, "
        "synthetic entities, microbiomes etc. are excluded and reported. NIH's Sex as a Biological Variable "
        "policy applies to human and animal studies alike.\n"
        "- *Labels* count if they come from the datapackage's own term tables, or were read off the CFDE portal.\n"
        "- A real datapackage is one program's submission and is scored as a whole."
    )
    st.subheader("Relation to CFDE's c2m2-assessment")
    st.markdown(
        f"CFDE already has an assessment tool for C2M2 datapackages, [nih-cfde/c2m2-assessment]"
        f"({C2M2_ASSESSMENT_URL}) (by Daniel J. B. Clarke). It runs FAIRshake-style rubrics and reports, per "
        "metric, a value with its numerator and denominator; its default rubric measures FAIRness, including "
        "live-testing a sample of access URLs, persistent identifiers on files, and about 34 coverage metrics. "
        "This tool does not replace it and does not use its code. It asks a different question: the Bridge2AI "
        "paper argues that FAIR conformance alone is not sufficient for AI-readiness and defines seven "
        "dimensions, of which FAIRness is one. This checker is a first attempt at simple proxies for all seven "
        "from C2M2 metadata alone; its FAIRness checks are deliberately coarser than c2m2-assessment's."
    )
    st.subheader("Limitations")
    st.markdown(
        "- Simplified proxies, not an official implementation of the Bridge2AI criteria; they measure "
        "metadata coverage only.\n"
        "- One release per program; releases older than two years are flagged.\n"
        "- Some gaps come from the C2M2 schema rather than the programs (no consent or governance fields).\n"
        "- Persistent identifiers are recognised by scheme; nothing is resolved over the network.\n"
        "- Every check and dimension is weighted equally, so overall scores are a rough summary.\n"
        "- Labels are checked for presence, not correctness."
    )
    st.caption(f"Citation: {rc.CITATION}.")


def upload():
    st.title("Check your own datapackage")
    st.caption(rc.DISCLAIMER)
    st.markdown(
        f"Upload a C2M2 datapackage as a `.zip` (up to **{MAX_UPLOAD_MB} MB** zipped and "
        f"**{MAX_UNZIPPED_MB} MB** unzipped) and the checker will run on it here. The file is unpacked into a "
        "temporary folder, scored, and deleted; nothing is stored. Larger packages can be scored locally with "
        "`python3 src/readiness_checker.py --data-dir <folder>`."
    )
    file = st.file_uploader("C2M2 datapackage (.zip)", type="zip")
    if file is None:
        return
    if file.size > MAX_UPLOAD_MB * 1024 * 1024:
        st.error(f"This file is {file.size / 1e6:.0f} MB; the limit here is {MAX_UPLOAD_MB} MB.")
        return
    try:
        with zipfile.ZipFile(file) as zf:
            unzipped = sum(info.file_size for info in zf.infolist())
            if unzipped > MAX_UNZIPPED_MB * 1024 * 1024:
                st.error(f"Unzipped, this package is {unzipped / 1e6:.0f} MB; the limit here is "
                         f"{MAX_UNZIPPED_MB} MB. Please run the checker locally instead.")
                return
            with tempfile.TemporaryDirectory() as tmp, st.spinner("Scoring the datapackage..."):
                zf.extractall(tmp)  # zipfile strips absolute paths and '..' from member names
                data_dir = rc.find_package_dir(Path(tmp))
                if data_dir is None:
                    st.error("No project.tsv was found in this zip, so it doesn't look like a C2M2 datapackage.")
                    return
                result = rc.score_real_package(data_dir, Path(tmp), release=(file.name, "unknown"))
    except zipfile.BadZipFile:
        st.error("This file could not be read as a zip archive.")
        return
    except Exception as e:  # show the problem rather than a stack trace
        st.error(f"The checker could not score this package: {type(e).__name__}: {e}")
        return
    st.session_state["uploaded_result"] = result
    st.success(f"Scored {file.name}. It also appears in the Program report card dropdown for this session.")
    render_program(result)


# ---------------------------------------------------------------------------

st.set_page_config(page_title="CFDE AI-Readiness Report Card", layout="wide")
page = st.navigation([
    st.Page(home, title="Home", default=True),
    st.Page(comparison, title="Comparison", url_path="comparison"),
    st.Page(program_report, title="Program report card", url_path="program"),
    st.Page(methods, title="Methods", url_path="methods"),
    st.Page(upload, title="Check your own datapackage", url_path="upload"),
])
page.run()
