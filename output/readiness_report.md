# CFDE AI-Readiness Report

> **DEMO ON A SMALL HAND-COLLECTED SAMPLE - these scores reflect this sample, not the full program's metadata.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| hmp | 1 / 2 / 2 / 0 | 11 | 0 | 0 | 33 | n/a | n/a | n/a | n/a |
| kidsfirst | 3 / 3 / 3 / 1 | 17 | 25 | 15 | 11 | 0 | n/a | 0 | 50 |
| lincs | 2 / 2 / 3 / 1 | 17 | 0 | 12 | 22 | n/a | n/a | 0 | 50 |
| sennet | 1 / 1 / 1 / 0 | 22 | 0 | 33 | 33 | n/a | n/a | n/a | n/a |
| sparc | 3 / 3 / 3 / 1 | 50 | 15 | 5 | 33 | 100 | n/a | 100 | 50 |

n/a = NOT ASSESSABLE (reason given in the program section).

## hmp (`cfde:hmp`)

**Overall: 11/100** (average of the 3 of 7 dimensions that could be assessed)  
Records: 1 project, 2 subject, 2 biosample, 0 file

### FAIRness: 0/100 [persistent_ids 0/5, ontology_ids 0/2]
- **Observation:** 5 of 5 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 2 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 0 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 5 of 5 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 2 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 0 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 0 of 2 ontology-field values use a term ID; free text found: 'Feces', 'posterior fornix of vagina'
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Provenance: 0/100 [creation_time 0/5]
- **Observation:** 5 of 5 records have no creation_time recorded. Timestamps help identify which version of the data a model used and make batch or time effects detectable.
- `creation_time` = 0 -- Records (project/subject/biosample/file) with a creation_time: 5 of 5 records have no creation_time recorded
- `file_checksums` = skipped (nothing to measure) -- Files with a sha256 or md5 checksum: 0 of 0 files have no checksum recorded (file.tsv has no sha256 or md5 column at all)

