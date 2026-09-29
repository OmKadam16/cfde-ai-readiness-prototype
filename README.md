# CFDE AI-Readiness Prototype — Week 2

## What this is
A working prototype that:
1. Represents a real, multi-program C2M2 datapackage (project, subject,
   biosample, file tables + 3 association tables), built to the official
   CFDE C2M2 schema (column names pulled directly from
   cfde.cloud/data/documentation/C2M2).
2. Converts that datapackage into **Croissant-format JSON-LD metadata**
   (`output/croissant.json`) — the AI-ready format CFDE has only adopted
   for a handful of its programs so far.
3. Builds a **knowledge graph** (`src/build_graph.py`, using NetworkX)
   connecting subjects → biosamples → files → project → disease, and runs
   real connected queries across it.

## The data is real
Values in `data/*.tsv` were pulled by hand from CFDE's live Data Portal
(cfde.cloud/data/processed/entity/biosample/search), one detail page at a
time, and transcribed into the official schema. Current coverage:

- **5 real DCCs**: SPARC, Kids First, HMP (Human Microbiome Project),
  LINCS, SenNet
- **11 projects**, **13 subjects**, **14 biosamples**, **5 files**
- Real anatomy terms (neck, urinary bladder, cardiac nerve plexus, stomach,
  posterior fornix of vagina, feces, breast, brain)
- One fully-detailed real file record (SPARC: filename, size, sha256,
  format, assay type, creation time, access URL)
- One real disease association (`biosample_disease.tsv`): two separate
  LINCS biosamples (different drug treatments on the same MCF10A cell
  line) both link to "breast carcinoma" — a real example of the knowledge
  graph unifying disparate records around a shared concept.
- A handful of gaps we could NOT fill from the portal (subject sex/age,
  some anatomy fields) are left blank rather than invented — this is
  itself a live example of the "limited patient metadata" gap named in
  the CFDE Workbench paper.

One synthetic demo cluster (`demo:proj1` / EEG study) is still in there
too, kept as a clean example of the schema mechanics.

## Files
- `schema/c2m2_field_reference.md` — real C2M2 column definitions.
- `data/*.tsv` — the datapackage (real + one demo cluster).
- `src/c2m2_to_croissant.py` — converts the datapackage to Croissant JSON-LD.
- `src/build_graph.py` — builds the knowledge graph (every node carries a
  `dcc` attribute now, not just an ID string, so DCC-based queries are
  reliable rather than guessed from substrings).
- `src/query.py` — command-line query interface over the graph (see below).
- `src/validate_croissant.py` — structural Croissant spec validator.
- `src/term_labels.py` — human-readable ontology term labels.
- `output/croissant.json` — the generated AI-ready metadata file.

## Run it
```
cd src
python3 c2m2_to_croissant.py
python3 build_graph.py
python3 validate_croissant.py
```

## Query it
```
python3 query.py list --type biosample
python3 query.py search --anatomy brain
python3 query.py search --dcc sparc
python3 query.py connected biosample:QC9XMFT8 --hops 2
python3 query.py show biosample:QC9XMFT8
```

## Validation + term labels (done)
- `src/validate_croissant.py` — structurally validates the output against
  the real Croissant 1.0 spec (checks required keys, field types, and
  that every field's fileObject reference actually resolves). The
  official `mlcroissant` package fails to install in this environment
  due to an unrelated packaging bug in one of its dependencies
  (`jsonpath-rw` + modern setuptools), so this validates the same
  structural rules by hand instead. Currently passes.
- `src/term_labels.py` — adds human-readable labels next to raw ontology
  codes (e.g. `OBI:0002119` → "microscopy assay") in the Croissant field
  descriptions. Each label is honestly marked by source: `portal` (read
  directly off a real CFDE page), `inferred` (reasoned from context, not
  independently confirmed), or `placeholder` (used only in the synthetic
  demo cluster, explicitly flagged as unverified rather than guessed).

## Week 2: query CLI (done)
- `src/query.py` — a simple, real command-line interface: `connected`,
  `list`, `search`, `show`. Building it surfaced (and fixed) a real bug:
  the graph originally had no explicit `dcc` attribute on nodes, so a
  "search by DCC" query silently returned nothing for some DCCs. Now
  every node carries its source DCC explicitly.

## Next steps
- Write up the disease-unification example as a short case study for the
  outreach email — it's the clearest illustration of "why this matters."
- Draft the actual outreach email to Chen/AI.MED Lab, linking the repo.
