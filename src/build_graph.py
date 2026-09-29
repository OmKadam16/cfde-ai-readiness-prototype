"""
build_graph.py

Builds a small knowledge graph out of the C2M2 datapackage, linking
project -> subject -> biosample -> file using the association tables.
This is the "connect the dots between datasets" step: once entities are
graph-connected, you can query across them instead of digging through
separate tables by hand.

Usage:
    python3 build_graph.py
"""

import pandas as pd
import networkx as nx
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load(table):
    return pd.read_csv(DATA_DIR / f"{table}.tsv", sep="\t", dtype=str)


def build_graph() -> nx.DiGraph:
    G = nx.DiGraph()

    project = load("project")
    subject = load("subject")
    biosample = load("biosample")
    file_df = load("file")
    bio_from_subj = load("biosample_from_subject")
    file_desc_bio = load("file_describes_biosample")
    bio_disease = load("biosample_disease")

    # Add nodes with attributes
    for _, row in project.iterrows():
        G.add_node(f"project:{row.local_id}", type="project", name=row["name"])

    for _, row in subject.iterrows():
        G.add_node(f"subject:{row.local_id}", type="subject", sex=row["sex"], age=row["age_at_enrollment"])
        G.add_edge(f"subject:{row.local_id}", f"project:{row.project_local_id}", relation="enrolled_in")

    for _, row in biosample.iterrows():
        G.add_node(f"biosample:{row.local_id}", type="biosample", anatomy=row["anatomy"])
        G.add_edge(f"biosample:{row.local_id}", f"project:{row.project_local_id}", relation="collected_by")

    for _, row in file_df.iterrows():
        G.add_node(f"file:{row.local_id}", type="file", filename=row["filename"])
        G.add_edge(f"file:{row.local_id}", f"project:{row.project_local_id}", relation="produced_by")

    for _, row in bio_from_subj.iterrows():
        G.add_edge(f"biosample:{row.biosample_local_id}", f"subject:{row.subject_local_id}", relation="from_subject")

    for _, row in file_desc_bio.iterrows():
        G.add_edge(f"file:{row.file_local_id}", f"biosample:{row.biosample_local_id}", relation="describes")

    # Disease nodes: multiple biosamples can share the same disease node,
    # which is exactly the "connect disparate records" case -- two separate
    # experiments (different treatments) linking to the same disease.
    for _, row in bio_disease.iterrows():
        disease_node = f"disease:{row.disease}"
        G.add_node(disease_node, type="disease")
        G.add_edge(f"biosample:{row.biosample_local_id}", disease_node, relation=row.association_type)

    return G


def query_connected(G: nx.DiGraph, node_id: str, hops: int = 2):
    """Return everything connected to a node within N hops, either direction."""
    undirected = G.to_undirected()
    if node_id not in undirected:
        return []
    lengths = nx.single_source_shortest_path_length(undirected, node_id, cutoff=hops)
    return [(n, d) for n, d in lengths.items() if n != node_id]


if __name__ == "__main__":
    G = build_graph()
    print(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print()
    print("Node types:", {t: sum(1 for _, d in G.nodes(data=True) if d.get("type") == t)
                           for t in ["project", "subject", "biosample", "file", "disease"]})
    print()
    print("Example query: everything connected to disease:breast carcinoma within 2 hops")
    print("(shows two separate LINCS biosamples -- different treatments -- unified by one disease node)")
    for node, dist in query_connected(G, "disease:breast carcinoma", hops=2):
        print(f"  {node}  (distance {dist})  attrs={G.nodes[node]}")
