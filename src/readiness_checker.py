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
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import numpy as np
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
# Data quality note threshold: mention ages of exactly 0 when they are at least
# this share of the recorded ages.
ZERO_AGE_SHARE = 0.05
# Named rule AGE_ZERO_PLACEHOLDER: in a program where at least ZERO_AGE_SHARE of all
# recorded ages (age_at_enrollment and age_at_sampling) are exactly 0 AND the median
# non-zero age is at least ADULT_MEDIAN_AGE, age 0 is treated as "not recorded" (a
# placeholder for unknown) everywhere age is counted. Decided once per program; its
# projects follow the program. Pediatric programs (low median age) are never affected,
# since an age of 0 (under one year) is plausible there.
ADULT_MEDIAN_AGE = 18
AGE_COLUMNS = [("subject", "age_at_enrollment"), ("biosample_from_subject", "age_at_sampling")]
# CFDE sex vocabulary (nih-cfde/c2m2, internal_CFDE_CV_reference_tables/subject_sex.tsv).
INDETERMINATE_SEX = "cfde_subject_sex:0"
KNOWN_SEX = ["cfde_subject_sex:1", "cfde_subject_sex:2"]  # Female, Male: what the finder counts as "sex"
SEX_NAMES = {
    "cfde_subject_sex:0": "Indeterminate",
    "cfde_subject_sex:1": "Female",
    "cfde_subject_sex:2": "Male",
    "cfde_subject_sex:3": "Intersex",
    "cfde_subject_sex:4": "Transsexual (MTF)",
    "cfde_subject_sex:5": "Transsexual (FTM)",
}
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
PER_PROGRAM_TABLES = CORE_TABLES + ["biosample_disease", "subject_disease", "biosample_from_subject",
                                    "file_describes_biosample", "file_describes_subject"]
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
    "file_describes_biosample": ["file_id_namespace", "file_local_id",
                                 "biosample_id_namespace", "biosample_local_id"],
    "file_describes_subject": ["file_id_namespace", "file_local_id",
                               "subject_id_namespace", "subject_local_id"],
}

# C2M2 term tables: real datapackages ship one row (id, name, ...) for every
# ontology term ID they use, so the term's label comes with the submission.
# Our hand-collected sample has none of these.
TERM_TABLES = ["anatomy", "biofluid", "sample_prep_method", "assay_type", "analysis_type",
               "file_format", "data_type", "disease"]
# Further term tables used only to label values in field discovery (not scored).
LABEL_TABLES = ["gene", "substance", "compound", "phenotype", "ncbi_taxonomy", "protein"]


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
    # Other term tables (gene, substance, phenotype, ncbi_taxonomy, ...) label discovered field values.
    extra = [df[["id", "name"]].assign(table=path.stem) for path in sorted(data_dir.glob("*.tsv"))
             if path.stem in LABEL_TABLES and path.stat().st_size
             and {"id", "name"} <= set((df := pd.read_csv(path, sep="\t", dtype=str)).columns)]
    tables["value_labels"] = (pd.concat(extra, ignore_index=True) if extra
                              else pd.DataFrame(columns=["id", "name", "table"]))
    tables["term_names"] = (pd.concat(term_frames, ignore_index=True) if term_frames
                            else pd.DataFrame(columns=["id", "name", "table"]))

    for lookup in ("id_namespace", "dcc"):
        df = read_tsv(data_dir / f"{lookup}.tsv")
        if df is not None:
            tables[lookup] = df
    # Every <entity>_<x>.tsv that links records to values, for field discovery.
    tables["assoc"] = find_association_tables(data_dir)
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
        prog["value_labels"] = tables["value_labels"]
        prog["assoc"] = {name: df[df[namespace_column(df)] == ns].reset_index(drop=True)
                         for name, df in tables["assoc"].items()}
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


def age_zero_rule(prog: dict) -> dict:
    """Apply AGE_ZERO_PLACEHOLDER to a program: are its ages of exactly 0 likely placeholders?"""
    values = [pd.to_numeric(prog[t].loc[column_mask(prog[t], c), c], errors="coerce")
              for t, c in AGE_COLUMNS if c in prog[t].columns]
    ages = pd.concat(values) if values else pd.Series(dtype=float)
    zeros = int((ages == 0).sum())
    nonzero = ages[(ages != 0) & ages.notna()]
    median = float(nonzero.median()) if len(nonzero) else None
    applies = bool(zeros and zeros >= ZERO_AGE_SHARE * len(ages) and median is not None and median >= ADULT_MEDIAN_AGE)
    return {"applies": applies, "zeros": zeros, "recorded": int(len(ages)), "median_nonzero_age": median}


def age_mask(df: pd.DataFrame, column: str, prog: dict) -> pd.Series:
    """column_mask for an age column; under AGE_ZERO_PLACEHOLDER an age of exactly 0 counts as not recorded."""
    mask = column_mask(df, column)
    if column in df.columns and prog.get("age_rule", {}).get("applies"):
        mask &= ~(pd.to_numeric(df[column], errors="coerce") == 0).fillna(False)
    return mask


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


def organism_mask(subjects: pd.DataFrame) -> pd.Series:
    """True for single-organism subjects (or subjects with no granularity recorded)."""
    if "granularity" not in subjects.columns:
        return pd.Series(True, index=subjects.index)
    granularity = subjects["granularity"].astype("string").str.strip()
    return (granularity == SINGLE_ORGANISM).fillna(False).astype(bool) | ~filled_mask(subjects["granularity"])


