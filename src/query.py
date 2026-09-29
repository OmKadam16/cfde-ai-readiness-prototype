"""
query.py

A simple command-line query interface over the knowledge graph. This is
the "give it a simple way to ask questions" step -- instead of digging
through separate TSV tables by hand, ask the graph directly.

Usage examples:
    python3 query.py connected biosample:QC9XMFT8
    python3 query.py connected "disease:breast carcinoma" --hops 3
    python3 query.py list --type biosample
    python3 query.py search --anatomy brain
    python3 query.py search --dcc sparc
    python3 query.py show biosample:QC9XMFT8
"""

import argparse
import sys
from build_graph import build_graph, query_connected


def cmd_connected(G, args):
    node_id = args.node
    if node_id not in G:
        print(f"'{node_id}' not found in graph.")
        print("Tip: node IDs look like 'biosample:QC9XMFT8' or 'project:OT2OD023873'. "
              "Use 'list --type <type>' to see valid IDs.")
        return
    results = query_connected(G, node_id, hops=args.hops)
    print(f"Everything connected to '{node_id}' within {args.hops} hop(s): {len(results)} found\n")
    for node, dist in sorted(results, key=lambda x: x[1]):
        attrs = {k: v for k, v in G.nodes[node].items() if k != "type"}
        print(f"  [{dist} hop{'s' if dist > 1 else ''}] {node}  {attrs}")


def cmd_list(G, args):
    matches = [(n, d) for n, d in G.nodes(data=True) if d.get("type") == args.type]
    print(f"{len(matches)} node(s) of type '{args.type}':\n")
    for node, attrs in matches:
        extra = {k: v for k, v in attrs.items() if k != "type" and v == v}  # drop NaN
        print(f"  {node}  {extra}")


def cmd_search(G, args):
    field, value = None, None
    if args.anatomy:
        field, value = "anatomy", args.anatomy
    elif args.dcc:
        field, value = "dcc", args.dcc
    else:
        print("Specify --anatomy or --dcc to search.")
        return

    matches = [(n, d) for n, d in G.nodes(data=True)
               if str(d.get(field, "")).lower().find(value.lower()) != -1]
    print(f"{len(matches)} node(s) with {field} matching '{value}':\n")
    for node, attrs in matches:
        print(f"  {node}  {attrs}")


def cmd_show(G, args):
    node_id = args.node
    if node_id not in G:
        print(f"'{node_id}' not found in graph.")
        return
    print(f"{node_id}")
    print(f"  attributes: {G.nodes[node_id]}")
    print(f"  outgoing edges (this -> other):")
    for _, target, data in G.out_edges(node_id, data=True):
        print(f"    --{data.get('relation')}--> {target}")
    print(f"  incoming edges (other -> this):")
    for source, _, data in G.in_edges(node_id, data=True):
        print(f"    {source} --{data.get('relation')}--> ")


def main():
    parser = argparse.ArgumentParser(description="Query the CFDE prototype knowledge graph.")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("connected", help="Everything connected to a node within N hops")
    p1.add_argument("node", help="Node ID, e.g. biosample:QC9XMFT8")
    p1.add_argument("--hops", type=int, default=2)
    p1.set_defaults(func=cmd_connected)

    p2 = sub.add_parser("list", help="List all nodes of a given type")
    p2.add_argument("--type", required=True,
                     choices=["project", "subject", "biosample", "file", "disease"])
    p2.set_defaults(func=cmd_list)

    p3 = sub.add_parser("search", help="Search nodes by attribute")
    p3.add_argument("--anatomy", help="Substring match on anatomy")
    p3.add_argument("--dcc", help="Substring match on node ID (catches namespace, e.g. 'sparc')")
    p3.set_defaults(func=cmd_search)

    p4 = sub.add_parser("show", help="Show full detail + edges for one node")
    p4.add_argument("node")
    p4.set_defaults(func=cmd_show)

    args = parser.parse_args()
    G = build_graph()
    args.func(G, args)


if __name__ == "__main__":
    main()
