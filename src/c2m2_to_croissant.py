"""
c2m2_to_croissant.py

Converts a small C2M2 datapackage (TSV tables following the official CFDE
C2M2 schema) into a Croissant-format JSON-LD metadata file, so the dataset
becomes machine-readable for AI tools -- addressing the AI-readiness gap
named in the CFDE Workbench paper (only GTEx, LINCS, MoTrPAC and Bridge2AI
currently have Croissant metadata).

Usage:
    python3 c2m2_to_croissant.py

Reads TSVs from ../data/, writes croissant metadata to ../output/croissant.json
"""

import json
import pandas as pd
from pathlib import Path

from term_labels import label_for

# C2M2 columns that hold ontology term IDs (rather than plain values) --
# these are the ones worth enriching with human-readable labels.
ONTOLOGY_COLUMNS = {
    "anatomy", "biofluid", "sample_prep_method", "assay_type",
    "analysis_type", "file_format", "compression_format", "data_type",
}

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Map pandas/C2M2 field types to Croissant (schema.org) data types
# (kept intentionally simple -- good enough for a prototype)
CORE_TABLES = ["project", "subject", "biosample", "file"]

def infer_croissant_type(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "sc:Integer"
    if pd.api.types.is_float_dtype(series):
        return "sc:Float"
    return "sc:Text"


def build_recordset(table_name: str, df: pd.DataFrame) -> dict:
    fields = []
    for col in df.columns:
        description = f"Column '{col}' from the C2M2 {table_name}.tsv table."

        # For ontology-coded columns, add human-readable labels for
        # whichever distinct term IDs actually appear in the real data --
        # this is the AI-readiness enrichment: a raw code like
        # "OBI:0002117" means nothing to a person or most AI tools without
        # this lookup, and C2M2 itself stores only the code.
        if col in ONTOLOGY_COLUMNS:
            terms = sorted(t for t in df[col].dropna().unique() if str(t).strip())
            if terms:
                labeled = [label_for(t) for t in terms]
                description += " Terms used in this data: " + "; ".join(labeled) + "."

        fields.append({
            "@type": "cr:Field",
            "@id": f"{table_name}/{col}",
            "dataType": infer_croissant_type(df[col]),
            "description": description,
            "source": {
                "fileObject": {"@id": f"{table_name}.tsv"},
                "extract": {"column": col},
            },
        })
    return {
        "@type": "cr:RecordSet",
        "@id": table_name,
        "name": table_name,
        "key": {"@id": f"{table_name}/local_id"},
        "field": fields,
    }


def build_distribution(table_name: str) -> dict:
    return {
        "@type": "cr:FileObject",
        "@id": f"{table_name}.tsv",
        "name": f"{table_name}.tsv",
        "contentUrl": f"./data/{table_name}.tsv",
        "encodingFormat": "text/tab-separated-values",
    }


def main():
    distributions = []
    recordsets = []
    row_counts = {}

    for table in CORE_TABLES:
        tsv_path = DATA_DIR / f"{table}.tsv"
        df = pd.read_csv(tsv_path, sep="\t", dtype=str)
        row_counts[table] = len(df)
        distributions.append(build_distribution(table))
        recordsets.append(build_recordset(table, df))

    croissant = {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "cr": "http://mlcommons.org/croissant/",
            "dct": "http://purl.org/dc/terms/",
            "sc": "https://schema.org/",
        },
        "@type": "sc:Dataset",
        "name": "demo-eeg-c2m2-dataset",
        "description": (
            "A small demonstration C2M2 datapackage (project, subject, "
            "biosample, file tables) converted into Croissant-format "
            "AI-ready metadata. Built as a prototype addressing the "
            "AI-readiness gap named in the CFDE Workbench paper."
        ),
        "dct:conformsTo": "http://mlcommons.org/croissant/1.0",
        "url": "https://example.org/demo-eeg-c2m2-dataset",
        "distribution": distributions,
        "recordSet": recordsets,
    }

    out_path = OUTPUT_DIR / "croissant.json"
    with open(out_path, "w") as f:
        json.dump(croissant, f, indent=2)

    print(f"Wrote Croissant metadata to {out_path}")
    print("Row counts per table:", row_counts)


if __name__ == "__main__":
    main()
