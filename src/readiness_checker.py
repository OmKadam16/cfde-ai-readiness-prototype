"""
readiness_checker.py

AI-Readiness Checker: grades CFDE programs' C2M2 metadata on the seven
AI-readiness dimensions from:

    Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv
    2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for
    Biomedical Data: Bridge2AI Recommendations")

    Dimensions: FAIRness, Provenance, Characterization, Pre-model
    Explainability, Ethics, Sustainability, Computability.

IMPORTANT: this is NOT an official implementation of the Bridge2AI
recommendations. The paper describes each dimension qualitatively; the
checks below are our own simplified, measurable proxies for them, chosen
because they can be computed directly from C2M2 tables. A high score here
means "the fields we can check are filled in", not "certified AI-ready".

How scoring works (deliberately simple):
  - Each dimension is made of one or more checks.
  - Each check is a fraction: (records that pass) / (records checked),
    shown as 0-100. The raw numbers are always kept alongside the score.
  - If a check has nothing to measure (e.g. a program has no files), it is
    skipped -- it is NOT counted as 0.
  - A dimension's score is the plain average of its non-skipped checks.
    If every check was skipped, the dimension is "NOT ASSESSABLE".
  - A program's overall score is the plain average of its assessable
    dimensions (the report says how many of the 7 that was).
  - Some things are reported but never scored: "info" lines (e.g. disease
    associations) and per-program "data quality notes" (e.g. stray
    whitespace in term IDs).

What counts as one "program":
  - data/ (our hand-collected sample) mixes 5 programs in one package, so
    it is split by id_namespace.
  - A real datapackage (--data-dir) is one DCC's submission, so it is
    scored as a single program. It is NOT split by namespace: SPARC, for
    example, puts files, subjects and projects in different namespaces.

Usage:
    python3 readiness_checker.py                  # the hand-collected sample
    python3 readiness_checker.py --program sparc  # one program from the sample
    python3 readiness_checker.py --include-demo   # also score demo:proj1
    python3 readiness_checker.py --data-dir ../data_real/sennet  # a real datapackage
    python3 readiness_checker.py --compare        # every package in ../data_real/

Writes to ../output/: readiness_report.md + readiness_scores.json for the
sample; readiness_report_<name>.md + readiness_scores_<name>.json for a real
package; and readiness_comparison.md for --compare.
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from c2m2_to_croissant import CORE_TABLES, ONTOLOGY_COLUMNS, build_croissant
from term_labels import TERM_LABELS
from validate_croissant import validate as validate_croissant

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_REAL_DIR = Path(__file__).parent.parent / "data_real"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
# Where each data_real/ package came from (tracked in git; data_real/ is not).
RELEASES_FILE = Path(__file__).parent.parent / "releases.tsv"
OLD_RELEASE_YEARS = 2
OLD_RELEASE_FLAG = "older release - may not reflect current metadata"

DEMO_NAMESPACE = "demo:proj1"
NOT_ASSESSABLE = "NOT ASSESSABLE"
LOW_SCORE_THRESHOLD = 70

# Values that mean "someone filled the cell but we still don't know".
# They count as missing, not as data.
NON_ANSWERS = {"not reported", "unknown", "na", "n/a", "none"}

SAMPLE_BANNER = ("DEMO ON A SMALL HAND-COLLECTED SAMPLE - these scores reflect this sample, "
                 "not the full program's metadata.")

# Attached to the ontology checks. The CFDE portal shows labels ("Breast"),
# but a real C2M2 submission stores the term ID ("UBERON:0000310") -- so
# free text in a hand-transcribed sample may be our artifact, not the DCC's.
ONTOLOGY_TRANSCRIPTION_NOTE = (
    "The CFDE portal UI displays human-readable labels, while real C2M2 submissions store "
    "ontology IDs, so if this data was hand-transcribed from the portal, free-text values may "
    "be a transcription artifact rather than a gap in the program's own metadata.")

# An ontology term ID looks like PREFIX:ID, e.g. "UBERON:0000955" or
# "EDAM:format_3752". Free text like "Breast" or "urinary bladder" does not.
ONTOLOGY_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*:[A-Za-z0-9_]+$")

CITATION = ('Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. '
            'doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: '
            'Bridge2AI Recommendations")')

DISCLAIMER = "These are simplified proxy measures for exploration, not an official evaluation."

# ONE list of persistent-identifier schemes, used for both persistent_id and
# access_url. Plain s3:// and ordinary https:// URLs are locations, not
# persistent identifiers, so they don't count.
PERSISTENT_SCHEMES = {
    "DOI": r"https?://(dx\.)?doi\.org/|doi:",
    "identifiers.org": r"https?://identifiers\.org/",
    "ARK": r"ark:/|https?://n2t\.net/ark:",
    "DRS": r"drs://",
    "Handle": r"hdl:|https?://hdl\.handle\.net/",
    "PURL": r"https?://purl\.org/",
}
# identifiers.org also resolves compact identifiers ("prefix:accession") for
# registered prefixes. Recognising every registered prefix would need a
# network lookup, so this lists the ones we have confirmed in the registry
# (registry.api.identifiers.org, checked 2026-09-29).
IDENTIFIERS_ORG_PREFIXES = {
    "sparc.drs": "MIR:00001102",  # used in SPARC's file.persistent_id
}
PERSISTENT_ID_PATTERN = re.compile(
    "^(" + "|".join(list(PERSISTENT_SCHEMES.values())
                    + [re.escape(p) + ":" for p in IDENTIFIERS_ORG_PREFIXES]) + ")",
    re.IGNORECASE)

# C2M2 subject.granularity values (C2M2 specification, nih-cfde/c2m2,
# draft-C2M2_specification/README.md). Sex and age are only checked for
# single organisms -- humans and animals alike.
SINGLE_ORGANISM = "cfde_subject_granularity:0"
GRANULARITY_NAMES = {
    "cfde_subject_granularity:0": "single-organism",
    "cfde_subject_granularity:1": "symbiont-system",
    "cfde_subject_granularity:2": "host-pathogen-system",
    "cfde_subject_granularity:3": "microbiome",
    "cfde_subject_granularity:4": "cell-line",
    "cfde_subject_granularity:5": "synthetic",
}

# One sentence per check: why closing this gap helps AI use of the data.
WHY_IT_MATTERS = {
    "subject_sex": ("Recording sex lets model developers check whether results hold for both sexes; "
                    "NIH's Sex as a Biological Variable policy applies to human and animal studies alike."),
    "subject_age": "Recording age lets model developers check whether results differ across age groups, such as children and adults.",
    "biosample_anatomy": "Recording anatomy lets a model keep tissue-specific signals apart instead of mixing samples from different tissues.",
    "persistent_ids": "Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.",
    "ontology_ids": "Ontology term IDs let values be matched reliably across programs ('Breast' in one, 'UBERON:0000310' in another), so a model sees one concept as one feature.",
    "creation_time": "Timestamps help identify which version of the data a model used and make batch or time effects detectable.",
    "file_checksums": "Checksums let users verify that a downloaded file is exactly the one a model was trained on.",
    "labeled_terms": "Human-readable labels let reviewers sanity-check what a model's input features mean.",
    "file_format": "A declared file format lets pipelines parse each file without guessing.",
    "croissant_valid": "Valid Croissant metadata lets ML tools discover and load the dataset automatically.",
    "file_locatable": "A persistent ID or access URL on each file keeps it findable for the models and benchmarks that depend on it.",
}


# ---------------------------------------------------------------------------
# Loading and grouping
# ---------------------------------------------------------------------------

# Tables whose rows belong to a program.
PER_PROGRAM_TABLES = CORE_TABLES + ["biosample_disease", "subject_disease", "biosample_from_subject"]
RECORD_TABLES = ["project", "subject", "biosample", "file"]
DISEASE_TABLES = ["biosample_disease", "subject_disease"]

# The minimum columns needed to split a table by program. A table missing
# from the datapackage is treated as an empty table with these columns.
MIN_COLUMNS = {
    "project": ["id_namespace", "local_id"],
    "subject": ["id_namespace", "local_id"],
    "biosample": ["id_namespace", "local_id"],
    "file": ["id_namespace", "local_id"],
    "biosample_disease": ["biosample_id_namespace", "biosample_local_id", "disease"],
    "subject_disease": ["subject_id_namespace", "subject_local_id", "disease"],
    "biosample_from_subject": ["biosample_id_namespace", "biosample_local_id",
                               "subject_id_namespace", "subject_local_id"],
}

# C2M2 term tables: real datapackages ship one row (id, name, ...) for every
# ontology term ID they use, so the term's label comes with the submission.
# Our hand-collected sample has none of these.
TERM_TABLES = ["anatomy", "biofluid", "sample_prep_method", "assay_type", "analysis_type",
               "file_format", "data_type", "disease"]


def read_tsv(path: Path) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    return pd.read_csv(path, sep="\t", dtype=str)


def load_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load only the tables the checker uses. Missing tables don't crash:
    per-program tables become empty, lookup tables are just absent."""
    tables = {}
    for name in PER_PROGRAM_TABLES:
        df = read_tsv(data_dir / f"{name}.tsv")
        tables[name] = df if df is not None else pd.DataFrame(columns=MIN_COLUMNS[name])

    # Term IDs are kept exactly as written (no stripping) so that data
    # quality notes can report stray whitespace.
    term_frames = [df[["id", "name"]].assign(table=name) for name in TERM_TABLES
                   if (df := read_tsv(data_dir / f"{name}.tsv")) is not None and {"id", "name"} <= set(df.columns)]
    tables["term_names"] = (pd.concat(term_frames, ignore_index=True) if term_frames
                            else pd.DataFrame(columns=["id", "name", "table"]))

    for lookup in ("id_namespace", "dcc"):
        df = read_tsv(data_dir / f"{lookup}.tsv")
        if df is not None:
            tables[lookup] = df
    return tables


