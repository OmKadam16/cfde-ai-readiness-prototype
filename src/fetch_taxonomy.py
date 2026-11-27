"""
fetch_taxonomy.py -- builds taxonomy_lineage.tsv: for every NCBI taxon the packages in data_real/ use,
its name, rank and whether it is an animal (Metazoa), from NCBI Taxonomy (E-utilities efetch).

    python3 src/fetch_taxonomy.py

The checker uses taxonomy_lineage.tsv to tell humans, other animals and other organisms (plants,
fungi, microbes) apart. It only needs re-running when a new package brings new taxa.
"""

import csv
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "taxonomy_lineage.tsv"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=taxonomy&retmode=xml&id="
METAZOA = "33208"


def used_taxa() -> set[str]:
    """Numeric NCBI taxon IDs that subjects have, in any package's subject_role_taxonomy.tsv."""
    found = set()
    for path in ROOT.glob("data_real/**/subject_role_taxonomy.tsv"):
        with open(path, newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if (m := re.fullmatch(r"NCBI:txid(\d+)", (row.get("taxonomy_id") or "").strip())):
                    found.add(m.group(1))
    return found


def fetch(ids: list[str]) -> list[dict]:
    # curl rather than urllib: it uses the system's certificate store, which works on networks where
    # Python's bundled certificates don't.
    body = subprocess.run(["curl", "-sSf", "-m", "60", EFETCH + ",".join(ids)], capture_output=True, check=True).stdout
    root = ET.fromstring(body)
    rows = []
    for taxon in root.findall("Taxon"):
        lineage = [t.findtext("TaxId") for t in taxon.findall("LineageEx/Taxon")] + [taxon.findtext("TaxId")]
        names = [t.findtext("ScientificName") for t in taxon.findall("LineageEx/Taxon")]
        rows.append({"taxonomy_id": f"NCBI:txid{taxon.findtext('TaxId')}", "name": taxon.findtext("ScientificName"),
                     "rank": taxon.findtext("Rank"), "is_animal": str(METAZOA in lineage).lower(),
                     "lineage": "; ".join(names)})
    return rows


def main():
    ids = sorted(used_taxa(), key=int)
    rows = []
    for i in range(0, len(ids), 150):
        rows += fetch(ids[i:i + 150])
        time.sleep(0.5)  # stay within NCBI's request rate without an API key
    missing = set(ids) - {r["taxonomy_id"].removeprefix("NCBI:txid") for r in rows}
    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["taxonomy_id", "name", "rank", "is_animal", "lineage"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: int(r["taxonomy_id"].removeprefix("NCBI:txid"))))
    print(f"Wrote {OUT} ({len(rows)} taxa; not returned by NCBI: {sorted(missing) or 'none'})")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
