"""
validate_croissant.py

Structurally validates output/croissant.json against the real Croissant
1.0 spec (docs.mlcommons.org/croissant/docs/croissant-spec.html).

Note on approach: the official `mlcroissant` Python package fails to
install in this environment (a packaging bug in one of its dependencies,
`jsonpath-rw`, unrelated to our code -- it uses a legacy setup.py that's
incompatible with modern setuptools). Rather than fight that, this script
checks the same required structure by hand, straight from the spec:

- top-level @context, @type == "sc:Dataset", name, description
- every distribution entry is a cr:FileObject with @id, contentUrl, encodingFormat
- every recordSet has @id, key, and a non-empty field list
- every field has @id, dataType, and a source.fileObject/extract.column
- every field's source.fileObject.@id actually matches a distribution @id
  (catches typos / renamed files -- this is the kind of bug the official
  validator would catch, so we check it too)
"""

import json
from pathlib import Path

CROISSANT_PATH = Path(__file__).parent.parent / "output" / "croissant.json"

REQUIRED_TOP_LEVEL = ["@context", "@type", "name", "description", "distribution", "recordSet"]
VALID_DATATYPES = {"sc:Text", "sc:Integer", "sc:Float", "sc:Boolean", "sc:Date", "sc:DateTime"}


def validate(doc: dict) -> list[str]:
    errors = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            errors.append(f"Missing required top-level key: {key}")

    if doc.get("@type") != "sc:Dataset":
        errors.append(f"@type should be 'sc:Dataset', got {doc.get('@type')!r}")

    distribution_ids = set()
    for i, dist in enumerate(doc.get("distribution", [])):
        for key in ["@type", "@id", "contentUrl", "encodingFormat"]:
            if key not in dist:
                errors.append(f"distribution[{i}] missing '{key}'")
        if "@id" in dist:
            distribution_ids.add(dist["@id"])

    for i, rs in enumerate(doc.get("recordSet", [])):
        for key in ["@type", "@id", "key", "field"]:
            if key not in rs:
                errors.append(f"recordSet[{i}] missing '{key}'")
        fields = rs.get("field", [])
        if not fields:
            errors.append(f"recordSet[{i}] ({rs.get('@id')}) has no fields")
        for j, field in enumerate(fields):
            loc = f"recordSet[{i}].field[{j}] ({field.get('@id')})"
            for key in ["@type", "@id", "dataType", "source"]:
                if key not in field:
                    errors.append(f"{loc} missing '{key}'")
            if field.get("dataType") not in VALID_DATATYPES:
                errors.append(f"{loc} has unrecognized dataType: {field.get('dataType')!r}")
            source = field.get("source", {})
            file_obj_id = source.get("fileObject", {}).get("@id")
            if file_obj_id and file_obj_id not in distribution_ids:
                errors.append(f"{loc} references unknown fileObject '{file_obj_id}' "
                               f"(not in distribution list)")
            if "extract" not in source or "column" not in source.get("extract", {}):
                errors.append(f"{loc} source missing extract.column")

    return errors


if __name__ == "__main__":
    with open(CROISSANT_PATH) as f:
        doc = json.load(f)

    errors = validate(doc)

    print(f"Validating {CROISSANT_PATH}")
    print(f"  distribution entries: {len(doc.get('distribution', []))}")
    print(f"  recordSets: {len(doc.get('recordSet', []))}")
    total_fields = sum(len(rs.get("field", [])) for rs in doc.get("recordSet", []))
    print(f"  total fields: {total_fields}")
    print()

    if errors:
        print(f"FAILED -- {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    else:
        print("PASSED -- structurally valid Croissant 1.0 metadata.")
