# CFDE AI-Readiness Report

> **FULL C2M2 DATAPACKAGE from data_real/sparc/ - these scores reflect this one submitted release, measured with our simplified proxies.**

*These are simplified proxy measures for exploration, not an official evaluation.*

Scores use our own simplified, measurable proxies for the 7 AI-readiness dimensions in
Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations").
They describe what the C2M2 metadata records, not the quality of the program's data or work.
Every score is computed from the C2M2 records in `/Users/omkadam/Documents/Om Kadam/PROJECTS/cfde-project/data_real/sparc`; see `src/readiness_checker.py`.

## Summary

| Program | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|
| SPARC | 78 / 4,597 / 9,212 / 175,471 | 88 | 96 | 96 | 33 | 100 | n/a | 100 | 100 |

n/a = NOT ASSESSABLE (reason given in the program section).

## SPARC (`SPARC.file:, SPARC.project:, SPARC.sample:, SPARC.subject:, SPARC:`)

**Overall: 88/100** (average of the 6 of 7 dimensions that could be assessed)  
Records: 78 project, 4597 subject, 9212 biosample, 175471 file  
Release: `C2M2_datapackage_20260916.zip` (2026-09-17)

### FAIRness: 96/100 [persistent_ids 175471/189358, ontology_ids 509813/509813]
- `persistent_ids` = 93 -- Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files): 13,887 of 189,358 records have no persistent identifier recorded (175,471 have one in persistent_id; 0 more files have one only in access_url; 78 persistent_id values use a non-persistent scheme and are not counted)
- `ontology_ids` = 100 -- Ontology-coded field values that are real term IDs (PREFIX:ID), not free text: 509813 of 509813 ontology-field values use a term ID

### Provenance: 96/100 [creation_time 173350/189358, file_checksums 175471/175471]
- `creation_time` = 92 -- Records (project/subject/biosample/file) with a creation_time: 16,008 of 189,358 records have no a creation_time recorded
- `file_checksums` = 100 -- Files with a sha256 or md5 checksum: 0 of 175,471 files have no a checksum recorded

### Characterization: 33/100 [subject_sex 0/4597, subject_age 0/4597, biosample_anatomy 9206/9212]
- **Observation:** 4,597 of 4,597 subjects have no sex recorded. Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
- `subject_sex` = 0 -- Single-organism subjects with sex recorded: 4,597 of 4,597 subjects have no sex recorded
- `subject_age` = 0 -- Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample): 4,597 of 4,597 subjects have no age recorded (0 have age_at_enrollment; 0 more have age_at_sampling on a linked biosample)
- `biosample_anatomy` = 100 -- Biosamples with anatomy recorded: 6 of 9,212 biosamples have no anatomy recorded
- *Info (not scored):* 0 disease associations in this release (0 in biosample_disease.tsv, 0 in subject_disease.tsv) - not scored, since not every program studies a disease

### Pre-model Explainability: 100/100 [labeled_terms 100/100]
- `labeled_terms` = 100 -- Distinct ontology term IDs with a human-readable label (from the package's own term tables, or portal-sourced in term_labels.py): 100 of 100 term IDs have a label (datapackage term table or portal); breakdown: 100 datapackage ('OBI:0000185', 'OBI:0000424', 'OBI:0000454', 'OBI:0001271', 'OBI:0001980', ... (95 more))

### Ethics: NOT ASSESSABLE
- Why not assessable: This reflects the C2M2 schema, not the program: C2M2 has no fields for consent, data use limitations, IRB approval, or governance, so ethics cannot be measured from C2M2 metadata. Each program's own data use documentation is the place to look.

### Sustainability: 100/100 [file_locatable 175471/175471]
- `file_locatable` = 100 -- Files with a persistent_id or access_url: 0 of 175,471 files have no both a persistent_id and an access_url recorded

### Computability: 100/100 [file_format 173792/175471, croissant_valid 1/1]
- `file_format` = 99 -- Files with a file_format: 1,679 of 175,471 files have no a file_format recorded
- `croissant_valid` = 100 -- Croissant metadata generated and passes validate_croissant.py (yes=100 / no=0): Croissant generated for this program's records and passed validate_croissant.py

### Data quality notes (not scored)
- project.tsv: 78 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://projectreporter.nih.gov (71), https://sparc.science (5), https://cdmrp.health.mil (1), https://gtr.ukri.org (1).

