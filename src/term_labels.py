"""
term_labels.py

Human-readable labels for the ontology term IDs used in our data.tsv files.
This addresses a real, named gap: raw IDs like "OBI:0002117" are meaningless
to a person (or to most AI tools) without a lookup -- C2M2 stores only the
ID, not the label.

Honesty note on sourcing: an attempt to pull authoritative definitions from
EBI's Ontology Lookup Service (OLS) API got rate-limited mid-session, so
these labels are sourced two different ways, and each is marked which:

  "portal"   = read directly off a real CFDE Data Portal page (as reliable
               as it gets -- it's literally what the DCC's own metadata says)
  "inferred" = reasoned from context (e.g. the file was named "amplicon..."
               and CFDE's own description text named this exact term), but
               not independently confirmed against the ontology's own
               canonical definition
  "placeholder" = used only in our synthetic demo cluster (demo:proj1) --
               these codes were made up for illustration and are NOT
               claimed to be accurate to the real ontology. Flagged
               honestly rather than presented as verified.

A real (non-prototype) version of this tool would call the OLS API
properly (with retry/backoff) instead of hand-maintaining this dict.
"""

TERM_LABELS = {
    "OBI:0002119": {
        "label": "microscopy assay",
        "source": "portal",
    },
    "OBI:0002117": {
        "label": "amplicon sequencing assay",
        "source": "inferred",
        "note": "Portal's own description text named this exact term on a file "
                "labeled 'amplicon37_gene_list.tsv'; not independently confirmed "
                "against OBI's canonical definition.",
    },
    "UBERON:0000955": {
        "label": "brain",
        "source": "inferred",
        "note": "Confirmed via public ontology search results; not pulled live "
                "from OLS due to rate limiting this session.",
    },
    "EDAM:format_3752": {
        "label": "CSV",
        "source": "placeholder",
        "note": "Used only in the synthetic demo cluster (demo:proj1) -- not a "
                "value pulled from a real DCC record.",
    },
    "EDAM:data_3858": {
        "label": "(unverified -- placeholder demo value)",
        "source": "placeholder",
        "note": "Used only in the synthetic demo cluster; meaning not confirmed.",
    },
    "OBI:0600016": {
        "label": "(unverified -- placeholder demo value)",
        "source": "placeholder",
        "note": "Used only in the synthetic demo cluster; meaning not confirmed.",
    },
    "OBI:0000487": {
        "label": "(unverified -- placeholder demo value)",
        "source": "placeholder",
        "note": "Used only in the synthetic demo cluster; meaning not confirmed.",
    },
}


def label_for(term_id: str) -> str:
    entry = TERM_LABELS.get(term_id)
    if entry is None:
        return term_id
    return f"{term_id} ({entry['label']})"
