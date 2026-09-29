# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/exrna/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/exrna`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| ERCC_DCC | 78 / 8,584 / 14,765 / 336,426 | 91 | 50 | 98 | 100 | 100 | n/a | 100 | 100 |

n/a = NOT ASSESSABLE (reason given in the program section).

## ERCC_DCC (`ERCC-exRNA`)

**Overall: 91/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 78 project, 8584 subject, 14765 biosample, 336426 file  
Release: `CFDE08272026_C2M2.zip` (2026-08-28)

### FAIRness: 50/100 [persistent_ids 0/359853, ontology_ids 1428946/1428946]
- **Observation:** 359,853 of 359,853 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 0 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 0 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 359,853 of 359,853 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 0 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 1,428,946 of 1,428,946 ontology-field values use a term ID

### Provenance: 98/100 [creation_time 350633/359853, file_checksums 336426/336426]
- `creation_time` = 97 -- Records (project/subject/biosample/file) with a creation_time: 9,220 of 359,853 records have no creation_time recorded
- `file_checksums` = 100 -- Files with a sha256 or md5 checksum: 0 of 336,426 files have no checksum recorded

### Characterization: 100/100 [subject_sex 8580/8580, subject_age 8580/8580, biosample_anatomy 14765/14765]
- `subject_sex` = 100 -- Single-organism subjects with sex recorded: 0 of 8,580 subjects have no sex recorded
- `subject_age` = 100 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 0 of 8,580 subjects have no age recorded (8,580 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 100 -- Biosamples with anatomy recorded: 0 of 14,765 biosamples have no anatomy recorded
- *Info (not scored):* 4 cell-line subjects excluded from sex/age checks (these checks apply to single-organism subjects, human or animal)
- *Info (not scored):* 4,961 disease associations in this release (3,125 in biosample_disease.tsv, 1,836 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 124/124]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 124 of 124 term IDs have a label (datapackage term table or portal); breakdown: 124 datapackage ('CL:0000081', 'CL:0000125', 'DOID:0080199', 'DOID:0080832', 'DOID:0081445', ... (119 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 336426/336426]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 336,426 files have no persistent_id or access_url recorded

### Computability: 100/100 [file_format 336426/336426, croissant_valid 1/1]
- `file_format` = 100 -- Files with a file_format: 0 of 336,426 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- subject.tsv: 1,223 single-organism subject(s) have sex recorded as Indeterminate (cfde_subject_sex:0). This is a valid C2M2 value, so they count as having sex recorded, but it does not say which sex. All sex values used: Female 7,357, Indeterminate 1,223.
- subject.tsv: 1,508 of 8,580 recorded age_at_enrollment values are exactly 0 (under one year old). If 0 is used for "unknown", leaving the field empty would keep it from being read as an age.
- biosample_from_subject.tsv: 3,446 of 14,818 recorded age_at_sampling values are exactly 0 (under one year old). If 0 is used for "unknown", leaving the field empty would keep it from being read as an age.

