# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/kidsfirst/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/kidsfirst`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| KFDRC | 45 / 39,156 / 111,300 / 1,356,814 | 78 | 62 | 50 | 58 | 100 | n/a | 100 | 97 |

n/a = NOT ASSESSABLE (reason given in the program section).

## KFDRC (`kidsfirst:`)

**Overall: 78/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 45 project, 39156 subject, 111300 biosample, 1356814 file  
Release: `2026Q4_C2M2_datapackage.zip` (2026-09-16)

### FAIRness: 62/100 [persistent_ids 370371/1507315, ontology_ids 4191203/4191203]
- **Observation:** 1,136,944 of 1,507,315 records have no persistent identifier recorded (370,371 have one in persistent_id; 0 more files have one only in access_url; 45 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 25 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 1,136,944 of 1,507,315 records have no persistent identifier recorded (370,371 have one in persistent_id; 0 more files have one only in access_url; 45 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 4,191,203 of 4,191,203 ontology-field values use a term ID

### Provenance: 50/100 [creation_time 1507314/1507315, file_checksums 0/1356814]
- **Observation:** 1,356,814 of 1,356,814 files have no checksum recorded. Checksums let users verify that a downloaded file is exactly the one a model was trained on.
- `creation_time` = 100 -- Records (project/subject/biosample/file) with a creation_time: 1 of 1,507,315 records have no creation_time recorded
- `file_checksums` = 0 -- Files with a sha256 or md5 checksum: 1,356,814 of 1,356,814 files have no checksum recorded

### Characterization: 58/100 [subject_sex 39044/39156, subject_age 7349/39156, biosample_anatomy 60726/111300]
- **Observation:** 31,807 of 39,156 subjects have no age recorded (0 have age_at_enrollment; 7,349 more have age_at_sampling on a linked biosample). Recording age lets model developers check whether results differ across age groups, such as children and adults.
- `subject_sex` = 100 -- Single-organism subjects with sex recorded: 112 of 39,156 subjects have no sex recorded
- `subject_age` = 19 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 31,807 of 39,156 subjects have no age recorded (0 have age_at_enrollment; 7,349 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 55 -- Biosamples with anatomy recorded: 50,574 of 111,300 biosamples have no anatomy recorded
- *Info (not scored):* 154,157 disease associations in this release (114,888 in biosample_disease.tsv, 39,269 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 169/169]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 169 of 169 term IDs have a label (datapackage term table or portal); breakdown: 169 datapackage ('CL:0000057', 'DOID:0050545', 'DOID:0050567', 'DOID:0050668', 'DOID:0050834', ... (164 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 1356814/1356814]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 1,356,814 files have no persistent_id or access_url recorded

### Computability: 97/100 [file_format 1280973/1356814, croissant_valid 1/1]
- `file_format` = 94 -- Files with a file_format: 75,841 of 1,356,814 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- project.tsv: 45 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://www.ncbi.nlm.nih.gov (44), https://kidsfirstdrc.org (1).
- subject.tsv: 348 single-organism subject(s) have sex recorded as Indeterminate (cfde_subject_sex:0). This is a valid C2M2 value, so they count as having sex recorded, but it does not say which sex. All sex values used: Male 20,186, Female 18,510, Indeterminate 348.

