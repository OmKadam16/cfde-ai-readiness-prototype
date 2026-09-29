# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/sennet/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/sennet`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| SenNet | 21 / 897 / 5,673 / 154,612 | 94 | 98 | 100 | 67 | 100 | n/a | 100 | 98 |

n/a = NOT ASSESSABLE (reason given in the program section).

## SenNet (`tag:sennetconsortium.org,2025:`)

**Overall: 94/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 21 project, 897 subject, 5673 biosample, 154612 file  
Release: `sennet_c2m2_sep26.zip` (2026-09-24)

### FAIRness: 98/100 [persistent_ids 154612/161203, ontology_ids 628947/628947]
- `persistent_ids` = 96 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 6,591 of 161,203 records have no persistent identifier recorded (0 have one in persistent_id; 154,612 more files have one only in access_url; 0 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 628947 of 628947 ontology-field values use a term ID

### Provenance: 100/100 [creation_time 161182/161203, file_checksums 154612/154612]
- `creation_time` = 100 -- Records (project/subject/biosample/file) with a creation_time: 21 of 161,203 records have no a creation_time recorded
- `file_checksums` = 100 -- Files with a sha256 or md5 checksum: 0 of 154,612 files have no a checksum recorded

### Characterization: 67/100 [subject_sex 450/897, subject_age 462/897, biosample_anatomy 5669/5673]
- **Observation:** 447 of 897 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 50 -- Single-organism subjects with sex recorded: 447 of 897 subjects have no sex recorded
- `subject_age` = 52 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 435 of 897 subjects have no age recorded (462 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 100 -- Biosamples with anatomy recorded: 4 of 5,673 biosamples have no anatomy recorded
- *Info (not scored):* 0 disease associations in this release (0 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 76/76]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 76 of 76 term IDs have a label (datapackage term table or portal); breakdown: 76 datapackage ('IAO:0000572', 'OBI:0000227', 'OBI:0000711', 'OBI:0001007', 'OBI:0001028', ... (71 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 154612/154612]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 154,612 files have no both a persistent_id and an access_url recorded

### Computability: 98/100 [file_format 146936/154612, croissant_valid 1/1]
- `file_format` = 95 -- Files with a file_format: 7,676 of 154,612 files have no a file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- assay_type.tsv: 2 term ID(s) have leading/trailing whitespace ('OBI:0001271 ', 'OBI:0600020 '). As written they are not valid term IDs, and any tool that trims whitespace on one side of a join but not the other will fail to match them. The labels exist; this checker trims both sides before matching.
- 13,520 ontology-field value(s) in the data have leading/trailing whitespace: file.tsv assay_type: 13,520 (e.g. 'OBI:0001271 ', 'OBI:0600020 ')
- Persistent IDs present, but stored in access_url instead of the C2M2 persistent_id field (154,612 of 154,612 files; 3,233 distinct identifiers, e.g. 'https://doi.org/10.60586/SNT968.LLQQ.268', 'https://doi.org/10.60586/SNT693.RHFM.739', ... (3231 more)).