### Characterization: 33/100 [subject_sex 0/2, subject_age 0/2, biosample_anatomy 2/2]
- **Observation:** 2 of 2 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 2 of 2 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 2 of 2 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 100 -- Biosamples with anatomy recorded: 0 of 2 biosamples have no anatomy recorded
- *Info (not scored):* 2 subject(s) have no granularity recorded and are counted as single organisms
- *Info (not scored):* 0 disease associations in this release (0 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: NOT ASSESSABLE
- Why not assessable: This program uses no ontology term IDs -- its ontology fields hold free text (see FAIRness), so there are no codes to look up labels for. The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.
- `labeled_terms` = skipped (nothing to measure) -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 0 of 0 term IDs have a label (datapackage term table or portal)

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: NOT ASSESSABLE
- Why not assessable: This program has no file records, so there is nothing whose long-term access can be checked.
- `file_locatable` = skipped (nothing to measure) -- Files with a persistent_id or access_url: 0 of 0 files have no persistent_id or access_url recorded

### Computability: NOT ASSESSABLE
- Why not assessable: This program has no file records, so there is no data for a model to load (for reference: croissant generated for this program's records and passed validate_croissant.py).

### Data quality notes (not scored)
- biosample.tsv: 2 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://cfde.cloud (2).

## kidsfirst (`cfde:kidsfirst`)

**Overall: 17/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 3 project, 3 subject, 3 biosample, 1 file

### FAIRness: 25/100 [persistent_ids 0/10, ontology_ids 1/2]
- **Observation:** 10 of 10 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 3 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 0 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 10 of 10 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 3 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 50 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 1 of 2 ontology-field values use a term ID; free text found: 'neck'
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Provenance: 15/100 [creation_time 3/10, file_checksums 0/1]
- **Observation:** 1 of 1 files have no checksum recorded (file.tsv has no sha256 or md5 column at all). Checksums let users verify that a downloaded file is exactly the one a model was trained on.
- `creation_time` = 30 -- Records (project/subject/biosample/file) with a creation_time: 7 of 10 records have no creation_time recorded
- `file_checksums` = 0 -- Files with a sha256 or md5 checksum: 1 of 1 files have no checksum recorded (file.tsv has no sha256 or md5 column at all)

### Characterization: 11/100 [subject_sex 0/3, subject_age 0/3, biosample_anatomy 1/3]
- **Observation:** 3 of 3 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 3 of 3 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 3 of 3 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 33 -- Biosamples with anatomy recorded: 2 of 3 biosamples have no anatomy recorded
- *Info (not scored):* 3 subject(s) have no granularity recorded and are counted as single organisms
- *Info (not scored):* 0 disease associations in this release (0 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 0/100 [labeled_terms 0/1]
- **Observation:** 0 of 1 term IDs have a label (datapackage term table or portal); breakdown: 1 inferred ('OBI:0002117'). Human-readable labels let reviewers sanity-check what a model's input features mean.
- `labeled_terms` = 0 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 0 of 1 term IDs have a label (datapackage term table or portal); breakdown: 1 inferred ('OBI:0002117')
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 0/100 [file_locatable 0/1]
- **Observation:** 1 of 1 files have no persistent_id or access_url recorded. A persistent ID or access URL on each file keeps it findable for the models and benchmarks that depend on it.
- `file_locatable` = 0 -- Files with a persistent_id or access_url: 1 of 1 files have no persistent_id or access_url recorded

### Computability: 50/100 [file_format 0/1, croissant_valid 1/1]
- **Observation:** 1 of 1 files have no file_format recorded. A declared file format lets pipelines parse each file without guessing.
- `file_format` = 0 -- Files with a file_format: 1 of 1 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- project.tsv: 1 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://kidsfirstdrc.org (1).
- biosample.tsv: 2 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://cfde.cloud (2).

## lincs (`cfde:lincs`)

**Overall: 17/100** (average of the 5 of 7 dimensions that could be assessed)  
Records: 2 project, 2 subject, 3 biosample, 1 file

### FAIRness: 0/100 [persistent_ids 0/8, ontology_ids 0/7]
- **Observation:** 8 of 8 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 2 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 0 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 8 of 8 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 2 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 0 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 0 of 7 ontology-field values use a term ID; free text found: 'Breast', 'breast carcinoma', 'maintaining cell culture'
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Provenance: 12/100 [creation_time 2/8, file_checksums 0/1]
- **Observation:** 1 of 1 files have no checksum recorded (file.tsv has no sha256 or md5 column at all). Checksums let users verify that a downloaded file is exactly the one a model was trained on.
- `creation_time` = 25 -- Records (project/subject/biosample/file) with a creation_time: 6 of 8 records have no creation_time recorded
- `file_checksums` = 0 -- Files with a sha256 or md5 checksum: 1 of 1 files have no checksum recorded (file.tsv has no sha256 or md5 column at all)

### Characterization: 22/100 [subject_sex 0/2, subject_age 0/2, biosample_anatomy 2/3]
- **Observation:** 2 of 2 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 2 of 2 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 2 of 2 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 67 -- Biosamples with anatomy recorded: 1 of 3 biosamples have no anatomy recorded
- *Info (not scored):* 2 subject(s) have no granularity recorded and are counted as single organisms
- *Info (not scored):* 2 disease associations in this release (2 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: NOT ASSESSABLE
- Why not assessable: This program uses no ontology term IDs -- its ontology fields hold free text (see FAIRness), so there are no codes to look up labels for. The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.
- `labeled_terms` = skipped (nothing to measure) -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 0 of 0 term IDs have a label (datapackage term table or portal)

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 0/100 [file_locatable 0/1]
- **Observation:** 1 of 1 files have no persistent_id or access_url recorded. A persistent ID or access URL on each file keeps it findable for the models and benchmarks that depend on it.
- `file_locatable` = 0 -- Files with a persistent_id or access_url: 1 of 1 files have no persistent_id or access_url recorded

### Computability: 50/100 [file_format 0/1, croissant_valid 1/1]
- **Observation:** 1 of 1 files have no file_format recorded. A declared file format lets pipelines parse each file without guessing.
- `file_format` = 0 -- Files with a file_format: 1 of 1 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- biosample.tsv: 2 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://cfde.cloud (2).

## sennet (`cfde:sennet`)

**Overall: 22/100** (average of the 3 of 7 dimensions that could be assessed)  
Records: 1 project, 1 subject, 1 biosample, 0 file

### FAIRness: 0/100 [persistent_ids 0/3, ontology_ids 0/2]
- **Observation:** 3 of 3 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 0 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 0 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 3 of 3 records have no persistent identifier recorded (0 have one in persistent_id; 0 more files have one only in access_url; 0 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 0 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 0 of 2 ontology-field values use a term ID; free text found: 'Brain', 'collecting specimen from organism'
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Provenance: 33/100 [creation_time 1/3]
- **Observation:** 2 of 3 records have no creation_time recorded. Timestamps help identify which version of the data a model used and make batch or time effects detectable.
- `creation_time` = 33 -- Records (project/subject/biosample/file) with a creation_time: 2 of 3 records have no creation_time recorded
- `file_checksums` = skipped (nothing to measure) -- Files with a sha256 or md5 checksum: 0 of 0 files have no checksum recorded (file.tsv has no sha256 or md5 column at all)

### Characterization: 33/100 [subject_sex 0/1, subject_age 0/1, biosample_anatomy 1/1]
- **Observation:** 1 of 1 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 1 of 1 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 1 of 1 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 100 -- Biosamples with anatomy recorded: 0 of 1 biosamples have no anatomy recorded
- *Info (not scored):* 1 subject(s) have no granularity recorded and are counted as single organisms
- *Info (not scored):* 0 disease associations in this release (0 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: NOT ASSESSABLE
- Why not assessable: This program uses no ontology term IDs -- its ontology fields hold free text (see FAIRness), so there are no codes to look up labels for. The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.
- `labeled_terms` = skipped (nothing to measure) -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 0 of 0 term IDs have a label (datapackage term table or portal)

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: NOT ASSESSABLE
- Why not assessable: This program has no file records, so there is nothing whose long-term access can be checked.
- `file_locatable` = skipped (nothing to measure) -- Files with a persistent_id or access_url: 0 of 0 files have no persistent_id or access_url recorded

### Computability: NOT ASSESSABLE
- Why not assessable: This program has no file records, so there is no data for a model to load (for reference: croissant generated for this program's records and passed validate_croissant.py).

### Data quality notes (not scored)
- None found by the checks we run.

## sparc (`cfde:sparc`)

**Overall: 50/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 3 project, 3 subject, 3 biosample, 1 file

### FAIRness: 15/100 [persistent_ids 1/10, ontology_ids 1/5]
- **Observation:** 9 of 10 records have no persistent identifier recorded (1 have one in persistent_id; 0 more files have one only in access_url; 3 persistent_id values use a non-persistent scheme and are not counted). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.
- `persistent_ids` = 10 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 9 of 10 records have no persistent identifier recorded (1 have one in persistent_id; 0 more files have one only in access_url; 3 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 20 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 1 of 5 ontology-field values use a term ID; free text found: 'Image', 'cardiac nerve plexus', 'stomach', 'urinary bladder'
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Provenance: 5/100 [creation_time 1/10, file_checksums 0/1]
- **Observation:** 1 of 1 files have no checksum recorded (file.tsv has no sha256 or md5 column at all). Checksums let users verify that a downloaded file is exactly the one a model was trained on.
- `creation_time` = 10 -- Records (project/subject/biosample/file) with a creation_time: 9 of 10 records have no creation_time recorded
- `file_checksums` = 0 -- Files with a sha256 or md5 checksum: 1 of 1 files have no checksum recorded (file.tsv has no sha256 or md5 column at all)

### Characterization: 33/100 [subject_sex 0/3, subject_age 0/3, biosample_anatomy 3/3]
- **Observation:** 3 of 3 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 3 of 3 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 3 of 3 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 100 -- Biosamples with anatomy recorded: 0 of 3 biosamples have no anatomy recorded
- *Info (not scored):* 3 subject(s) have no granularity recorded and are counted as single organisms
- *Info (not scored):* 0 disease associations in this release (0 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 1/1]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 1 of 1 term IDs have a label (datapackage term table or portal); breakdown: 1 portal ('OBI:0002119')
- *Note:* The CFDE portal UI displays human-readable labels, while real C2M2 submissions store ontology IDs, so if this data was hand-transcribed from the portal, free-text values may be a transcription artifact rather than a gap in the program's own metadata.

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 1/1]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 1 files have no persistent_id or access_url recorded

### Computability: 50/100 [file_format 0/1, croissant_valid 1/1]
- **Observation:** 1 of 1 files have no file_format recorded. A declared file format lets pipelines parse each file without guessing.
- `file_format` = 0 -- Files with a file_format: 1 of 1 files have no file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- project.tsv: 1 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://commonfund.nih.gov (1).
- biosample.tsv: 2 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://cfde.cloud (2).