def organism_subjects(subjects: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Subjects whose sex and age are checked: single organisms (human or animal).
    Cell lines, microbiomes, synthetic entities etc. are excluded and reported.
    A subject with no granularity recorded is kept (C2M2 requires the field;
    only our hand-collected sample leaves it blank)."""
    if "granularity" not in subjects.columns:
        return subjects, (["subject.tsv has no granularity column, so all subjects are treated as single organisms"]
                          if len(subjects) else [])
    keep = organism_mask(subjects)
    granularity = subjects["granularity"].astype("string").str.strip()
    blank = ~filled_mask(subjects["granularity"])
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
    has_enrollment_age = age_mask(subjects, "age_at_enrollment", prog)
    links = prog["biosample_from_subject"]
    sampled = links[age_mask(links, "age_at_sampling", prog)]
    sampled_keys = set(zip(sampled["subject_id_namespace"], sampled["subject_local_id"]))
    subject_keys = pd.Series(list(zip(subjects["id_namespace"], subjects["local_id"])), index=subjects.index, dtype=object)
    has_sampling_age = subject_keys.map(lambda key: key in sampled_keys).astype(bool) if len(subjects) else has_enrollment_age
    n_enrollment = int(has_enrollment_age.sum())
    n_sampling_only = int((has_sampling_age & ~has_enrollment_age).sum())
    n_age = n_enrollment + n_sampling_only
    age_detail = missing_detail(n_age, len(subjects), "subjects", "age") + (
        f" ({n_enrollment:,} have age_at_enrollment; {n_sampling_only:,} more have age_at_sampling on a linked biosample)")
    if prog.get("age_rule", {}).get("applies"):
        age_detail += "; ages of exactly 0 are treated as not recorded (likely placeholders, see Methods)"

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


def score_computability(prog, croissant: dict | None = None):
    """`croissant`: an already-computed croissant_valid check to reuse (projects
    inherit it from their package) instead of building Croissant again."""
    files = prog["file"]
    n_format = count_filled(files, "file_format")

    # Build Croissant for just this program's records and run the same
    # structural validator used on the full output.
    if croissant is not None:
        errors = [] if croissant["passed"] else [croissant["detail"]]
        croissant_detail = croissant["detail"]
    else:
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
# Field coverage and requirement combinations (reported, never scored)
# ---------------------------------------------------------------------------

# Field discovery. Instead of a fixed list, every column that holds information
# about a subject, biosample or file is found in whatever tables the package
# has: the entity tables themselves (subject.tsv, biosample.tsv, file.tsv) and
# every association table named <entity>_<something>.tsv (subject_race,
# subject_phenotype, biosample_gene, subject_role_taxonomy, ...). A field is
# available when at least one record has a value for it.
#
# A few C2M2 attributes are recorded in more than one place; they are merged
# into one field so a single checkbox means "has it, wherever it is recorded":
#   age        subject.age_at_enrollment, biosample_from_subject.age_at_sampling
#   disease    subject_disease.disease, biosample_disease.disease
#   checksum   file.md5, file.sha256
# Two fields are about each record itself, at whatever level is counted:
#   persistent_id  the record's own persistent_id (files: also a persistent-identifier access_url)
#   creation_time  the record's own creation_time
#
# Counting is exact. For each level (subject, biosample, file) every record
# gets a bitmask with one bit per field it has (after following links, below),
# and we store how many records share each bitmask. "How many records have all
# of X, Y, Z" is then a sum over the stored bitmasks -- for any combination,
# with no estimation and no raw data needed.
ENTITIES = ["subject", "biosample", "file"]
QUALIFIER_COLUMNS = {"association_type", "role_id"}  # describe a link, not the record
IDENTIFIER_COLUMNS = {"filename"}                     # names/identifiers, not information
MERGED_FIELDS = {
    "age": [("subject", "age_at_enrollment"), ("biosample_from_subject", "age_at_sampling")],
    "disease": [("subject_disease", "disease"), ("biosample_disease", "disease")],
    "checksum": [("file", "md5"), ("file", "sha256")],
}
PER_RECORD_FIELDS = {"persistent_id": "persistent_id", "creation_time": "creation_time"}
ORGANISM_FIELDS = {"sex", "age"}      # counted only for single-organism subjects
SINGLE_ORGANISM_BIT = "_single_organism"  # hidden bit: sets the denominator for sex/age
FIELD_GROUPS = ["Demographics", "Clinical/disease", "Biological sample", "Molecular", "File/technical"]
# Plain-English names and groups for known fields; anything else gets a name
# built from its column and a group from its entity.
KNOWN_FIELDS = {
    "sex": ("Sex", "Demographics"),
    "age": ("Age", "Demographics"),
    "subject.ethnicity": ("Ethnicity", "Demographics"),
    "subject_race.race": ("Race", "Demographics"),
    "subject.granularity": ("Subject type", "Demographics"),
    "subject_role_taxonomy.taxonomy_id": ("Organism", "Demographics"),
    "disease": ("Disease", "Clinical/disease"),
    "subject_phenotype.phenotype": ("Phenotype", "Clinical/disease"),
    "subject_substance.substance": ("Substance (subject)", "Clinical/disease"),
    "biosample.anatomy": ("Anatomy", "Biological sample"),
    "biosample.biofluid": ("Biofluid", "Biological sample"),
    "biosample.sample_prep_method": ("Sample prep", "Biological sample"),
    "biosample_gene.gene": ("Gene (sample)", "Molecular"),
    "biosample_substance.substance": ("Substance (sample)", "Molecular"),
    "file.assay_type": ("Assay type", "Molecular"),
    "file.analysis_type": ("Analysis type", "Molecular"),
    "file.data_type": ("Data type", "Molecular"),
    "file.file_format": ("File format", "File/technical"),
    "file.compression_format": ("Compression", "File/technical"),
    "file.mime_type": ("MIME type", "File/technical"),
    "checksum": ("Checksums", "File/technical"),
    "file.size_in_bytes": ("File size", "File/technical"),
    "file.uncompressed_size_in_bytes": ("Uncompressed size", "File/technical"),
    "file.access_url": ("Access URL", "File/technical"),
    "file.dbgap_study_id": ("dbGaP study ID", "File/technical"),
    "persistent_id": ("Persistent IDs", "File/technical"),
    "creation_time": ("Creation time", "File/technical"),
}
DEFAULT_GROUP = {"subject": "Demographics", "biosample": "Biological sample", "file": "File/technical"}
# CFDE controlled vocabularies (nih-cfde/c2m2 internal_CFDE_CV_reference_tables), for value labels.
CFDE_VOCABULARY = {
    **SEX_NAMES,
    **{k: v.replace("-", " ") for k, v in GRANULARITY_NAMES.items()},
    "cfde_subject_race:0": "American Indian or Alaskan Native", "cfde_subject_race:1": "Asian or Pacific Islander",
    "cfde_subject_race:2": "Black", "cfde_subject_race:3": "White", "cfde_subject_race:4": "Other",
    "cfde_subject_ethnicity:0": "Hispanic or Latino", "cfde_subject_ethnicity:1": "not Hispanic or Latino",
}
TOP_VALUES = 5

COMBINATION_RULES = (
    "Fields are discovered from the tables each datapackage actually has. A record meets a need if it, or a "
    "record it is directly linked to, has a value. Sex means Male or Female recorded; Indeterminate is not "
    "counted, since a model can't use it (the Characterization score still counts any recorded sex value). "
    "Sex and age count only for single-organism subjects (human or animal). "
    "Subjects: their own fields, plus biosample fields recorded on any of their biosamples. "
    "Biosamples: their own fields; a field that can be recorded on subjects (e.g. sex, age, disease) also "
    "counts if their subject has it, including values recorded on the subject's other biosamples. "
    "Files: the fields of the biosamples and subjects they describe (file_describes_biosample, "
    "file_describes_subject), plus their own file fields; file fields (e.g. checksums, file format) can only be "
    "counted per file. Persistent IDs and creation time are always the record's own. Records are linked only "
    "through these C2M2 link tables, not through collections.")


def is_key_column(column: str) -> bool:
    return column in ("id_namespace", "local_id") or column.endswith(("_id_namespace", "_local_id"))


def association_table_columns(data_dir: Path) -> dict[str, list[str]]:
    """Every <entity>_<something>.tsv that links an entity to a value (e.g. subject_race.race), with the
    columns to read (the entity's keys and the value columns). Read from headers only.
    Link-only tables (file_describes_*, *_in_collection) have no value column and are skipped."""
    found = {}
    for path in sorted(data_dir.glob("*.tsv")):
        entity = next((e for e in ENTITIES if path.stem.startswith(e + "_")), None)
        if entity is None or path.stat().st_size == 0:
            continue
        header = list(pd.read_csv(path, sep="\t", nrows=0).columns)
        keys = [f"{entity}_id_namespace", f"{entity}_local_id"]
        values = [c for c in header if not is_key_column(c) and c not in QUALIFIER_COLUMNS]
        if set(keys) <= set(header) and values:
            found[path.stem] = keys + values
    return found


def find_association_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(data_dir / f"{name}.tsv", sep="\t", dtype=str, usecols=columns)
            for name, columns in association_table_columns(data_dir).items()}


def field_sources(prog: dict) -> dict[str, dict]:
    """Every candidate field in this package: id -> {label, group, entity, sources: [(table, column)], kind}."""
    raw = []  # (table, column, entity)
    for entity in ENTITIES:
        for column in prog[entity].columns:
            if not is_key_column(column) and column not in IDENTIFIER_COLUMNS and column not in PER_RECORD_FIELDS:
                raw.append((entity, column, entity))
    for table, df in prog.get("assoc", {}).items():
        entity = next(e for e in ENTITIES if table.startswith(e + "_"))
        for column in df.columns:
            if not is_key_column(column) and column not in QUALIFIER_COLUMNS:
                raw.append((table, column, entity))

    merged_source = {src: fid for fid, sources in MERGED_FIELDS.items() for src in sources}
    fields = {}
    for table, column, entity in raw:
        fid = "sex" if (table, column) == ("subject", "sex") else merged_source.get((table, column), f"{table}.{column}")
        f = fields.setdefault(fid, {"id": fid, "entities": [], "sources": [], "kind": "linked"})
        f["sources"].append([table, column])
        if entity not in f["entities"]:
            f["entities"].append(entity)
    for fid, column in PER_RECORD_FIELDS.items():
        sources = [[e, column] for e in ENTITIES if column in prog[e].columns]
        if fid == "persistent_id" and "access_url" in prog["file"].columns:
            sources.append(["file", "access_url"])
        if sources:
            fields[fid] = {"id": fid, "entities": [s[0] for s in sources if s[1] == column], "sources": sources,
                           "kind": "per_record"}
    for fid, f in fields.items():
        entity = f["entities"][0]
        default = (f["sources"][0][1].replace("_", " ").capitalize()
                   + (f" ({entity})" if f["sources"][0][0] != entity else ""), DEFAULT_GROUP[entity])
        f["label"], f["group"] = KNOWN_FIELDS.get(fid, default)
        f["organism"] = fid in ORGANISM_FIELDS
        # Fields recorded only on files can only be counted per file.
        f["file_only"] = f["kind"] == "linked" and f["entities"] == ["file"]
        # Fields with no subject-level source (e.g. anatomy) are counted per biosample or file.
        f["no_subject_level"] = f["kind"] == "linked" and "subject" not in f["entities"] and not f["file_only"]
    return fields


def record_index(df: pd.DataFrame) -> pd.MultiIndex:
    """(id_namespace, local_id) of each row, used to find rows by their C2M2 key."""
    return pd.MultiIndex.from_arrays([df["id_namespace"].astype(str), df["local_id"].astype(str)])


def positions(index: pd.MultiIndex, links: pd.DataFrame, entity: str) -> np.ndarray:
    """Row number in `index` of each link row's <entity>_id_namespace/<entity>_local_id (-1 if absent)."""
    if links.empty or len(index) == 0:
        return np.full(len(links), -1)
    keys = pd.MultiIndex.from_arrays([links[f"{entity}_id_namespace"].astype(str),
                                      links[f"{entity}_local_id"].astype(str)])
    return index.get_indexer(keys)


def any_linked(n_from: int, from_pos: np.ndarray, to_pos: np.ndarray, to_flag: np.ndarray) -> np.ndarray:
    """For each 'from' record: does ANY record it links to have the flag?"""
    ok = (from_pos >= 0) & (to_pos >= 0)
    hits = np.bincount(from_pos[ok], weights=to_flag[to_pos[ok]].astype(float), minlength=n_from)
    return hits > 0


def value_mask(df: pd.DataFrame, column: str, fid: str, prog: dict | None = None) -> np.ndarray:
    """Which rows have a usable value. For sex, only Male or Female counts; for age, see AGE_ZERO_PLACEHOLDER."""
    if fid == "age":
        return age_mask(df, column, prog or {}).to_numpy()
    if fid == "sex":
        values = df[column].astype("string").str.strip() if column in df.columns else pd.Series(pd.NA, index=df.index)
        return values.isin(KNOWN_SEX).fillna(False).to_numpy(dtype=bool)
    return column_mask(df, column).to_numpy()


def field_bitmasks(prog: dict, fields: dict | None = None) -> dict:
    """Per level, how many records share each combination of fields (as bitmasks), plus the field list.
    Also: how many records have sex recorded only as Indeterminate."""
    fields = fields if fields is not None else field_sources(prog)
    # Duplicate keys (should not occur) keep their first row.
    subjects, biosamples, files = (prog[t].drop_duplicates(["id_namespace", "local_id"]).reset_index(drop=True)
                                   for t in ENTITIES)
    s_idx, b_idx, f_idx = record_index(subjects), record_index(biosamples), record_index(files)
    n = {"subject": len(subjects), "biosample": len(biosamples), "file": len(files)}
    frames = {"subject": subjects, "biosample": biosamples, "file": files}

    bfs = prog["biosample_from_subject"]
    bs_b, bs_s = positions(b_idx, bfs, "biosample"), positions(s_idx, bfs, "subject")
    fdb, fds = prog["file_describes_biosample"], prog["file_describes_subject"]
    fb_f, fb_b = positions(f_idx, fdb, "file"), positions(b_idx, fdb, "biosample")
    fs_f, fs_s = positions(f_idx, fds, "file"), positions(s_idx, fds, "subject")
    s_org = organism_mask(subjects).to_numpy()
    b_org = any_linked(n["biosample"], bs_b, bs_s, s_org)
    index_of = {"subject": s_idx, "biosample": b_idx, "file": f_idx}

    def own(fid: str, f: dict, entity: str) -> np.ndarray:
        """Records of `entity` that have this field themselves (any of its sources on that entity)."""
        flag = np.zeros(n[entity], dtype=bool)
        for table, column in f["sources"]:
            if table == entity:
                if fid == "persistent_id":  # persistent_id, and access_url on files
                    flag |= is_persistent(frames[entity], column).to_numpy()
                else:
                    flag |= value_mask(frames[entity], column, fid, prog)
            elif table == "biosample_from_subject" and entity == "biosample":
                # a value on the biosample-subject link (age_at_sampling) belongs to the biosample
                has = (age_mask(bfs, column, prog) if fid == "age" else column_mask(bfs, column)).to_numpy()
                flag[bs_b[(bs_b >= 0) & has]] = True
            elif table in prog.get("assoc", {}) and table.startswith(entity + "_"):
                df = prog["assoc"][table]
                rows = column_mask(df, column).to_numpy()
                pos = positions(index_of[entity], df, entity)
                flag[pos[(pos >= 0) & rows]] = True
        if f["organism"]:
            flag &= s_org if entity == "subject" else b_org if entity == "biosample" else flag
        return flag

    levels = {lv: {} for lv in ENTITIES}
    for fid, f in fields.items():
        if f["kind"] == "per_record":
            for lv in ENTITIES:
                levels[lv][fid] = own(fid, f, lv)
            continue
        s_own = own(fid, f, "subject") if "subject" in f["entities"] else np.zeros(n["subject"], bool)
        b_own = own(fid, f, "biosample") if "biosample" in f["entities"] else np.zeros(n["biosample"], bool)
        f_own = own(fid, f, "file") if "file" in f["entities"] else np.zeros(n["file"], bool)
        subject_level = s_own | any_linked(n["subject"], bs_s, bs_b, b_own)
        if f["organism"]:
            subject_level &= s_org
        biosample_level = b_own | (any_linked(n["biosample"], bs_b, bs_s, subject_level)
                                   if "subject" in f["entities"] else False)
        file_level = (f_own | any_linked(n["file"], fb_f, fb_b, biosample_level)
                      | (any_linked(n["file"], fs_f, fs_s, subject_level) if "subject" in f["entities"] else False))
        levels["subject"][fid], levels["biosample"][fid], levels["file"][fid] = subject_level, biosample_level, file_level
    levels["subject"][SINGLE_ORGANISM_BIT] = s_org

    order = sorted(fields) + [SINGLE_ORGANISM_BIT]
    patterns = {}
    for lv in ENTITIES:
        if n[lv] == 0:
            patterns[lv] = {"total": 0, "patterns": []}
            continue
        code = np.zeros(n[lv], dtype=np.int64)
        for bit, fid in enumerate(order):
            if fid in levels[lv]:
                code |= levels[lv][fid].astype(np.int64) << bit
        masks, counts = np.unique(code, return_counts=True)
        patterns[lv] = {"total": n[lv], "patterns": [[int(m), int(c)] for m, c in zip(masks, counts)]}

    # Records whose only sex information is "Indeterminate" (reported next to sex counts).
    sex_value = (subjects["sex"].astype("string").str.strip() if "sex" in subjects.columns
                 else pd.Series(pd.NA, index=subjects.index, dtype="string"))
    s_indet = (sex_value == INDETERMINATE_SEX).fillna(False).to_numpy(dtype=bool) & s_org
    no_sex = {lv: ~levels[lv].get("sex", np.zeros(n[lv], bool)) for lv in ENTITIES}
    b_indet = any_linked(n["biosample"], bs_b, bs_s, s_indet) & no_sex["biosample"]
    f_indet = (any_linked(n["file"], fb_f, fb_b, b_indet) | any_linked(n["file"], fs_f, fs_s, s_indet)) & no_sex["file"]
    return {"fields": order, "levels": patterns,
            "sex_indeterminate": {"subject": int(s_indet.sum()), "biosample": int(b_indet.sum()),
                                  "file": int(f_indet.sum())}}


def count_meeting(combinations: dict, level: str, required: list[str]) -> tuple[int, int]:
    """(records at `level` that have ALL `required` fields, records counted at `level`), from stored bitmasks.
    A field the package doesn't have is met by no record. Sex/age subject counts are out of single-organism
    subjects."""
    order = combinations["fields"]
    data = combinations["levels"][level]
    total = data["total"]
    if level == "subject" and ORGANISM_FIELDS & set(required):
        org = 1 << order.index(SINGLE_ORGANISM_BIT)
        total = sum(c for m, c in data["patterns"] if m & org)
    if any(r not in order for r in required):
        return 0, total
    mask = sum(1 << order.index(r) for r in required)
    return sum(c for m, c in data["patterns"] if m & mask == mask), total


def field_catalog(results: list[dict]) -> dict[str, dict]:
    """Every field discovered in any of these programs: id -> how to show and count it."""
    catalog = {}
    for r in results:
        for f in r["fields"]:
            entry = catalog.setdefault(f["id"], {k: f[k] for k in ("label", "group", "file_only", "no_subject_level",
                                                                      "organism")} | {"sources": [], "programs": []})
            entry["sources"] = sorted(set(entry["sources"]) | set(f["sources"]))
            entry["programs"].append(r["program"])
    return catalog


def coverage_level(f: dict) -> str | None:
    """The level at which a field's '% filled' is measured (None: per-record fields, measured on every level)."""
    if f["kind"] == "per_record":
        return None
    return "file" if f["file_only"] else "biosample" if f["no_subject_level"] else "subject"


def field_filled(combinations: dict, f: dict) -> tuple[int, int]:
    """Records with the field / records it could be on (exact, from the bitmasks)."""
    level = coverage_level(f)
    if level:
        return count_meeting(combinations, level, [f["id"]])
    parts = [count_meeting(combinations, lv, [f["id"]]) for lv in ENTITIES]
    return sum(p[0] for p in parts), sum(p[1] for p in parts)


def term_labels_for(prog: dict) -> dict[str, str]:
    """Value -> label, from the package's own term tables and CFDE vocabularies."""
    labels = dict(CFDE_VOCABULARY)
    for names in (prog["term_names"], prog.get("value_labels", pd.DataFrame(columns=["id", "name"]))):
        labels.update({str(i).strip(): str(nm) for i, nm in zip(names["id"], names["name"]) if is_filled(nm)})
    return labels


def discover_fields(prog: dict, combinations: dict | None = None, fields: dict | None = None,
                    labels: dict | None = None) -> list[dict]:
    """The available fields (at least one filled value) with their counts and most common values."""
    fields = fields if fields is not None else field_sources(prog)
    combinations = combinations if combinations is not None else field_bitmasks(prog, fields)
    labels = labels if labels is not None else term_labels_for(prog)
    found = []
    for fid in sorted(fields, key=lambda k: (FIELD_GROUPS.index(fields[k]["group"]), fields[k]["label"].lower())):
        f = fields[fid]
        filled, total = field_filled(combinations, f)
        values = []
        for table, column in f["sources"]:
            df = prog[table] if table in prog else prog.get("assoc", {}).get(table)
            if df is not None and column in df.columns:
                usable = age_mask(df, column, prog) if fid == "age" else column_mask(df, column)
                values.append(df.loc[usable, column].astype(str).str.strip())
        values = pd.concat(values) if values else pd.Series(dtype=str)
        if not len(values):
            continue  # not available: no filled value anywhere
        counts = values.value_counts()
        entry = {"id": fid, "label": f["label"], "group": f["group"], "entity": f["entities"],
                 "sources": [f"{t}.{c}" for t, c in f["sources"]], "kind": f["kind"],
                 "file_only": f["file_only"], "no_subject_level": f["no_subject_level"], "organism": f["organism"],
                 "records_filled": filled, "records_total": total, "distinct_values": int(len(counts))}
        # Mostly-unique values (checksums, sizes, URLs) and per-record fields (persistent IDs,
        # timestamps) have no meaningful "most common" list.
        if f["kind"] != "per_record" and len(counts) <= max(50, 0.5 * len(values)):
            entry["top_values"] = [[v, labels.get(v, ""), int(c)] for v, c in counts.head(TOP_VALUES).items()]
        found.append(entry)
    return found


def field_coverage(dims: dict, combinations: dict) -> list[dict]:
    """% of records with each key field filled, for the Field coverage view. Reuses the
    scored checks' numbers; disease links come from the biosample-level combinations."""
    def from_check(dim_name: str, check_id: str) -> tuple[int, int]:
        # A dimension with nothing to measure (e.g. no files) has no checks: 0 of 0.
        c = next((c for c in dims[dim_name]["checks"] if c["id"] == check_id), None)
        return (c["passed"], c["total"]) if c else (0, 0)

    disease = count_meeting(combinations, "biosample", ["disease"])
    fields = [
        ("sex", "Sex", "subject.sex", "single-organism subjects", from_check("Characterization", "subject_sex")),
        ("age", "Age", "subject.age_at_enrollment, biosample_from_subject.age_at_sampling",
         "single-organism subjects", from_check("Characterization", "subject_age")),
        ("anatomy", "Anatomy", "biosample.anatomy", "biosamples", from_check("Characterization", "biosample_anatomy")),
        ("disease", "Disease link", "biosample_disease, subject_disease (via biosample_from_subject)",
         "biosamples", disease),
        ("persistent_id", "Persistent ID", "persistent_id (all records), file.access_url", "records",
         from_check("FAIRness", "persistent_ids")),
        ("checksum", "Checksum", "file.sha256, file.md5", "files", from_check("Provenance", "file_checksums")),
        ("file_format", "File format", "file.file_format", "files", from_check("Computability", "file_format")),
        ("creation_time", "Creation time", "creation_time (all records)", "records",
         from_check("Provenance", "creation_time")),
    ]
    return [{"field": f, "label": label, "columns": cols, "unit": unit, "passed": passed, "total": total}
            for f, label, cols, unit, (passed, total) in fields]


# ---------------------------------------------------------------------------
# Data quality notes (reported, never scored)
# ---------------------------------------------------------------------------

HUMAN_TAXON_IDS = {"NCBI:txid9606", "NCBITaxon:9606"}


def human_subjects(prog: dict, organisms: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Single-organism subjects that are human (via subject_role_taxonomy, when the package has it)."""
    taxa = prog.get("assoc", {}).get("subject_role_taxonomy")
    if taxa is None or "taxonomy_id" not in taxa.columns or not len(taxa):
        return organisms, "single-organism subjects"
    human = taxa[taxa["taxonomy_id"].astype(str).str.strip().isin(HUMAN_TAXON_IDS)]
    keys = set(zip(human["subject_id_namespace"], human["subject_local_id"]))
    mask = pd.Series([k in keys for k in zip(organisms["id_namespace"], organisms["local_id"])], index=organisms.index,
                     dtype=bool)
    return organisms[mask], "human subjects"


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

    # 6. Sex recorded as "Indeterminate" (cfde_subject_sex:0). It is a valid
    #    C2M2 value, so it counts as recorded, but it carries no sex information.
    organisms, _ = organism_subjects(prog["subject"])
    if "sex" in organisms.columns:
        sex = organisms["sex"].astype("string").str.strip()
        indeterminate = int((sex == INDETERMINATE_SEX).sum())
        if indeterminate:
            counts = sex[filled_mask(organisms["sex"])].value_counts()
            found.append(f"subject.tsv: {indeterminate:,} single-organism subject(s) have sex recorded as "
                         f"Indeterminate ({INDETERMINATE_SEX}). This is a valid C2M2 value, so they count as "
                         "having sex recorded, but it does not say which sex. All sex values used: "
                         + ", ".join(f"{SEX_NAMES.get(v, v)} {n:,}" for v, n in counts.items()) + ".")

    # 7. Ages of exactly 0. C2M2 ages are in years, so 0 means under one year
    #    old; when it is common, it is worth confirming it is not a stand-in
    #    for "unknown". Only noted when it is a notable share of recorded ages,
    #    since infants are expected in some studies (e.g. pediatric ones).
    for table, column in [("subject", "age_at_enrollment"), ("biosample_from_subject", "age_at_sampling")]:
        df = organisms if table == "subject" else prog[table]
        if column in df.columns:
            zero = int((pd.to_numeric(df[column], errors="coerce") == 0).sum())
            if zero and zero >= ZERO_AGE_SHARE * int(column_mask(df, column).sum()):
                found.append(f"{table}.tsv: {zero:,} of {int(column_mask(df, column).sum()):,} recorded "
                             f"{column} values are exactly 0 (under one year old). If 0 is used for "
                             "\"unknown\", leaving the field empty would keep it from being read as an age.")
    rule = prog.get("age_rule") or age_zero_rule(prog)
    if rule["applies"]:
        found.append(f"{rule['zeros']:,} ages of exactly 0 treated as not recorded (likely placeholders): "
                     f"{rule['zeros'] / rule['recorded']:.0%} of the {rule['recorded']:,} recorded ages are 0, while the "
                     f"median of the others is {rule['median_nonzero_age']:g} years (rule AGE_ZERO_PLACEHOLDER).")

    # 8. Likely sex mis-coding: Female and Indeterminate but no Male (or the reverse).
    humans, whom = human_subjects(prog, organisms)
    if "sex" in humans.columns:
        codes = humans["sex"].astype("string").str.strip().value_counts()
        n_female, n_male = int(codes.get(KNOWN_SEX[0], 0)), int(codes.get(KNOWN_SEX[1], 0))
        n_indet = int(codes.get(INDETERMINATE_SEX, 0))
        for present, absent, n_present in (("Female", "Male", n_female), ("Male", "Female", n_male)):
            if n_present and n_indet and not (n_male if absent == "Male" else n_female):
                found.append(f"subject.tsv ({whom}): no subjects are coded {absent} while {n_indet:,} are coded "
                             f"Indeterminate ({INDETERMINATE_SEX}) and {n_present:,} are coded {present}. If 0 was "
                             f"intended to mean {absent}, these subjects are mis-coded; worth confirming with the "
                             "program.")
    return found


def score_program(namespace: str, label: str, prog: dict[str, pd.DataFrame],
                  release: str = "", release_date: str = "") -> dict:
    prog.setdefault("age_rule", age_zero_rule(prog))  # projects are given their program's decision
    dims = {name: fn(prog) for name, fn in DIMENSIONS}
    # Store the plain-English text with the numbers, so the JSON output is
    # self-contained (the web app reads only the JSON).
    for dim in dims.values():
        for c in dim["checks"]:
            c["why_it_matters"] = WHY_IT_MATTERS[c["id"]]
        if dim["score"] != NOT_ASSESSABLE and dim["score"] < LOW_SCORE_THRESHOLD:
            dim["observation"] = low_score_sentence(dim)
    numeric = [d["score"] for d in dims.values() if d["score"] != NOT_ASSESSABLE]
    fields = field_sources(prog)
    combinations = field_bitmasks(prog, fields)
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
        "field_coverage": field_coverage(dims, combinations),
        "fields": discover_fields(prog, combinations, fields),
        "combinations": combinations,
        "age_zero_rule": prog["age_rule"],
    }


# ---------------------------------------------------------------------------
# Project-level scoring (read by the web app's Dataset basket)
# ---------------------------------------------------------------------------
# A datapackage is a whole program, but researchers choose projects/studies.
# Each project is scored with the SAME dimension functions as a program, on
# the records that make up that project:
#   1. subjects, biosamples and files whose project_id_namespace/local_id is
#      the project or one of its sub-projects (project_in_project, any depth);
#   2. plus the biosamples and subjects those records link to directly
#      (file_describes_biosample, file_describes_subject, biosample_from_subject).
#      Links are followed file -> biosample -> subject only, never back down,
#      so a shared subject does not pull in other projects' samples. Several
#      programs (e.g. ExRNA, LINCS) file their subjects under a different project
#      than the samples taken from them, so without this step those projects
#      would appear to have no subjects.
#   3. disease links of those biosamples and subjects.
# Checks that describe the datapackage as a whole are inherited from the
# package and marked as inherited.
PACKAGE_LEVEL_CHECKS = {
    "labeled_terms": "term labels come from the package's shared term tables",
    "croissant_valid": "Croissant is generated and validated for the whole package",
}
PROJECTS_JSON = OUTPUT_DIR / "readiness_projects.json"
EXPORT_TABLES = ["project", "subject", "biosample", "file", "biosample_from_subject", "file_describes_biosample",
                 "file_describes_subject", "biosample_disease", "subject_disease"]
PROJECT_DESCRIPTION_CHARS = 300  # descriptions are shortened to keep the JSON small
PROJECT_RULES = (
    "A project's records are its own subjects, biosamples and files (including those of its sub-projects, "
    "via project_in_project), plus the biosamples and subjects they link to directly (file_describes_biosample, "
    "file_describes_subject, biosample_from_subject; followed from files to biosamples to subjects only). "
    "Each project is scored with the same checks as a whole program. Two checks describe the datapackage "
    "as a whole and are inherited from the program: term labels (from the package's shared term tables) "
    "and Croissant validity.")


def unique_keys(df: pd.DataFrame, ns_col: str = "id_namespace", id_col: str = "local_id") -> pd.MultiIndex:
    return pd.MultiIndex.from_arrays([df[ns_col].astype(str), df[id_col].astype(str)]).unique()


def key_positions(index: pd.MultiIndex, df: pd.DataFrame, ns_col: str, id_col: str) -> np.ndarray:
    """Position in `index` of each row's (ns_col, id_col) key; -1 if absent."""
    if df.empty or len(index) == 0 or ns_col not in df.columns or id_col not in df.columns:
        return np.full(len(df), -1)
    return index.get_indexer(pd.MultiIndex.from_arrays([df[ns_col].astype(str), df[id_col].astype(str)]))


def mark(n: int, pos: np.ndarray) -> np.ndarray:
    flags = np.zeros(n, dtype=bool)
    flags[pos[pos >= 0]] = True
    return flags


def project_tree(projects: pd.DataFrame, pip: pd.DataFrame | None) -> tuple[pd.MultiIndex, list[int], list[list[int]]]:
    """Project keys, each project's parent position (-1 for none) and descendant positions (itself included)."""
    index = unique_keys(projects)
    n = len(index)
    parent, children = [-1] * n, [[] for _ in range(n)]
    if pip is not None and len(pip):
        parents = key_positions(index, pip, "parent_project_id_namespace", "parent_project_local_id")
        kids = key_positions(index, pip, "child_project_id_namespace", "child_project_local_id")
        for p, c in zip(parents, kids):
            if p >= 0 and c >= 0 and p != c:
                children[p].append(c)
                if parent[c] < 0:
                    parent[c] = p
    descendants = []
    for start in range(n):
        seen, stack = {start}, [start]
        while stack:
            for c in children[stack.pop()]:
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        descendants.append(sorted(seen))
    return index, parent, descendants


# Per-project results are stored as lists in these orders (named once at the
# top of the JSON), which keeps the file small with ~3,000 projects.
DIMENSION_ORDER = [name for name, _ in DIMENSIONS]
CHECK_ORDER = [check_id for _, check_id, _, _ in METHODS if check_id in WHY_IT_MATTERS]  # real checks only
COVERAGE_ORDER = ["sex", "age", "anatomy", "disease", "persistent_id", "checksum", "file_format", "creation_time"]


def compact_dimensions(dims: dict) -> tuple[list, list]:
    """[score or None per dimension], [[passed, total] or None per check] in DIMENSION_ORDER / CHECK_ORDER."""
    scores = [None if dims[name]["score"] == NOT_ASSESSABLE else dims[name]["score"] for name in DIMENSION_ORDER]
    found = {c["id"]: [c["passed"], c["total"]] for d in dims.values() for c in d["checks"]}
    return scores, [found.get(check_id) for check_id in CHECK_ORDER]


def score_projects(data_dir: Path, package: dict) -> tuple[list[dict], dict[str, str]]:
    """Score every project in one real datapackage that has at least one subject, biosample or file.
    `package` is the program-level result from score_real_package (its inherited checks are reused).
    Also returns the value labels (term tables), used to name the projects' most common values."""
    tables = load_tables(data_dir)
    prog = {name: tables[name] for name in PER_PROGRAM_TABLES}
    prog.update(term_names=tables["term_names"], value_labels=tables["value_labels"], assoc=tables["assoc"],
                age_rule=package["age_zero_rule"])  # projects follow their program's AGE_ZERO_PLACEHOLDER decision
    # One field list (bit order) for the whole package, so every project's bitmasks read the same way.
    package_fields = field_sources(prog)
    labels = term_labels_for(prog)
    projects = prog["project"]
    index, parent, descendants = project_tree(projects, read_tsv(data_dir / "project_in_project.tsv"))
    n_proj = len(index)

    # Row positions of every record and link, computed once.
    rec = {t: prog[t] for t in ("subject", "biosample", "file")}
    idx = {t: unique_keys(df) for t, df in rec.items()}
    row_pos = {t: key_positions(idx[t], df, "id_namespace", "local_id") for t, df in rec.items()}
    own_project = {t: np.full(len(idx[t]), -1) for t in rec}
    for t, df in rec.items():
        proj_of_row = key_positions(index, df, "project_id_namespace", "project_local_id")
        own_project[t][row_pos[t]] = proj_of_row
    project_row = key_positions(index, projects, "id_namespace", "local_id")

    def link(table: str, a: str, b: str) -> tuple[np.ndarray, np.ndarray]:
        df = prog[table]
        return (key_positions(idx[a], df, f"{a}_id_namespace", f"{a}_local_id"),
                key_positions(idx[b], df, f"{b}_id_namespace", f"{b}_local_id"))
    fb_f, fb_b = link("file_describes_biosample", "file", "biosample")
    fs_f, fs_s = link("file_describes_subject", "file", "subject")
    bs_b, bs_s = link("biosample_from_subject", "biosample", "subject")
    bd_b = key_positions(idx["biosample"], prog["biosample_disease"], "biosample_id_namespace", "biosample_local_id")
    assoc_pos = {name: (entity, key_positions(idx[entity], df, f"{entity}_id_namespace", f"{entity}_local_id"))
                 for name, df in prog["assoc"].items()
                 for entity in [next(e for e in ENTITIES if name.startswith(e + "_"))]}
    sd_s = key_positions(idx["subject"], prog["subject_disease"], "subject_id_namespace", "subject_local_id")

    package_checks = {c["id"]: c for d in package["dimensions"].values() for c in d["checks"]}
    explainability = package["dimensions"]["Pre-model Explainability"]
    name_col = projects["name"] if "name" in projects.columns else pd.Series("", index=projects.index)
    desc_col = projects["description"] if "description" in projects.columns else pd.Series("", index=projects.index)
    first_row = {int(p): i for i, p in reversed(list(enumerate(project_row))) if p >= 0}

    results = []
    for p in range(n_proj):
        in_tree = mark(n_proj, np.array(descendants[p]))

        def own(t: str) -> np.ndarray:
            op = own_project[t]
            return (op >= 0) & in_tree[np.maximum(op, 0)]

        files = own("file")
        biosamples = own("biosample") | mark(len(idx["biosample"]), fb_b[(fb_f >= 0) & files[np.maximum(fb_f, 0)]])
        subjects = (own("subject")
                    | mark(len(idx["subject"]), fs_s[(fs_f >= 0) & files[np.maximum(fs_f, 0)]])
                    | mark(len(idx["subject"]), bs_s[(bs_b >= 0) & biosamples[np.maximum(bs_b, 0)]]))
        if not (files.any() or biosamples.any() or subjects.any()):
            continue
        keep = {"file": files, "biosample": biosamples, "subject": subjects}

        def rows(t: str) -> pd.DataFrame:
            return rec[t][keep[t][row_pos[t]]].reset_index(drop=True)

        def link_rows(table: str, owner_pos: np.ndarray, owner: str) -> pd.DataFrame:
            return prog[table][(owner_pos >= 0) & keep[owner][np.maximum(owner_pos, 0)]].reset_index(drop=True)

        sub = {
            "project": projects[(project_row >= 0) & in_tree[np.maximum(project_row, 0)]].reset_index(drop=True),
            "subject": rows("subject"), "biosample": rows("biosample"), "file": rows("file"),
            "biosample_from_subject": link_rows("biosample_from_subject", bs_b, "biosample"),
            "file_describes_biosample": link_rows("file_describes_biosample", fb_f, "file"),
            "file_describes_subject": link_rows("file_describes_subject", fs_f, "file"),
            "biosample_disease": link_rows("biosample_disease", bd_b, "biosample"),
            "subject_disease": link_rows("subject_disease", sd_s, "subject"),
            "term_names": tables["term_names"],
            "value_labels": tables["value_labels"],
            "age_rule": package["age_zero_rule"],
            "assoc": {name: prog["assoc"][name][(pos >= 0) & keep[entity][np.maximum(pos, 0)]].reset_index(drop=True)
                      for name, (entity, pos) in assoc_pos.items()},
        }
        dims = {}
        for dim_name, fn in DIMENSIONS:
            if dim_name == "Pre-model Explainability":
                dims[dim_name] = explainability  # term tables are package-wide
            elif dim_name == "Computability":
                dims[dim_name] = score_computability(sub, croissant=package_checks.get("croissant_valid"))
            else:
                dims[dim_name] = fn(sub)
        numeric = [d["score"] for d in dims.values() if d["score"] != NOT_ASSESSABLE]
        combinations = field_bitmasks(sub, package_fields)
        coverage = field_coverage(dims, combinations)
        assert [f["field"] for f in coverage] == COVERAGE_ORDER
        scores, checks = compact_dimensions(dims)
        row = first_row.get(p)
        name = str(name_col.iloc[row]).strip() if row is not None and is_filled(name_col.iloc[row]) else index[p][1]
        description = str(desc_col.iloc[row]).strip() if row is not None and is_filled(desc_col.iloc[row]) else ""
        if len(description) > PROJECT_DESCRIPTION_CHARS:
            description = description[:PROJECT_DESCRIPTION_CHARS].rsplit(" ", 1)[0] + " ..."
        results.append({
            "id": list(index[p]),
            "name": name,
            "description": description,
            "parent": list(index[parent[p]]) if parent[p] >= 0 else None,
            "sub_projects": len(descendants[p]) - 1,
            "record_counts": {"project": len(sub["project"]), "subject": int(subjects.sum()),
                              "biosample": int(biosamples.sum()), "file": int(files.sum())},
            "overall_score": round(sum(numeric) / len(numeric)) if numeric else None,
            "dimensions": scores,
            "checks": checks,
            "field_coverage": [[f["passed"], f["total"]] for f in coverage],
            "combinations": combinations["levels"],
            "sex_indeterminate": combinations["sex_indeterminate"],
            # Discovered fields: [bit, records filled, records it could be on, distinct values,
            # [[value, count], ...] most common] -- values are resolved to names at program level.
            "fields": [[combinations["fields"].index(f["id"]), f["records_filled"], f["records_total"],
                        f["distinct_values"], [[v, c] for v, _, c in f.get("top_values", [])]]
                       for f in discover_fields(sub, combinations, package_fields, labels)],
        })
    return results, labels


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_projects(root: Path) -> None:
    """Score every project in every package in data_real/ -> output/readiness_projects.json."""
    releases = read_tsv(RELEASES_FILE)
    programs, projects = [], []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        package_dir = find_package_dir(folder)
        if package_dir is None:
            print(f"skipping {folder.name}/: no project.tsv found (not unzipped?)")
            continue
        print(f"scoring {folder.name}/ and its projects ...", flush=True)
        package = score_real_package(package_dir, folder)
        listed = releases[releases["folder"] == folder.name] if releases is not None else pd.DataFrame()
        display = listed["program"].iloc[0] if len(listed) else package["program"]
        zip_path = folder / package["release"]
        scored, labels = score_projects(package_dir, package)
        # Consistency check: the project that contains every other project (the
        # program's root) covers the whole package, so it must score the same.
        full = [r for r in scored if r["record_counts"]["project"] == package["record_counts"]["project"]]
        for r in full:
            same = (r["overall_score"] == package["overall_score"]
                    and r["dimensions"] == compact_dimensions(package["dimensions"])[0])
            print(f"  root project '{r['name']}' covers the whole package: "
                  f"{'same scores as the program' if same else 'SCORES DIFFER FROM THE PROGRAM'}")
        programs.append({
            "program": display,
            "package_label": package["program"],
            "release": package["release"],
            "release_date": package["release_date"],
            "old_release": package["old_release"],
            "download_url": listed["url"].iloc[0] if len(listed) else "",
            "sha256": file_sha256(zip_path) if zip_path.is_file() else "",
            # Where the C2M2 tables sit inside the zip ("" = at its top level).
            "package_path": inner if (inner := Path(package_dir).resolve().relative_to(folder.resolve()).as_posix()) != "." else "",
            "overall_score": package["overall_score"],
            "record_counts": package["record_counts"],
            # Column names of the tables a basket export describes (Croissant needs real columns).
            "columns": {t: list(pd.read_csv(path, sep="\t", nrows=0).columns)
                        for t in dict.fromkeys(EXPORT_TABLES + sorted(association_table_columns(Path(package_dir))))
                        if (path := Path(package_dir) / f"{t}.tsv").exists() and path.stat().st_size},
            "inherited_checks": {cid: {"passed": c["passed"], "total": c["total"], "why": PACKAGE_LEVEL_CHECKS[cid]}
                                 for d in package["dimensions"].values() for c in d["checks"]
                                 if (cid := c["id"]) in PACKAGE_LEVEL_CHECKS},
            # Field discovery for the whole package, and the bit order of every project's bitmasks.
            "fields": package["fields"],
            "field_order": package["combinations"]["fields"],
            "values": [],  # [value, label] -- projects' most common values point into this list
        })
        # Projects store their most common values as positions in the program's value list.
        value_pos = {}
        for r in scored:
            for stat in r["fields"]:
                for pair in stat[4]:
                    if pair[0] not in value_pos:
                        value_pos[pair[0]] = len(value_pos)
                        programs[-1]["values"].append([pair[0], labels.get(pair[0], "")])
                    pair[0] = value_pos[pair[0]]
            projects.append({"program": display, **r})
        print(f"  {len(scored)} projects scored")

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(PROJECTS_JSON, "w") as f:
        json.dump({"source": CITATION,
                   "disclaimer": DISCLAIMER,
                   "generated": date.today().isoformat(),
                   "rules": PROJECT_RULES,
                   "combination_rules": COMBINATION_RULES,
                   "field_groups": FIELD_GROUPS,
                   "dimension_order": DIMENSION_ORDER,
                   "check_order": CHECK_ORDER,
                   "coverage_order": COVERAGE_ORDER,
                   "programs": programs,
                   "projects": projects}, f, separators=(",", ":"))
    size = PROJECTS_JSON.stat().st_size / 1e6
    print(f"Wrote {PROJECTS_JSON} ({len(projects)} projects, {size:.1f} MB)")


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
    prog["value_labels"] = tables["value_labels"]
    prog["assoc"] = tables["assoc"]
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
                   "field_groups": FIELD_GROUPS,
                   "fields": field_catalog(results),
                   "combination_rules": COMBINATION_RULES,
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
    parser.add_argument("--projects", action="store_true",
                        help="score every project inside every package in data_real/ and write "
                             "output/readiness_projects.json (read by the web app's Dataset basket)")
    args = parser.parse_args()

    print("CFDE AI-Readiness Checker (simplified proxies for the Bridge2AI dimensions; not official)")
    if args.compare:
        run_compare(DATA_REAL_DIR)
        return
    if args.projects:
        run_projects(DATA_REAL_DIR)
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
