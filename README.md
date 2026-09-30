# CFDE AI-Readiness Prototype

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
4. Runs an **AI-Readiness Checker** (`src/readiness_checker.py`) over full
   C2M2 releases from seven CFDE programs, using simple, measurable proxies
   for the seven AI-readiness dimensions defined by the Bridge2AI
   Standards Working Group (see below).

## AI-Readiness Checker

**These are simplified proxy measures for exploration, not an official
evaluation.**

`src/readiness_checker.py` measures what a C2M2 datapackage's metadata
records, along the seven dimensions in:

> Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv
> 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for
> Biomedical Data: Bridge2AI Recommendations")

The dimensions are FAIRness, Provenance, Characterization, Pre-model
Explainability, Ethics, Sustainability, and Computability. The paper
describes them qualitatively; the checks here are our own simplified
proxies, chosen because they can be computed directly from C2M2 tables.
They describe metadata coverage, not the quality of any program's data
or work, and are meant to point at concrete, fixable gaps.

### How scoring works
- Each dimension is one or more checks. Each check is a fraction
  (records that pass / records checked), kept alongside its raw numbers.
- A check with nothing to measure (e.g. no files) is skipped, not scored
  0. A dimension with no measurable checks is "NOT ASSESSABLE".
- A dimension's score is the average of its checks; the overall score is
  the average of the assessable dimensions.
- Some things are reported but never scored: info lines (disease
  associations, subjects excluded from sex/age checks) and per-program
  data quality notes (e.g. stray whitespace in term IDs).