def namespace_column(df: pd.DataFrame) -> str:
    """Core tables use id_namespace; association tables use <entity>_id_namespace
    for the first entity listed (e.g. biosample_disease -> biosample_id_namespace)."""
    if "id_namespace" in df.columns:
        return "id_namespace"
    return next(c for c in df.columns if c.endswith("_id_namespace"))


def split_by_namespace(tables: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.DataFrame]]:
    """For a package that mixes several programs (our sample): one program per namespace."""
    namespaces = sorted(tables["project"]["id_namespace"].dropna().unique())
    programs = {}
    for ns in namespaces:
        prog = {name: tables[name][tables[name][namespace_column(tables[name])] == ns].reset_index(drop=True)
                for name in PER_PROGRAM_TABLES}
        prog["term_names"] = tables["term_names"]  # shared lookup, not split
        programs[ns] = prog
    return programs


def short_name(namespace: str) -> str:
    return namespace.split(":", 1)[-1]


def namespace_labels(tables: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Readable name per namespace: the abbreviation from id_namespace.tsv if the
    datapackage has one, else the part after 'cfde:' (e.g. 'sparc')."""
    labels = {}
    if "id_namespace" in tables and "abbreviation" in tables["id_namespace"].columns:
        for _, row in tables["id_namespace"].iterrows():
            if is_filled(row["abbreviation"]):
                labels[row["id"]] = row["abbreviation"]
    return {ns: labels.get(ns, short_name(ns)) for ns in tables["project"]["id_namespace"].dropna().unique()}


def package_label(tables: dict[str, pd.DataFrame], data_dir: Path) -> str:
    """Name for a whole real datapackage: the DCC abbreviation from dcc.tsv, else the folder name."""
    dcc = tables.get("dcc")
    if dcc is not None and "dcc_abbreviation" in dcc.columns and len(dcc) and is_filled(dcc["dcc_abbreviation"].iloc[0]):
        return dcc["dcc_abbreviation"].iloc[0].strip()
    return data_dir.name


def package_namespaces(tables: dict[str, pd.DataFrame]) -> str:
    namespaces = set()
    for name in RECORD_TABLES:
        if "id_namespace" in tables[name].columns:
            namespaces |= set(tables[name]["id_namespace"].dropna().unique())
    return ", ".join(sorted(namespaces))


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def is_filled(value) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip()
    return text != "" and text.lower() not in NON_ANSWERS


def filled_mask(series: pd.Series) -> pd.Series:
    """Vectorised is_filled, so million-row file tables stay fast."""
    text = series.astype("string").str.strip()
    return (text.notna() & (text != "") & ~text.str.lower().isin(NON_ANSWERS)).fillna(False).astype(bool)


def column_mask(df: pd.DataFrame, column: str) -> pd.Series:
    """filled_mask for a column; a column absent from the table counts as all-empty."""
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return filled_mask(df[column])


def count_filled(df: pd.DataFrame, column: str) -> int:
    return int(column_mask(df, column).sum())


def check(check_id: str, description: str, passed: int, total: int, detail: str,
          note: str = "", raw: dict | None = None) -> dict:
    """One measured check. If total == 0 there is nothing to measure, so it is skipped."""
    result = {
        "id": check_id,
        "description": description,
        "passed": int(passed),
        "total": int(total),
        "score": round(100 * passed / total) if total else None,
        "detail": detail,
    }
    if raw:
        result["raw"] = {k: int(v) for k, v in raw.items()}
    if note:
        result["note"] = note
    return result


def absent_column_note(frames: dict[str, pd.DataFrame], column: str) -> str:
    """Say so when a table has rows but no such column at all (counted as missing)."""
    lacking = [f"{name}.tsv" for name, df in frames.items() if len(df) and column not in df.columns]
    return f"no {column} column in {', '.join(lacking)}" if lacking else ""


def examples(values, limit: int = 8) -> str:
    values = list(values)
    shown = ", ".join(repr(v) for v in values[:limit])
    return shown + (f", ... ({len(values) - limit} more)" if len(values) > limit else "")


def missing_detail(passed: int, total: int, noun: str, what: str, note: str = "") -> str:
    text = f"{total - passed:,} of {total:,} {noun} have no {what} recorded"
    return text + (f" ({note})" if note else "")


def dimension(checks: list[dict], not_assessable_reason: str = "", info: list[str] | None = None) -> dict:
    measured = [c for c in checks if c["score"] is not None]
    result = {"score": NOT_ASSESSABLE, "reason": not_assessable_reason, "checks": checks}
    if measured:
        result.update(score=round(sum(c["score"] for c in measured) / len(measured)), reason="")
    if info:
        result["info"] = info
    return result


def ontology_cells(prog: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Every filled cell in an ontology-coded column (plus disease), exactly as written.
    Columns: table, column, raw."""
    parts = []
    sources = [(t, sorted(ONTOLOGY_COLUMNS & set(prog[t].columns))) for t in CORE_TABLES]
    sources += [(t, ["disease"] if "disease" in prog[t].columns else []) for t in DISEASE_TABLES]
    for table_name, columns in sources:
        df = prog[table_name]
        for col in columns:
            values = df.loc[filled_mask(df[col]), col].astype(str)
            parts.append(pd.DataFrame({"table": table_name, "column": col, "raw": values.values}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["table", "column", "raw"])


def is_term_id(values: pd.Series) -> pd.Series:
    return values.str.match(ONTOLOGY_ID_PATTERN).fillna(False).astype(bool)


def is_persistent(df: pd.DataFrame, column: str) -> pd.Series:
    """Cells whose value starts with a scheme from the persistent-identifier list."""
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    matches = df[column].astype("string").str.strip().str.match(PERSISTENT_ID_PATTERN)
    return matches.fillna(False).astype(bool)


def persistent_id_masks(prog: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.Series], pd.Series]:
    """(persistent_id holds a persistent identifier, per record table) and
    (file access_url holds one). The same scheme list applies to both."""
    in_field = {t: is_persistent(prog[t], "persistent_id") for t in RECORD_TABLES}
    return in_field, is_persistent(prog["file"], "access_url")


def value_scheme(value: str) -> str:
    """'https://www.ncbi.nlm.nih.gov/...' -> 'https://www.ncbi.nlm.nih.gov'; 's3://bucket/..' -> 's3:'."""
    match = re.match(r"^(https?://[^/]+|[A-Za-z][\w.+-]*:)", value.strip())
    return match.group(1) if match else "(no scheme)"


def organism_subjects(subjects: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Subjects whose sex and age are checked: single organisms (human or animal).
    Cell lines, microbiomes, synthetic entities etc. are excluded and reported.
    A subject with no granularity recorded is kept (C2M2 requires the field;
    only our hand-collected sample leaves it blank)."""
    if "granularity" not in subjects.columns:
        return subjects, (["subject.tsv has no granularity column, so all subjects are treated as single organisms"]
                          if len(subjects) else [])
    granularity = subjects["granularity"].astype("string").str.strip()
    blank = ~filled_mask(subjects["granularity"])
    keep = (granularity == SINGLE_ORGANISM).fillna(False).astype(bool) | blank
    info = []
    excluded = granularity[~keep].value_counts()
    if len(excluded):
        parts = [f"{n:,} {GRANULARITY_NAMES.get(g, g)}" for g, n in excluded.items()]
        info.append(f"{' and '.join(parts)} subjects excluded from sex/age checks "
                    "(these checks apply to single-organism subjects, human or animal)")
    if blank.any():
        info.append(f"{int(blank.sum()):,} subject(s) have no granularity recorded and are counted as single organisms")
    return subjects[keep], info


# ---------------------------------------------------------------------------
# The seven dimensions
# ---------------------------------------------------------------------------

def score_fairness(prog):
    records = {t: prog[t] for t in RECORD_TABLES}
    total = sum(len(df) for df in records.values())

    # A record has a persistent ID if persistent_id, or (files only, since only
    # file.tsv has access_url) access_url, holds a value with a scheme from
    # PERSISTENT_SCHEMES. Other filled persistent_id values are not counted
    # and are reported as a data quality note.
    in_field, in_access_url = persistent_id_masks(prog)
    n_field = sum(int(m.sum()) for m in in_field.values())
    n_access_only = int((in_access_url & ~in_field["file"]).sum())
    n_other_scheme = sum(int((column_mask(df, "persistent_id") & ~in_field[t]).sum()) for t, df in records.items())
    with_pid = n_field + n_access_only
    pid_detail = (f"{total - with_pid:,} of {total:,} records have no persistent identifier recorded "
                  f"({n_field:,} have one in persistent_id; {n_access_only:,} more files have one only in access_url; "
                  f"{n_other_scheme:,} persistent_id values use a non-persistent scheme and are not counted)")
    absent = absent_column_note(records, "persistent_id")
    if absent:
        pid_detail += f" ({absent})"

    cells = ontology_cells(prog)
    values = cells["raw"].str.strip()
    coded = is_term_id(values)
    free_text = sorted(set(values[~coded]))
    onto_detail = f"{int(coded.sum()):,} of {len(values):,} ontology-field values use a term ID"
    if free_text:
        onto_detail += "; free text found: " + examples(free_text)

    return dimension([
        check("persistent_ids", "Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files)",
              with_pid, total, pid_detail,
              raw={"persistent_id_field": n_field, "access_url_only": n_access_only,
                   "access_url_persistent_total": int(in_access_url.sum()),
                   "persistent_id_non_persistent_scheme": n_other_scheme}),
        check("ontology_ids", "Ontology-coded field values that are real term IDs (PREFIX:ID), not free text",
              int(coded.sum()), len(values), onto_detail,
              note=ONTOLOGY_TRANSCRIPTION_NOTE if free_text else ""),
    ], "No records found for this program.")


def score_provenance(prog):
    records = {t: prog[t] for t in RECORD_TABLES}
    total = sum(len(df) for df in records.values())
    with_time = sum(count_filled(df, "creation_time") for df in records.values())

    files = prog["file"]
    checksum_cols = [c for c in ("sha256", "md5") if c in files.columns]
    has_checksum = pd.Series(False, index=files.index)
    for col in checksum_cols:
        has_checksum |= filled_mask(files[col])
    with_checksum = int(has_checksum.sum())
    note = "" if checksum_cols else "file.tsv has no sha256 or md5 column at all"

    return dimension([
        check("creation_time", "Records (project/subject/biosample/file) with a creation_time",
              with_time, total, missing_detail(with_time, total, "records", "creation_time",
                                               absent_column_note(records, "creation_time"))),
        check("file_checksums", "Files with a sha256 or md5 checksum",
              with_checksum, len(files), missing_detail(with_checksum, len(files), "files", "checksum", note),
              raw={f"with_{c}": int(filled_mask(files[c]).sum()) for c in checksum_cols}),
    ], "No records found for this program.")


def score_characterization(prog):
    subjects, granularity_info = organism_subjects(prog["subject"])
    biosamples = prog["biosample"]
    n_sex = count_filled(subjects, "sex")
    n_anat = count_filled(biosamples, "anatomy")

    # C2M2 records age in two places: subject.age_at_enrollment and
    # biosample_from_subject.age_at_sampling. A subject has an age if either
    # is filled (e.g. Kids First uses only age_at_sampling).
    has_enrollment_age = column_mask(subjects, "age_at_enrollment")
    links = prog["biosample_from_subject"]
    sampled = links[column_mask(links, "age_at_sampling")]
    sampled_keys = set(zip(sampled["subject_id_namespace"], sampled["subject_local_id"]))
    subject_keys = pd.Series(list(zip(subjects["id_namespace"], subjects["local_id"])), index=subjects.index, dtype=object)
    has_sampling_age = subject_keys.map(lambda key: key in sampled_keys).astype(bool) if len(subjects) else has_enrollment_age
    n_enrollment = int(has_enrollment_age.sum())
    n_sampling_only = int((has_sampling_age & ~has_enrollment_age).sum())
    n_age = n_enrollment + n_sampling_only
    age_detail = missing_detail(n_age, len(subjects), "subjects", "age") + (
        f" ({n_enrollment:,} have age_at_enrollment; {n_sampling_only:,} more have age_at_sampling on a linked biosample)")

    # Disease links are reported, not scored: not every program studies a disease.
    n_links = {t: len(prog[t]) for t in DISEASE_TABLES}
    n_total = sum(n_links.values())
    per_table = ", ".join(f"{n:,} in {t}.tsv" for t, n in n_links.items())
    disease_info = (f"{n_total:,} disease associations in this release ({per_table}) - not scored, "
                    "since not every program studies a disease")

    return dimension([
        check("subject_sex", "Single-organism subjects with sex recorded",
              n_sex, len(subjects), missing_detail(n_sex, len(subjects), "subjects", "sex",
                                                   absent_column_note({"subject": subjects}, "sex"))),
        check("subject_age", "Single-organism subjects with an age recorded "
              "(age_at_enrollment, or age_at_sampling on a linked biosample)",
              n_age, len(subjects), age_detail,
              raw={"age_at_enrollment": n_enrollment, "age_at_sampling_only": n_sampling_only}),
        check("biosample_anatomy", "Biosamples with anatomy recorded",
              n_anat, len(biosamples), missing_detail(n_anat, len(biosamples), "biosamples", "anatomy",
                                                      absent_column_note({"biosample": biosamples}, "anatomy"))),
    ], "No single-organism subjects or biosamples found for this program.",
        info=granularity_info + [disease_info])


def score_explainability(prog):
    # Distinct term IDs actually used. A term counts as labeled if a label
    # comes from an authoritative source:
    #   "datapackage" = the program's own C2M2 term tables (anatomy.tsv etc.),
    #                   i.e. the label shipped with the official submission
    #   "portal"      = read directly off a CFDE portal page (term_labels.py)
    # "inferred" and "placeholder" labels from term_labels.py are reported but
    # earn no credit.
    values = ontology_cells(prog)["raw"].str.strip()
    coded = is_term_id(values)
    terms = sorted(set(values[coded]))
    has_free_text = bool((~coded).any())
    names = prog["term_names"]
    # Strip IDs: real term tables can carry stray whitespace (reported
    # separately as a data quality note).
    datapackage_labels = set(names.loc[filled_mask(names["name"]), "id"].str.strip())

    by_source = {"datapackage": [], "portal": [], "inferred": [], "placeholder": [], "no label": []}
    for term in terms:
        if term in datapackage_labels:
            source = "datapackage"
        else:
            source = TERM_LABELS.get(term, {}).get("source", "no label")
        by_source.setdefault(source, []).append(term)

    labeled = len(by_source["datapackage"]) + len(by_source["portal"])
    parts = [f"{len(v)} {k} ({examples(v, 5)})" for k, v in by_source.items() if v]
    detail = f"{labeled} of {len(terms)} term IDs have a label (datapackage term table or portal)"
    if parts:
        detail += "; breakdown: " + "; ".join(parts)

    return dimension([
        check("labeled_terms", "Distinct ontology term IDs with a human-readable label "
              "(from the package's own term tables, or portal-sourced in term_labels.py)",
              labeled, len(terms), detail,
              note=ONTOLOGY_TRANSCRIPTION_NOTE if has_free_text else ""),
    ], "This program uses no ontology term IDs -- its ontology fields hold free text "
       "(see FAIRness), so there are no codes to look up labels for. " + ONTOLOGY_TRANSCRIPTION_NOTE)


def score_ethics(prog):
    return {
        "score": NOT_ASSESSABLE,
        "reason": ("This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, "
                   "data use limitations, IRB approval, or governance, so ethics cannot be measured "
                   "from C2M2 metadata. Each program's own data use documentation is the place to look."),
        "checks": [],
    }


def score_sustainability(prog):
    files = prog["file"]
    locatable = column_mask(files, "persistent_id") | column_mask(files, "access_url")
    n_locatable = int(locatable.sum())
    return dimension([
        check("file_locatable", "Files with a persistent_id or access_url",
              n_locatable, len(files),
              missing_detail(n_locatable, len(files), "files", "persistent_id or access_url")),
    ], "This program has no file records, so there is nothing whose long-term access can be checked.")


def score_computability(prog):
    files = prog["file"]
    n_format = count_filled(files, "file_format")

    # Build Croissant for just this program's records and run the same
    # structural validator used on the full output.
    errors = validate_croissant(build_croissant({t: prog[t] for t in CORE_TABLES}))
    croissant_detail = ("Croissant generated for this program's records and passed validate_croissant.py"
                        if not errors else f"Croissant failed validation: {'; '.join(errors)}")

    # With no files, the Croissant check alone would give a misleading 100:
    # there is no actual data for a model to compute on.
    if len(files) == 0:
        return {"score": NOT_ASSESSABLE,
                "reason": "This program has no file records, so there is no data for a model to load "
                          f"(for reference: {croissant_detail[0].lower() + croissant_detail[1:]}).",
                "checks": []}

    return dimension([
        check("file_format", "Files with a file_format",
              n_format, len(files), missing_detail(n_format, len(files), "files", "file_format")),
        check("croissant_valid", "Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0)",
              int(not errors), 1, croissant_detail),
    ])


DIMENSIONS = [
    ("FAIRness", score_fairness),
    ("Provenance", score_provenance),
    ("Characterization", score_characterization),
    ("Pre-model Explainability", score_explainability),
    ("Ethics", score_ethics),
    ("Sustainability", score_sustainability),
    ("Computability", score_computability),
]

# Every check behind each dimension, and where in C2M2 it reads from.
# Used for documentation (the web app's Methods page).
METHODS = [
    ("FAIRness", "persistent_ids",
     "Records with a persistent identifier (DOI, identifiers.org, ARK, DRS, Handle, PURL)",
     "persistent_id in project, subject, biosample, file; file.access_url"),
    ("FAIRness", "ontology_ids",
     "Ontology-coded values that are term IDs (PREFIX:ID) rather than free text",
     "biosample: anatomy, biofluid, sample_prep_method; file: file_format, compression_format, "
     "data_type, assay_type, analysis_type; biosample_disease / subject_disease: disease"),
    ("Provenance", "creation_time", "Records with a creation time",
     "creation_time in project, subject, biosample, file"),
    ("Provenance", "file_checksums", "Files with a sha256 or md5 checksum", "file: sha256, md5"),
    ("Characterization", "subject_sex", "Single-organism subjects (human or animal) with sex recorded",
     "subject: sex, granularity"),
    ("Characterization", "subject_age",
     "Single-organism subjects with an age recorded",
     "subject: age_at_enrollment, granularity; biosample_from_subject: age_at_sampling"),
    ("Characterization", "biosample_anatomy", "Biosamples with anatomy recorded", "biosample: anatomy"),
    ("Characterization", "(info, not scored)", "Disease associations; subjects excluded from sex/age checks",
     "biosample_disease, subject_disease; subject: granularity"),
    ("Pre-model Explainability", "labeled_terms",
     "Distinct term IDs used in the data that have a human-readable label",
     "the ontology-coded columns above; the package's own term tables (anatomy.tsv, assay_type.tsv, "
     "file_format.tsv, ...: name)"),
    ("Ethics", "(none)", "Not assessable: the C2M2 schema has no consent, data-use, IRB or governance fields",
     "-"),
    ("Sustainability", "file_locatable", "Files with a persistent_id or an access_url",
     "file: persistent_id, access_url"),
    ("Computability", "file_format", "Files with a declared file format", "file: file_format"),
    ("Computability", "croissant_valid",
     "Croissant metadata generated from the records and passing validate_croissant.py",
     "project, subject, biosample, file (all columns)"),
]


# ---------------------------------------------------------------------------
# Data quality notes (reported, never scored)
# ---------------------------------------------------------------------------

def data_quality_notes(prog: dict[str, pd.DataFrame]) -> list[str]:
    found = []
    cells = ontology_cells(prog)
    stripped = cells["raw"].str.strip()
    used_terms = set(stripped[is_term_id(stripped)])
    names = prog["term_names"]
    term_ids = names["id"].astype(str)

    # 1. Term-table IDs with stray whitespace, for terms this program uses.
    padded = names[term_ids != term_ids.str.strip()]
    for table, group in padded.groupby("table"):
        affected = [i for i in group["id"] if i.strip() in used_terms]
        if affected:
            found.append(f"{table}.tsv: {len(affected)} term ID(s) have leading/trailing whitespace "
                         f"({examples(affected)}). As written they are not valid term IDs, and any tool that "
                         "trims whitespace on one side of a join but not the other will fail to match them. "
                         "The labels exist; this checker trims both sides before matching.")

    # 2. Ontology values in the data with stray whitespace.
    padded_cells = cells[cells["raw"] != stripped]
    if len(padded_cells):
        where = padded_cells.groupby(["table", "column"]).size()
        found.append(f"{len(padded_cells):,} ontology-field value(s) in the data have leading/trailing whitespace: "
                     + ", ".join(f"{t}.tsv {c}: {n:,}" for (t, c), n in where.items())
                     + f" (e.g. {examples(padded_cells['raw'].unique(), 3)})")

    # 3. Term IDs used in the data with no row in the package's own term tables
    #    (only checked if the package ships term tables at all).
    if len(names):
        unlisted = sorted(used_terms - set(term_ids.str.strip()))
        if unlisted:
            found.append(f"{len(unlisted)} term ID(s) used in the data have no row in the package's term tables "
                         f"({', '.join(t + '.tsv' for t in sorted(set(names['table'])))}): {examples(unlisted)}")

    in_field, in_access_url = persistent_id_masks(prog)

    # 4. persistent_id filled with a value outside the persistent-identifier scheme list.
    for table in RECORD_TABLES:
        df = prog[table]
        other = column_mask(df, "persistent_id") & ~in_field[table]
        if other.any():
            schemes = df.loc[other, "persistent_id"].astype(str).map(value_scheme).value_counts()
            found.append(f"{table}.tsv: {int(other.sum()):,} persistent_id value(s) use a scheme that is not on the "
                         "persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are "
                         "not counted as persistent IDs. Schemes seen: "
                         + ", ".join(f"{s} ({n:,})" for s, n in schemes.head(5).items())
                         + (f", ... ({len(schemes) - 5} more)" if len(schemes) > 5 else "") + ".")

    # 5. Persistent identifiers stored in access_url instead of persistent_id.
    only_in_access_url = in_access_url & ~in_field["file"]
    if only_in_access_url.any():
        urls = prog["file"].loc[only_in_access_url, "access_url"]
        found.append("Persistent IDs present, but stored in access_url instead of the C2M2 persistent_id field "
                     f"({int(only_in_access_url.sum()):,} of {len(prog['file']):,} files; "
                     f"{urls.nunique():,} distinct identifiers, e.g. {examples(urls.unique(), 2)}).")
    return found


def score_program(namespace: str, label: str, prog: dict[str, pd.DataFrame],
                  release: str = "", release_date: str = "") -> dict:
    dims = {name: fn(prog) for name, fn in DIMENSIONS}
    # Store the plain-English text with the numbers, so the JSON output is
    # self-contained (the web app reads only the JSON).
    for dim in dims.values():
        for c in dim["checks"]:
            c["why_it_matters"] = WHY_IT_MATTERS[c["id"]]
        if dim["score"] != NOT_ASSESSABLE and dim["score"] < LOW_SCORE_THRESHOLD:
            dim["observation"] = low_score_sentence(dim)
    numeric = [d["score"] for d in dims.values() if d["score"] != NOT_ASSESSABLE]
    return {
        "program": label,
        "namespace": namespace,
        "release": release,
        "release_date": release_date,
        "old_release": is_old_release(release_date),
        "record_counts": {t: len(prog[t]) for t in CORE_TABLES},
        "overall_score": round(sum(numeric) / len(numeric)) if numeric else NOT_ASSESSABLE,
        "dimensions_assessed": len(numeric),
        "dimensions": dims,
        "data_quality_notes": data_quality_notes(prog),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def weakest_check(dim: dict) -> dict:
    measured = [c for c in dim["checks"] if c["score"] is not None]
    return min(measured, key=lambda c: c["score"])


def low_score_sentence(dim: dict) -> str:
    """One sentence: what's missing (raw numbers from the weakest check) and why it matters."""
    c = weakest_check(dim)
    return f"{c['detail']}. {WHY_IT_MATTERS[c['id']]}"


def format_score(score) -> str:
    return f"{score}/100" if score != NOT_ASSESSABLE else NOT_ASSESSABLE


def counts_text(r: dict) -> str:
    return ", ".join(f"{n} {t}" for t, n in r["record_counts"].items())


def counts_cell(r: dict) -> str:
    rc = r["record_counts"]
    return " / ".join(f"{rc.get(t, 0):,}" for t in RECORD_TABLES)


def basis_text(dim: dict) -> str:
    """The raw passed/total behind a dimension score, e.g. '[persistent_ids 5/9, ontology_ids 1/5]'."""
    measured = [c for c in dim["checks"] if c["score"] is not None]
    return "[" + ", ".join(f"{c['id']} {c['passed']}/{c['total']}" for c in measured) + "]" if measured else ""


def notes(dim: dict) -> list[str]:
    found = []
    for c in dim["checks"]:
        if c.get("note") and c["note"] not in found and c["note"] not in dim["reason"]:
            found.append(c["note"])
    return found


def score_cells(r: dict) -> list[str]:
    return [str(r["dimensions"][name]["score"]).replace(NOT_ASSESSABLE, "n/a") for name, _ in DIMENSIONS]


def render_report(results: list[dict], banner: str, data_dir: Path) -> str:
    lines = [
        "# CFDE AI-Readiness Report",
        "",
        f"> **{banner}**",
        "",
        f"*{DISCLAIMER}*",
        "",
        "Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in",
        f"{CITATION}.",
        "They describe what the C2M2 metadata records, not the quality of the program's data or work.",
        f"Every score is computed from the C2M2 records in `{data_dir}`; see `src/readiness_checker.py`.",
        "",
        "## Summary",
        "",
        "| Program | Records (project / subject / biosample / file) | Overall | "
        + " | ".join(name for name, _ in DIMENSIONS) + " |",
        "|---|---|---|" + "---|" * len(DIMENSIONS),
    ]
    for r in results:
        lines.append(f"| {r['program']} | {counts_cell(r)} | {r['overall_score']} | " + " | ".join(score_cells(r)) + " |")
    lines += ["", "n/a = NOT ASSESSABLE (reason given in the program section).", ""]

    for r in results:
        lines += [
            f"## {r['program']} (`{r['namespace']}`)",
            "",
            f"**Overall: {format_score(r['overall_score'])}** "
            f"(average of the {r['dimensions_assessed']} of {len(DIMENSIONS)} dimensions that could be assessed)  ",
            f"Records: {counts_text(r)}" + (f"  \nRelease: {release_text(r)}" if r["release"] else ""),
            "",
        ]
        for name, _ in DIMENSIONS:
            dim = r["dimensions"][name]
            lines.append(f"### {name}: {format_score(dim['score'])} {basis_text(dim)}".rstrip())
            if dim["score"] == NOT_ASSESSABLE:
                lines.append(f"- Why not assessable: {dim['reason']}")
            elif dim["score"] < LOW_SCORE_THRESHOLD:
                lines.append(f"- **Observation:** {low_score_sentence(dim)}")
            for c in dim["checks"]:
                shown = f"{c['score']}" if c["score"] is not None else "skipped (nothing to measure)"
                lines.append(f"- `{c['id']}` = {shown} -- {c['description']}: {c['detail']}")
            for info in dim.get("info", []):
                lines.append(f"- *Info (not scored):* {info}")
            for note in notes(dim):
                lines.append(f"- *Note:* {note}")
            lines.append("")
        lines.append("### Data quality notes (not scored)")
        lines += [f"- {n}" for n in r["data_quality_notes"]] or ["- None found by the checks we run."]
        lines.append("")
    return "\n".join(lines)


def render_terminal(results: list[dict], banner: str) -> str:
    width = max(len(name) for name, _ in DIMENSIONS)
    out = ["!" * 72, banner, "!" * 72]
    for r in results:
        out += ["", "=" * 72,
                f"{r['program']} ({r['namespace']})   OVERALL {format_score(r['overall_score'])}   "
                f"({r['dimensions_assessed']}/{len(DIMENSIONS)} dimensions assessed)",
                f"records: {counts_text(r)}"]
        if r["release"]:
            out.append(f"release: {release_text(r)}")
        out.append("=" * 72)
        for name, _ in DIMENSIONS:
            dim = r["dimensions"][name]
            out.append(f"  {name:<{width}}  {format_score(dim['score']):<14} {basis_text(dim)}".rstrip())
            if dim["score"] == NOT_ASSESSABLE:
                out.append(f"      -> {dim['reason']}")
            elif dim["score"] < LOW_SCORE_THRESHOLD:
                out.append(f"      -> {low_score_sentence(dim)}")
            for info in dim.get("info", []):
                out.append(f"      info: {info}")
            for note in notes(dim):
                out.append(f"      note: {note}")
        if r["data_quality_notes"]:
            out.append("  Data quality notes (not scored):")
            out += [f"    - {n}" for n in r["data_quality_notes"]]
    return "\n".join(out)


def top_gap_data(results: list[dict], n: int = 3) -> list[dict]:
    """The n checks with the lowest average score across programs.
    Only checks measured for at least two programs, so one program's gap isn't called a pattern."""
    by_check = {}
    for r in results:
        for dim in r["dimensions"].values():
            for c in dim["checks"]:
                if c["score"] is not None:
                    by_check.setdefault(c["id"], []).append((r["program"], c))
    ranked = sorted((sum(c["score"] for _, c in entries) / len(entries), check_id, entries)
                    for check_id, entries in by_check.items() if len(entries) >= 2)
    return [{
        "check": check_id,
        "description": entries[0][1]["description"],
        "average_score": round(avg),
        "programs": [{"program": p, "passed": c["passed"], "total": c["total"], "score": c["score"]}
                     for p, c in entries],
        "why_it_matters": WHY_IT_MATTERS[check_id],
    } for avg, check_id, entries in ranked[:n]]


def top_gaps(results: list[dict], n: int = 3) -> list[str]:
    """top_gap_data in plain English."""
    gaps = []
    for g in top_gap_data(results, n):
        per_program = "; ".join(f"{p['program']} {p['passed']:,}/{p['total']:,} ({p['score']}%)" for p in g["programs"])
        gaps.append(f"**{g['description']}**: {g['average_score']}% coverage on average across "
                    f"{len(g['programs'])} programs ({per_program}). {g['why_it_matters']}")
    return gaps


def render_comparison(results: list[dict]) -> str:
    lines = [
        "# CFDE AI-Readiness Comparison",
        "",
        f"**{DISCLAIMER}**",
        "",
        "Each row is one program's current C2M2 release, downloaded from the CFDE Workbench "
        "(cfde.cloud/info/dcc/<program>). Scores are our own simplified proxies for the 7 AI-readiness "
        f"dimensions in {CITATION}. They describe what the C2M2 metadata records -- not the quality of the "
        "underlying data or of each program's work -- and are meant to point at concrete, fixable gaps.",
        "",
        "| Program | Release file | Release date | Records (project / subject / biosample / file) | Overall | "
        + " | ".join(name for name, _ in DIMENSIONS) + " |",
        "|---|---|---|---|---|" + "---|" * len(DIMENSIONS),
    ]
    for r in results:
        date = r["release_date"] + (f" ({OLD_RELEASE_FLAG})" if is_old_release(r["release_date"]) else "")
        lines.append(f"| {r['program']} | `{r['release']}` | {date} | {counts_cell(r)} | {r['overall_score']} | "
                     + " | ".join(score_cells(r)) + " |")
    lines += [
        "",
        "n/a = NOT ASSESSABLE. Ethics is n/a for every program because of the C2M2 schema, not the programs: "
        "C2M2 has no consent or governance fields. Overall = average of the dimensions that could be assessed. "
        f"Releases older than {OLD_RELEASE_YEARS} years are flagged: {OLD_RELEASE_FLAG}.",
        "",
        "## Top 3 AI-readiness gaps across programs",
        "",
    ]
    lines += [f"{i}. {gap}" for i, gap in enumerate(top_gaps(results), 1)]
    lines += ["", "## Data quality notes (not scored)", ""]
    for r in results:
        lines.append(f"**{r['program']}**")
        lines += [f"- {n}" for n in r["data_quality_notes"]] or ["- None found by the checks we run."]
        lines.append("")
    lines.append("Full per-program detail: `output/readiness_report_<program>.md`.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def find_package_dir(folder: Path) -> Path | None:
    """The shallowest folder under `folder` holding a project.tsv (HMP's zip nests it in merged/data/)."""
    hits = sorted(folder.rglob("project.tsv"), key=lambda p: len(p.parts))
    return hits[0].parent if hits else None


def release_info(folder: Path) -> tuple[str, str]:
    """(release file, release date) for a data_real/ folder, from releases.tsv;
    falls back to the zip's name and 'unknown' for folders not listed there."""
    releases = read_tsv(RELEASES_FILE)
    if releases is not None:
        row = releases[releases["folder"] == folder.name]
        if len(row):
            return row["release_file"].iloc[0], row["release_date"].iloc[0]
    zips = sorted(z.name for z in folder.glob("*.zip"))
    return (", ".join(zips) if zips else "(no zip found)"), "unknown"


def is_old_release(release_date: str) -> bool:
    try:
        released = date.fromisoformat(release_date)
    except ValueError:
        return False
    return (date.today() - released).days > OLD_RELEASE_YEARS * 365


def release_text(r: dict) -> str:
    text = f"`{r['release']}` ({r['release_date']})"
    return text + (f" - {OLD_RELEASE_FLAG}" if is_old_release(r["release_date"]) else "")


def score_real_package(data_dir: Path, folder: Path, release: tuple[str, str] | None = None) -> dict:
    """A real datapackage is one DCC's submission: score all of it as one program.
    `release` is (file name, date); by default it is looked up in releases.tsv."""
    tables = load_tables(data_dir)
    prog = {name: tables[name] for name in PER_PROGRAM_TABLES}
    prog["term_names"] = tables["term_names"]
    release, release_date = release or release_info(folder)
    return score_program(package_namespaces(tables), package_label(tables, data_dir), prog, release, release_date)


def write_outputs(results: list[dict], banner: str, data_dir: Path, suffix: str) -> list[Path]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / f"readiness_report{suffix}.md"
    scores_path = OUTPUT_DIR / f"readiness_scores{suffix}.json"
    report_path.write_text(render_report(results, banner, data_dir) + "\n")
    with open(scores_path, "w") as f:
        json.dump({"source": CITATION,
                   "disclaimer": DISCLAIMER,
                   "banner": banner,
                   "data_dir": str(data_dir),
                   "programs": results}, f, indent=2)
    return [report_path, scores_path]


def real_banner(folder_name: str) -> str:
    return (f"FULL C2M2 DATAPACKAGE from data_real/{folder_name}/ - these scores reflect this one "
            "submitted release, measured with our simplified proxies.")


def run_compare(root: Path) -> None:
    results = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        package_dir = find_package_dir(folder)
        if package_dir is None:
            print(f"skipping {folder.name}/: no project.tsv found (not unzipped?)")
            continue
        print(f"scoring {folder.name}/ ...", flush=True)
        r = score_real_package(package_dir, folder)
        results.append(r)
        write_outputs([r], real_banner(folder.name), package_dir, f"_{folder.name}")

    comparison = render_comparison(results)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "readiness_comparison.md").write_text(comparison + "\n")
    # The same results as one JSON file: this is what the web app (app.py) reads.
    with open(OUTPUT_DIR / "readiness_comparison.json", "w") as f:
        json.dump({"source": CITATION,
                   "disclaimer": DISCLAIMER,
                   "generated": date.today().isoformat(),
                   "old_release_years": OLD_RELEASE_YEARS,
                   "old_release_flag": OLD_RELEASE_FLAG,
                   "programs": results,
                   "top_gaps": top_gap_data(results)}, f, indent=2)
    print()
    print(comparison)
    print()
    print(f"Wrote {OUTPUT_DIR / 'readiness_comparison.md'}, readiness_comparison.json, "
          "and one readiness_report_<program>.md per program")


def main():
    parser = argparse.ArgumentParser(description="Score CFDE programs on 7 AI-readiness dimensions.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR,
                        help="folder holding a C2M2 datapackage (default: data/, the hand-collected sample)")
    parser.add_argument("--program", help="with the sample: score one program, e.g. 'sparc' or 'cfde:sparc'")
    parser.add_argument("--include-demo", action="store_true",
                        help=f"with the sample: also score the synthetic demo cluster ({DEMO_NAMESPACE})")
    parser.add_argument("--compare", action="store_true",
                        help="score every datapackage folder in data_real/ and write output/readiness_comparison.md")
    args = parser.parse_args()

    print("CFDE AI-Readiness Checker (simplified proxies for the Bridge2AI dimensions; not official)")
    if args.compare:
        run_compare(DATA_REAL_DIR)
        return

    folder = args.data_dir.resolve()
    data_dir = find_package_dir(folder)
    if data_dir is None:
        raise SystemExit(f"No project.tsv in or under {folder} -- is this a C2M2 datapackage folder?")

    if data_dir == DATA_DIR.resolve():
        tables = load_tables(data_dir)
        labels = namespace_labels(tables)
        programs = split_by_namespace(tables)
        if not args.include_demo:
            programs.pop(DEMO_NAMESPACE, None)
        if args.program:
            wanted = args.program.lower()
            programs = {ns: p for ns, p in programs.items()
                        if wanted in (ns.lower(), short_name(ns).lower(), labels[ns].lower())}
            if not programs:
                raise SystemExit(f"Unknown program '{args.program}'. Available: {', '.join(labels.values())}"
                                 + ("" if args.include_demo else " (proj1 needs --include-demo)"))
        results = [score_program(ns, labels[ns], prog) for ns, prog in programs.items()]
        banner, suffix = SAMPLE_BANNER, ""
    else:
        results = [score_real_package(data_dir, folder)]
        banner, suffix = real_banner(folder.name), f"_{folder.name}"

    print(render_terminal(results, banner))
    print()
    for path in write_outputs(results, banner, data_dir, suffix):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
