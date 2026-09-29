# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/lincs/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/lincs`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| LINCS | 17 / 1,966 / 1,466,796 / 1,495,871 | 80 | 74 | 75 | 33 | 100 | n/a | 100 | 100 |

n/a = NOT ASSESSABLE (reason given in the program section).

## LINCS (`https://www.lincsproject.org/`)

**Overall: 80/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 17 project, 1966 subject, 1466796 biosample, 1495871 file  
Release: `LINCS_C2M2_2023-09-18_datapackage.zip` (2023-09-18) - older release - may not reflect current metadata

### FAIRness: 74/100 [persistent_ids 1454753/2964650, ontology_ids 10154278/10154278]
- `persistent_ids` = 49 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 1,509,897 of 2,964,650 records have no persistent identifier recorded (1,454,753 have one in persistent_id; 0 more files have one only in access_url; 42,492 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 10154278 of 10154278 ontology-field values use a term ID

### Provenance: 75/100 [creation_time 1496690/2964650, file_checksums 1495871/1495871]
- `creation_time` = 50 -- Records (project/subject/biosample/file) with a creation_time: 1,467,960 of 2,964,650 records have no a creation_time recorded
- `file_checksums` = 100 -- Files with a sha256 or md5 checksum: 0 of 1,495,871 files have no a checksum recorded

### Characterization: 33/100 [subject_sex 0/275, subject_age 0/275, biosample_anatomy 1451606/1466796]
- **Observation:** 275 of 275 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 275 of 275 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 275 of 275 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 99 -- Biosamples with anatomy recorded: 15,190 of 1,466,796 biosamples have no anatomy recorded
- *Info (not scored):* 1,527 cell-line and 164 synthetic subjects excluded from sex/age checks (these checks apply to single-organism subjects, human or animal)
- *Info (not scored):* 1,211,291 disease associations in this release (1211094 in biosample_disease.tsv, 197 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 131/131]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 131 of 131 term IDs have a label (datapackage term table or portal); breakdown: 131 datapackage ('DOID:0060058', 'DOID:0070004', 'DOID:10286', 'DOID:1107', 'DOID:1240', ... (126 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 1495871/1495871]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 1,495,871 files have no both a persistent_id and an access_url recorded

### Computability: 100/100 [file_format 1495871/1495871, croissant_valid 1/1]
- `file_format` = 100 -- Files with a file_format: 0 of 1,495,871 files have no a file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- project.tsv: 8 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://www.ncbi.nlm.nih.gov (4), https://www.lincsproject.org (1), https://clue.io (1), https://www.synapse.org (1), https://maayanlab.cloud (1).
- subject.tsv: 1,366 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://lincsportal.ccs.miami.edu (1,366).
- file.tsv: 41,118 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://s3.amazonaws.com (41,111), https://www.synapse.org (7).

