# C2M2 core table field reference
Source: https://cfde.cloud/data/documentation/C2M2/ (official CFDE Data Portal docs)

## project.tsv
- id_namespace (string) - top-level data space identifier
- local_id (string) - unique id within namespace
- persistent_id (string) - permanent resolvable URI
- creation_time (ISO 8601)
- abbreviation (string, max 10 chars)
- name (string)
- description (string)

## subject.tsv
- id_namespace, local_id, project_id_namespace, project_local_id
- persistent_id, creation_time
- granularity (CFDE CV term - e.g. single organism)
- sex (enum)
- ethnicity (enum)
- age_at_enrollment (number, years)

## biosample.tsv
- id_namespace, local_id, project_id_namespace, project_local_id
- persistent_id, creation_time
- sample_prep_method (OBI term)
- anatomy (UBERON/CL/CLO term)
- biofluid (UBERON/InterLex term)

## file.tsv
- id_namespace, local_id, project_id_namespace, project_local_id
- persistent_id, creation_time
- size_in_bytes, uncompressed_size_in_bytes, sha256, md5
- filename, file_format (EDAM term), compression_format, data_type (EDAM term)
- assay_type (OBI term), analysis_type (OBI term), mime_type
- bundle_collection_id_namespace, bundle_collection_local_id
- dbgap_study_id, access_url

## Association tables we need (link entities together)
- biosample_from_subject: biosample_id_namespace, biosample_local_id, subject_id_namespace, subject_local_id
- file_describes_biosample: file_id_namespace, file_local_id, biosample_id_namespace, biosample_local_id
- file_describes_subject: file_id_namespace, file_local_id, subject_id_namespace, subject_local_id
