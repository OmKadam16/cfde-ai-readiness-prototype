# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/metabolomics/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/metabolomics/MW_submission_packet_20260914`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| MW | 2,891 / 4,551 / 476,563 / 8,366 | 68 | 50 | 50 | 9 | 100 | n/a | 100 | 100 |

n/a = NOT ASSESSABLE (reason given in the program section).

## MW (`https://www.metabolomicsworkbench.org/`)

**Overall: 68/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 2891 project, 4551 subject, 476563 biosample, 8366 file  
Release: `MW_submission_packet_20260914.zip` (2026-09-14)

### FAIRness: 50/100 [persistent_ids 2890/492371, ontology_ids 419648/419648]
- **Observation:** 489,481 of 492,371 records have no persistent identifier recorded (2,890 have one in persistent_id; 0 more files have one only in access_url; 476,563 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 1 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 489,481 of 492,371 records have no persistent identifier recorded (2,890 have one in persistent_id; 0 more files have one only in access_url; 476,563 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 419,648 of 419,648 ontology-field values use a term ID

### Provenance: 50/100 [creation_time 0/492371, file_checksums 8366/8366]
- **Observation:** 492,371 of 492,371 records have no creation_time recorded. Timestamps help identify which version of the data a model used and make batch or time effects detectable.
- `creation_time` = 0 -- Records (project/subject/biosample/file) with a creation_time: 492,371 of 492,371 records have no creation_time recorded
- `file_checksums` = 100 -- Files with a sha256 or md5 checksum: 0 of 8,366 files have no checksum recorded

### Characterization: 9/100 [subject_sex 0/3673, subject_age 0/3673, biosample_anatomy 125384/476563]
- **Observation:** 3,673 of 3,673 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 3,673 of 3,673 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 3,673 of 3,673 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 26 -- Biosamples with anatomy recorded: 351,179 of 476,563 biosamples have no anatomy recorded
- *Info (not scored):* 818 cell-line and 38 synthetic and 22 microbiome subjects excluded from sex/age checks (these checks apply to single-organism subjects, human or animal)
- *Info (not scored):* 2,525 disease associations in this release (0 in biosample_disease.tsv, 2,525 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 459/459]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 459 of 459 term IDs have a label (datapackage term table or portal); breakdown: 459 datapackage ('CL:0000000', 'CL:0000019', 'CL:0000034', 'CL:0000037', 'CL:0000047', ... (454 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 8366/8366]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 8,366 files have no persistent_id or access_url recorded

### Computability: 100/100 [file_format 8364/8366, croissant_valid 1/1]
- `file_format` = 100 -- Files with a file_format: 2 of 8,366 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- biosample.tsv: 476,563 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://www.metabolomicsworkbench.org (476,563).

