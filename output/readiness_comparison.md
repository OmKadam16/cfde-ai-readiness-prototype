# CFDE AI-Readiness Comparison

**These are simplified proxy measures for exploration, not an official evaluation.**

Each row is one program's current C2M2 release, downloaded from the CFDE Workbench (cfde.cloud/info/dcc/<program>). Scores are our own simplified proxies for the 7 AI-readiness dimensions in Clark T, et al. "AI-readiness Criteria for Biomedical Data." bioRxiv 2024. doi:10.1101/2024.10.23.619844 (first posted as "AI-readiness for Biomedical Data: Bridge2AI Recommendations"). They describe what the C2M2 metadata records -- not the quality of the underlying data or of each program's work -- and are meant to point at concrete, fixable gaps.

| Program | Release file | Release date | Records (project / subject / biosample / file) | Overall | FAIRness | Provenance | Characterization | Pre-model Explainability | Ethics | Sustainability | Computability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ERCC_DCC | `CFDE08272026_C2M2.zip` | 2026-08-28 | 78 / 8,584 / 14,765 / 336,426 | 91 | 50 | 98 | 100 | 100 | n/a | 100 | 100 |
| HMP | `HMP_C2M2_2022-06-20_datapackage.zip` | 2022-06-20 (older release - may not reflect current metadata) | 24 / 7,903 / 51,873 / 251,136 | 80 | 86 | 50 | 59 | 100 | n/a | 88 | 100 |
| KFDRC | `2026Q4_C2M2_datapackage.zip` | 2026-09-16 | 45 / 39,156 / 111,300 / 1,356,814 | 78 | 62 | 50 | 58 | 100 | n/a | 100 | 97 |
| LINCS | `LINCS_C2M2_2023-09-18_datapackage.zip` | 2023-09-18 (older release - may not reflect current metadata) | 17 / 1,966 / 1,466,796 / 1,495,871 | 80 | 74 | 75 | 33 | 100 | n/a | 100 | 100 |
| MW | `MW_submission_packet_20260914.zip` | 2026-09-14 | 2,891 / 4,551 / 476,563 / 8,366 | 68 | 50 | 50 | 9 | 100 | n/a | 100 | 100 |
| SenNet | `sennet_c2m2_sep26.zip` | 2026-09-24 | 21 / 897 / 5,673 / 154,612 | 94 | 98 | 100 | 67 | 100 | n/a | 100 | 98 |
| SPARC | `C2M2_datapackage_20260916.zip` | 2026-09-17 | 78 / 4,597 / 9,212 / 175,471 | 88 | 96 | 96 | 33 | 100 | n/a | 100 | 100 |

n/a = NOT ASSESSABLE. Ethics is n/a for every program because of the C2M2 schema, not the programs: C2M2 has no consent or governance fields. Overall = average of the dimensions that could be assessed. Releases older than 2 years are flagged: older release - may not reflect current metadata.

## Top 3 AI-readiness gaps across programs

1. **Single-organism subjects with an age recorded (age_at_enrollment, or age_at_sampling on a linked biosample)**: 24% coverage on average across 7 programs (ERCC_DCC 8,580/8,580 (100%); HMP 0/7,903 (0%); KFDRC 7,349/39,156 (19%); LINCS 0/275 (0%); MW 0/3,673 (0%); SenNet 462/897 (52%); SPARC 0/4,597 (0%)). Recording age lets model developers check whether results differ across age groups, such as children and adults.
2. **Single-organism subjects with sex recorded**: 48% coverage on average across 7 programs (ERCC_DCC 8,580/8,580 (100%); HMP 6,623/7,903 (84%); KFDRC 39,044/39,156 (100%); LINCS 0/275 (0%); MW 0/3,673 (0%); SenNet 450/897 (50%); SPARC 0/4,597 (0%)). Recording sex lets model developers check whether results hold for both sexes; NIH's Sex as a Biological Variable policy applies to human and animal studies alike.
3. **Records with a persistent ID (persistent_id field, or a persistent-identifier access_url on files)**: 48% coverage on average across 7 programs (ERCC_DCC 0/359,853 (0%); HMP 220,615/310,936 (71%); KFDRC 370,371/1,507,315 (25%); LINCS 1,454,753/2,964,650 (49%); MW 2,890/492,371 (1%); SenNet 154,612/161,203 (96%); SPARC 175,471/189,358 (93%)). Persistent identifiers let a training set be cited and re-assembled later, which supports reproducible models.

## Data quality notes (not scored)

**ERCC_DCC**
- subject.tsv: 1,223 single-organism subject(s) have sex recorded as Indeterminate (cfde_subject_sex:0). This is a valid C2M2 value, so they count as having sex recorded, but it does not say which sex. All sex values used: Female 7,357, Indeterminate 1,223.
- subject.tsv: 1,508 of 8,580 recorded age_at_enrollment values are exactly 0 (under one year old). If 0 is used for "unknown", leaving the field empty would keep it from being read as an age.
- biosample_from_subject.tsv: 3,446 of 14,818 recorded age_at_sampling values are exactly 0 (under one year old). If 0 is used for "unknown", leaving the field empty would keep it from being read as an age.

**HMP**
- None found by the checks we run.

**KFDRC**
- project.tsv: 45 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://www.ncbi.nlm.nih.gov (44), https://kidsfirstdrc.org (1).
- subject.tsv: 348 single-organism subject(s) have sex recorded as Indeterminate (cfde_subject_sex:0). This is a valid C2M2 value, so they count as having sex recorded, but it does not say which sex. All sex values used: Male 20,186, Female 18,510, Indeterminate 348.

**LINCS**
- project.tsv: 8 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://www.ncbi.nlm.nih.gov (4), https://www.lincsproject.org (1), https://clue.io (1), https://www.synapse.org (1), https://maayanlab.cloud (1).
- subject.tsv: 1,366 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://lincsportal.ccs.miami.edu (1,366).
- file.tsv: 41,118 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://s3.amazonaws.com (41,111), https://www.synapse.org (7).

**MW**
- biosample.tsv: 476,563 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://www.metabolomicsworkbench.org (476,563).

**SenNet**
- assay_type.tsv: 2 term ID(s) have leading/trailing whitespace ('OBI:0001271 ', 'OBI:0600020 '). As written they are not valid term IDs, and any tool that trims whitespace on one side of a join but not the other will fail to match them. The labels exist; this checker trims both sides before matching.
- 13,520 ontology-field value(s) in the data have leading/trailing whitespace: file.tsv assay_type: 13,520 (e.g. 'OBI:0001271 ', 'OBI:0600020 ')
- Persistent IDs present, but stored in access_url instead of the C2M2 persistent_id field (154,612 of 154,612 files; 3,233 distinct identifiers, e.g. 'https://doi.org/10.60586/SNT968.LLQQ.268', 'https://doi.org/10.60586/SNT693.RHFM.739', ... (3231 more)).

**SPARC**
- project.tsv: 78 persistent_id value(s) use a scheme that is not on the persistent-identifier list (DOI, identifiers.org, ARK, DRS, Handle, PURL), so they are not counted as persistent IDs. Schemes seen: https://projectreporter.nih.gov (71), https://sparc.science (5), https://cdmrp.health.mil (1), https://gtr.ukri.org (1).

Full per-program detail: `output/readiness_report_<program>.md`.
