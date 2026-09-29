# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/hmp/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/hmp/merged/data`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| HMP | 24 / 7,903 / 51,873 / 251,136 | 80 | 86 | 50 | 59 | 100 | n/a | 88 | 100 |

n/a = NOT ASSESSABLE (reason given in the program section).

## HMP (`tag:hmpdacc.org,2022-04-04:`)

**Overall: 80/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 24 project, 7903 subject, 51873 biosample, 251136 file  
Release: `HMP_C2M2_2022-06-20_datapackage.zip` (2022-06-20) - older release - may not reflect current metadata

### FAIRness: 86/100 [persistent_ids 220615/310936, ontology_ids 804939/804939]
- `persistent_ids` = 71 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 90,321 of 310,936 records have no persistent identifier recorded (220,615 have one in persistent_id; 0 more files have one only in access_url; 0 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 804,939 of 804,939 ontology-field values use a term ID

### Provenance: 50/100 [creation_time 0/310936, file_checksums 251136/251136]
- **Observation:** 310,936 of 310,936 records have no creation_time recorded. Timestamps help identify which version of the data a model used and make batch or time effects detectable.
- `creation_time` = 0 -- Records (project/subject/biosample/file) with a creation_time: 310,936 of 310,936 records have no creation_time recorded
- `file_checksums` = 100 -- Files with a sha256 or md5 checksum: 0 of 251,136 files have no checksum recorded

### Characterization: 59/100 [subject_sex 6623/7903, subject_age 0/7903, biosample_anatomy 48510/51873]
- **Observation:** 7,903 of 7,903 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample). Recording age lets model developers check whether results differ across age groups, such as children and adults.
- `subject_sex` = 84 -- Single-organism subjects with sex recorded: 1,280 of 7,903 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 7,903 of 7,903 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 94 -- Biosamples with anatomy recorded: 3,363 of 51,873 biosamples have no anatomy recorded
- *Info (not scored):* 3,023 disease associations in this release (2,531 in biosample_disease.tsv, 492 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 146/146]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 146 of 146 term IDs have a label (datapackage term table or portal); breakdown: 146 datapackage ('DOID:4914', 'DOID:5295', 'DOID:8677', 'DOID:8778', 'DOID:8893', ... (141 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 88/100 [file_locatable 220615/251136]
- `file_locatable` = 88 -- Files with a persistent_id or access_url: 30,521 of 251,136 files have no persistent_id or access_url recorded

### Computability: 100/100 [file_format 251136/251136, croissant_valid 1/1]
- `file_format` = 100 -- Files with a file_format: 0 of 251,136 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- None found by the checks we run.