| Dimension | Checks |
|---|---|
| FAIRness | records with a persistent identifier; ontology fields holding term IDs rather than free text |
| Provenance | records with `creation_time`; files with a sha256 or md5 checksum |
| Characterization | single-organism subjects with sex; with an age (`age_at_enrollment`, or `age_at_sampling` on a linked biosample); biosamples with anatomy |
| Pre-model Explainability | term IDs with a human-readable label (from the package's own term tables, or read off the portal) |
| Ethics | not assessable: the C2M2 schema has no consent or governance fields |
| Sustainability | files with a `persistent_id` or `access_url` |
| Computability | files with a `file_format`; Croissant generated and passing `validate_croissant.py` |

Rules worth knowing:
- **Persistent identifiers:** one scheme list applies to both
  `persistent_id` and `access_url`: DOI, identifiers.org, ARK, `drs://`,
  Handle, PURL. Plain `s3://` and ordinary `https://` URLs don't count.
  identifiers.org compact identifiers are recognised for prefixes we have
  confirmed in the identifiers.org registry (currently `sparc.drs`,
  MIR:00001102). Filled `persistent_id` values with other schemes are
  listed as a data quality note.
- **Sex and age** are checked only for single-organism subjects
  (`cfde_subject_granularity:0`), human or animal — NIH's Sex as a
  Biological Variable policy applies to both. Cell lines, synthetic
  entities, microbiomes etc. are excluded and reported as an info line.
- **Real vs sample data:** a real datapackage is one DCC's submission and
  is scored as one program. Only the hand-collected sample in `data/` is
  split by `id_namespace`.

### Download the real datapackages
Each program's C2M2 releases are listed at
`https://cfde.cloud/info/dcc/<program>#C2M2`. The releases used here are
recorded in `releases.tsv`. To download and unzip them into `data_real/`
(about 425 MB of zips, about 3.4 GB unzipped; git-ignored):

```
tail -n +2 releases.tsv | while IFS=$'\t' read -r folder program file date url; do
  mkdir -p "data_real/$folder" && curl -fL -o "data_real/$folder/$file" "$url" \
    && (cd "data_real/$folder" && unzip -qo "$file")
done
```

### Run it
```
cd src
python3 readiness_checker.py --compare                    # all of data_real/ -> output/readiness_comparison.md
python3 readiness_checker.py --projects                   # every project in data_real/ -> output/readiness_projects.json
python3 readiness_checker.py --data-dir ../data_real/sparc  # one real package
python3 readiness_checker.py                              # the hand-collected sample in data/
```

`--compare` scores every package in `data_real/` (about 60-75 seconds;
peak memory 1.5-4 GB in our runs, mostly from Kids First's and LINCS's
multi-million row file and link tables) and writes
`output/readiness_comparison.md` and `.json` plus a
`readiness_report_<program>.md` / `readiness_scores_<program>.json` per
program. `--projects` scores every project inside every package (7-10
minutes, most of it Metabolomics Workbench's 2,891 studies) and
writes `output/readiness_projects.json` (5.5 MB) for the web app's
Dataset basket. The checker itself uses only pandas and the standard library.

### Run the web app
`app.py` is a small Streamlit app for browsing the results without
installing anything beyond `requirements.txt`. It reads only the
committed `output/readiness_comparison.json` and
`output/readiness_projects.json`, so it does not need `data_real/`.

```
pip3 install -r requirements.txt
streamlit run app.py
```

It opens at http://localhost:8501. The pages answer three questions:

- **Overview** (a reviewer: how AI-ready is CFDE metadata?) - a score card
  per program, a radar of the six measurable dimensions (all programs in
  gray, one highlighted in blue), and the three key cross-program gaps.
- **Field coverage** - a heatmap of how many records have each key field
  filled (sex, age, anatomy, disease link, persistent ID, checksum, file
  format, creation time); hover a cell for the raw count and C2M2 column.
- **Find ML-ready data** (a researcher: where are records with everything
  my model needs?) - tick the fields your model needs (built from the fields
  discovered in the data, grouped as Demographics, Clinical/disease,
  Biological sample, Molecular and File/technical), set a *minimum records
  needed* (default 100), and see per program how many subjects, biosamples
  or files have all of them. A program meets the needs when at least that
  many records do (blue bar; gray when fewer). "What each program records"
  lists every discovered field. Counts are exact (see "Field discovery").
  Sex and age use the same single-organism rule as the scores, so subject
  counts for them are out of single-organism subjects. Here (and in the
  Dataset basket) **sex means Male or Female recorded; Indeterminate is not
  counted**, since a model can't use it. The number of records with only
  an Indeterminate sex is shown separately (ExRNA: 1,223 subjects; Kids
  First: 348). The Characterization score and Field coverage still count
  any recorded sex value.
- **Program report card** (a program's data team: what would help most?) -
  dimension scores, every check as a progress bar with "X of Y", the top 3
  fixes ranked by points they would add, and data quality notes.
- **Dataset basket** (a researcher: which of the studies I want have what
  my model needs?) - search and filter all ~3,150 projects across the seven
  programs, add them to a basket, tick what your model needs, and see each
  project's status; remove the ones that don't fit and export the selection.
  A table shows which fields each shown project records (% filled). See
  "Dataset basket" below.
- **Methods** and **Check your own datapackage** (upload a C2M2 `.zip` up
  to 50 MB zipped / 300 MB unzipped and see its report card; the file is
  unpacked to a temporary folder and deleted afterwards).

Charts use one neutral blue scale for scores and gray for n/a, and read in
both Streamlit's light and dark themes.

To publish it on Streamlit Community Cloud (free): push the repo to
GitHub, then at share.streamlit.io choose "Create app", pick this repo and
branch, and set the main file to `app.py`. `.streamlit/config.toml` sets
the 50 MB upload cap. After re-running `--compare`, commit
`output/readiness_comparison.json` so the app shows the new results; after
`--projects`, commit `output/readiness_projects.json`.

### Field discovery
The "My model needs" choices are not a hard-coded list. For each package
and each project, the checker scans every column of `subject.tsv`,
`biosample.tsv` and `file.tsv` (except keys and file names) and every
association table named `<entity>_<something>.tsv` that links a record to a
value (e.g. `subject_race`, `subject_phenotype`, `subject_disease`,
`biosample_disease`, `biosample_gene`, `biosample_substance`,
`subject_role_taxonomy`), whatever the package contains. A field is
available when at least one record has a value. For each field it records:
- a plain-English name and group;
- the C2M2 table/column and the entity;
- the records filled and the number of distinct values;
- the 5 most common values, with labels from the package's term tables or
  the CFDE vocabularies.

Some attributes are recorded in two places in C2M2, so they are merged into
one field:
- age (`age_at_enrollment`, `age_at_sampling`);
- disease (`subject_disease`, `biosample_disease`);
- checksums (`md5`, `sha256`).

Persistent IDs and creation time are always the record's own. Across the
seven programs, 26 fields are found. Biofluid, for example, is recorded
only by ExRNA and Metabolomics Workbench.

**Counting is exact.** Each subject, biosample and file gets a bitmask with
one bit per field it has, after following C2M2 links. The checker stores how
many records share each bitmask, per program and per project. Any "has all
of X, Y, Z" count is then a sum over the stored bitmasks, with no estimates
and no raw data needed. An uploaded package is scored and counted the same
way, live. The new engine reproduces all 2,667 counts of the previous
fixed-list finder exactly (127 combinations × 3 levels × 7 programs).
Scores are unchanged: discovery is reported, never scored.

### Dataset basket
A C2M2 datapackage is a whole program, but researchers pick projects or
studies, so the checker also scores **every project** in each package
(`--projects`). This uses the same checks as a whole program, on the
records that make up the project:

- **Records:** the subjects, biosamples and files whose
  `project_id_namespace`/`project_local_id` is the project or one of its
  sub-projects (`project_in_project`, any depth).
- **Linked records:** plus the biosamples and subjects those records link to
  directly (`file_describes_biosample`, `file_describes_subject`,
  `biosample_from_subject`). Links are followed from files to biosamples to
  subjects only, never back down. This matters because ExRNA and LINCS file
  their subjects under a different project than the samples taken from them.
- **Inherited checks:** two checks describe the whole datapackage, so each
  project takes them from its program: term labels (from the package's shared
  term tables) and Croissant validity.
- **Consistency check:** each program's root project contains everything, so
  it must score exactly like the program. It does, for all seven.

In the app you:
1. **choose** projects from a searchable table (program, project, record
   counts, overall score);
2. **set your needs**, using the same checkboxes as *Find ML-ready data* (the
   choice carries over between the two pages);
3. **review** each project's status:
   - *Meets your needs:* at least the *minimum records needed* (default
     100) have every selected field. There's no universal minimum for
     training AI; it depends on the model and task.
   - *Partly:* some records do, but fewer than the minimum. The review says
     how many (e.g. "312 of 900 single-organism subjects") and which fields
     not every record has.
   - *Doesn't meet your needs:* none do.

   One button removes the projects that don't meet your needs, and each
   project can also be unticked by hand. If a project and one of its
   sub-projects are both in the basket, the sub-project is counted once,
   inside its parent;
4. **export**, generated in the browser session with nothing stored on the
   server:
   - a manifest (CSV or JSON): program, project, record counts, qualifying
     counts, status, the C2M2 download URL, release date and the release
     zip's sha256;
   - Croissant 1.0 metadata: each program's release zip, the C2M2 tables in
     it and the columns behind the chosen needs, naming the selected
     projects. It passes `validate_croissant.py`;
   - a short Markdown summary report.

The basket is kept in the browser session (`st.session_state`), so it
survives switching pages but not closing the tab.

### Results (current releases, run 2026-09-29)

| Program | Release | Release date | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ExRNA (ERCC_DCC) | `CFDE08272026_C2M2.zip` | 2026-08-28 | 78 / 8,584 / 14,765 / 336,426 | 91 | 50 | 98 | 100 | 100 | n/a | 100 | 100 |
| HMP | `HMP_C2M2_2022-06-20_datapackage.zip` | 2022-06-20 (older release - may not reflect current metadata) | 24 / 7,903 / 51,873 / 251,136 | 80 | 86 | 50 | 59 | 100 | n/a | 88 | 100 |
| Kids First (KFDRC) | `2026Q4_C2M2_datapackage.zip` | 2026-09-16 | 45 / 39,156 / 111,300 / 1,356,814 | 78 | 62 | 50 | 58 | 100 | n/a | 100 | 97 |
| LINCS | `LINCS_C2M2_2023-09-18_datapackage.zip` | 2023-09-18 (older release - may not reflect current metadata) | 17 / 1,966 / 1,466,796 / 1,495,871 | 80 | 74 | 75 | 33 | 100 | n/a | 100 | 100 |
| Metabolomics Workbench (MW) | `MW_submission_packet_20260914.zip` | 2026-09-14 | 2,891 / 4,551 / 476,563 / 8,366 | 68 | 50 | 50 | 9 | 100 | n/a | 100 | 100 |
| SenNet | `sennet_c2m2_sep26.zip` | 2026-09-24 | 21 / 897 / 5,673 / 154,612 | 94 | 98 | 100 | 67 | 100 | n/a | 100 | 98 |
| SPARC | `C2M2_datapackage_20260916.zip` | 2026-09-17 | 78 / 4,597 / 9,212 / 175,471 | 88 | 96 | 96 | 33 | 100 | n/a | 100 | 100 |

Ethics is n/a for every program because of the C2M2 schema, not the
programs. Most common gaps across programs: **age** recorded for 24% of
single-organism subjects on average (0% in four of seven releases),
**sex** for 48%, and **persistent identifiers** on 48% of records. See
`output/readiness_comparison.md` for per-program numbers and data
quality notes.

### Tested on held-out programs
The checker was written and tuned on HMP, Kids First, LINCS, SenNet and
SPARC. To see whether it generalizes, it was then run - with no code
changes first - on two programs it had never seen, both current releases
under 100 MB: **ExRNA** (`CFDE08272026_C2M2.zip`, 2026-08-28, 16.9 MB) and
**Metabolomics Workbench** (`MW_submission_packet_20260914.zip`,
2026-09-14, 24.5 MB; its zip unpacks into a subfolder, which the checker
already handled).

- **It ran without errors** on both (about 3 and 5 seconds), and
  `--compare` with all seven programs completed.
- **Spot-checks:** nine numbers were re-derived with separate code (plain
  `csv`, not the checker's pandas logic), and all matched exactly.
  - Metabolomics Workbench: 125,384 of 476,563 biosamples with anatomy;
    8,364 of 8,366 files with a file format; 2,890 persistent IDs (all
    project DOIs).
  - ExRNA scores: 8,580 of 8,580 single-organism subjects with sex; 8,580
    with age; 350,633 of 359,853 records with a creation time.
  - ExRNA finder counts: 8,580 of 8,580 subjects, 14,761 of 14,765
    biosamples and 331,776 of 336,426 files meeting sex (and age).
- **No scoring bugs were found.** Two things looked suspicious, and
  inspecting the raw data showed the numbers were right but hid a detail:
  - ExRNA's sex is 100% recorded, but 1,223 of its single-organism
    subjects are coded `cfde_subject_sex:0` (*Indeterminate* in the CFDE
    vocabulary), and no subject is coded Male.
  - 1,508 of its recorded `age_at_enrollment` values are exactly 0.

  The checker now reports both situations for any program, as unscored
  data quality notes: Indeterminate sex codes, with the full list of sex
  values used, and ages of exactly 0 when they are at least 5% of the
  recorded ages. The scoring rule was not changed. Indeterminate is a valid
  C2M2 value, and Kids First also uses it for 348 subjects.
- **The original five programs' scores, dimensions and field coverage are
  unchanged.** The only difference for them is the new Indeterminate note
  for Kids First.
- **Held-out results:** ExRNA 91 overall, Metabolomics Workbench 68.
  Metabolomics Workbench records no sex or age for any subject. Its
  biosample `persistent_id` values are Metabolomics Workbench landing-page
  URLs, which are not on the persistent-identifier scheme list.

Two programs is a small test. Programs with very different layouts (for
example ones that describe files mainly through collections) may still
expose gaps.

### Limitations
- Simplified proxies, not an official implementation of the Bridge2AI
  criteria; they measure metadata coverage only, not data quality.
- One release per program. The HMP (2022) and LINCS (2023) releases are
  the current ones listed on the CFDE Workbench but are more than two
  years old, so they may not reflect those programs' current metadata.
- Some gaps come from the C2M2 schema rather than the programs: there are
  no consent or governance fields (Ethics is not assessable).
- Persistent identifiers are recognised by scheme only; nothing is
  resolved over the network, and only confirmed identifiers.org compact
  prefixes are recognised.
- Every check and every dimension is weighted equally, and programs can
  have different numbers of assessable dimensions, so overall scores are
  a rough summary.
- The Croissant check is structural (`validate_croissant.py`), because
  the official `mlcroissant` validator doesn't install here.
- Labels are checked for presence, not correctness.
- Scores on `data/` reflect a few hand-transcribed records per program,
  not the programs' metadata.

### How this relates to CFDE's existing assessment
CFDE already has an assessment tool for C2M2 datapackages,
[nih-cfde/c2m2-assessment](https://github.com/nih-cfde/c2m2-assessment)
(by Daniel J. B. Clarke). It runs FAIRshake-style rubrics against a
datapackage (`c2m2-assessment -i datapackage.zip -o results.json`) and
reports, per metric, a value with its numerator and denominator. Its
default rubric (`drc2024`) measures FAIRness: resolvable access URLs
(including live-testing a sample of up to 100 of them), persistent
identifiers on files, and about 34 coverage metrics, i.e. what share of
files, biosamples, subjects and projects are linked to data types,
formats, assays, anatomy, species, collections, and (added in 2024)
genes, substances, proteins and phenotypes. This project cites it but
does not use or copy its code (the repository has no license file).

This checker does not replace it. It asks a different question: the
Bridge2AI paper states that "simple conformance to FAIR ... Principles is
insufficient" for AI-readiness and defines seven dimensions, of which
FAIRness is one. This checker is a first attempt at simple, measurable
proxies for all seven from C2M2 metadata alone. Its FAIRness checks are
deliberately coarser than c2m2-assessment's, and some dimensions (Ethics
most of all) can only be partly measured, or not at all, from C2M2.

Differences to keep in mind when comparing numbers:
- c2m2-assessment's persistent-identifier metric counts any filled file
  `persistent_id`. This checker counts only the scheme list above, but
  also accepts an identifier in `access_url` — so SenNet (DOIs in
  `access_url`) scores higher here, and projects whose `persistent_id` is
  an ordinary web page score lower.
- c2m2-assessment treats duplicated access URLs as invalid and tests a
  sample for resolvability; this checker does neither.

## The hand-collected sample (`data/`)
Values in `data/*.tsv` were pulled by hand from CFDE's live Data Portal
(cfde.cloud/data/processed/entity/biosample/search), one detail page at a
time, and transcribed into the official schema. Current coverage:

- **5 real DCCs**: SPARC, Kids First, HMP (Human Microbiome Project),
  LINCS, SenNet
- **11 projects**, **13 subjects**, **14 biosamples**, **5 files**
- Real anatomy terms (neck, urinary bladder, cardiac nerve plexus, stomach,
  posterior fornix of vagina, feces, breast, brain)
- One real SPARC file record with filename, size, persistent ID, data
  type, assay type, and creation time. **Correction:** an earlier version
  of this README said this record also had a sha256 checksum, a file
  format, and an access URL. It does not -- the checksum and access URL
  were seen on the portal but never saved, and cannot be recovered, and
  no `file_format` value was recorded either. `file.tsv` has no `sha256`,
  `md5`, or `access_url` columns. Those fields are left missing rather
  than invented.
- **Correction (creation times):** two project rows (`cfde:sparc`
  `OT2OD023873` and `cfde:kidsfirst` `SD_YGVA0E1C`) previously had
  `creation_time` = `2026-01-15`, which was the date the rows were typed
  in, not a value from the portal. Those cells are now blank. The
  remaining creation times on real records were copied from portal
  pages. (Dates in the synthetic `demo:proj1` cluster are also made up,
  as is everything in that cluster.)
- One real disease association (`biosample_disease.tsv`): two separate
  LINCS biosamples (different drug treatments on the same MCF10A cell
  line) both link to "breast carcinoma" — a real example of the knowledge
  graph unifying disparate records around a shared concept.
- A handful of gaps we could NOT fill from the portal (subject sex/age,
  some anatomy fields) are left blank rather than invented.
- The portal displays human-readable labels (e.g. "Breast"), while real
  C2M2 submissions store ontology IDs, so the free-text values in this
  sample are a transcription artifact. The full releases in `data_real/`
  use term IDs throughout.

One synthetic demo cluster (`demo:proj1` / EEG study) is still in there
too, kept as a clean example of the schema mechanics. The checker
excludes it unless run with `--include-demo`.

## Files
- `schema/c2m2_field_reference.md` — real C2M2 column definitions.
- `data/*.tsv` — the hand-collected datapackage (real + one demo cluster).
- `releases.tsv` — source URL and release date of each full release in `data_real/`.
- `src/readiness_checker.py` — the AI-Readiness Checker.
- `app.py`, `.streamlit/config.toml` — the Streamlit web app.
- `src/c2m2_to_croissant.py` — converts the datapackage to Croissant JSON-LD.
- `src/build_graph.py` — builds the knowledge graph (every node carries a
  `dcc` attribute, so DCC-based queries are reliable rather than guessed
  from substrings).
- `src/query.py` — command-line query interface over the graph (see below).
- `src/validate_croissant.py` — structural Croissant spec validator.
- `src/term_labels.py` — human-readable ontology term labels.
- `output/croissant.json` — the generated AI-ready metadata file.
- `output/readiness_*.md|json` — checker reports (sample, per program,
  comparison); `output/readiness_comparison.json` is what the web app reads.

## Croissant, graph and queries
```
cd src
python3 c2m2_to_croissant.py
python3 build_graph.py
python3 validate_croissant.py

python3 query.py list --type biosample
python3 query.py search --anatomy brain
python3 query.py search --dcc sparc
python3 query.py connected biosample:QC9XMFT8 --hops 2
python3 query.py show biosample:QC9XMFT8
```

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
- `src/query.py` — a simple command-line interface: `connected`, `list`,
  `search`, `show`. Building it surfaced (and fixed) a real bug: the
  graph originally had no explicit `dcc` attribute on nodes, so a
  "search by DCC" query silently returned nothing for some DCCs.

## Next steps
- Write up the disease-unification example as a short case study for the
  outreach email — it's the clearest illustration of "why this matters."
- Draft the actual outreach email to Chen/AI.MED Lab, linking the repo.
